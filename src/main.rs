use std::fmt;
use std::process::exit;

use getopts::Fail;
use getopts::ParsingStyle;
use ioctl_rs::TIOCNOTTY;
use ioctl_rs::TIOCSCTTY;
use nix::ioctl_none_bad;
use nix::ioctl_write_int_bad;
use regex::Regex;

use std::ffi::CString;

use nix::sys::wait::waitpid;
use nix::sys::wait::WaitPidFlag;
use nix::sys::wait::WaitStatus;

use nix::sys::signal::kill;
use nix::sys::signal::signal;
use nix::sys::signal::sigprocmask;
use nix::sys::signal::SigHandler;
use nix::sys::signal::SigSet;
use nix::sys::signal::SigmaskHow;
use nix::sys::signal::Signal;

use nix::unistd::getpid;
use nix::unistd::getsid;
use nix::unistd::ForkResult;
use nix::unistd::Pid;

use getopts::Options;
use std::env;

ioctl_none_bad!(ioctl_tiocnotty, TIOCNOTTY);
ioctl_write_int_bad!(ioctl_tiocsctty, TIOCSCTTY);

// /*
//  * dumb-init is a simple wrapper program designed to run as PID 1 and pass
//  * signals to its children.
//  *
//  * Usage:
//  *   ./dumb-init python -c 'while True: pass'
//  *
//  * To get debug output on stderr, run with '-v'.
//  */
fn printerr(args: fmt::Arguments) {
    eprintln!("[dumb-init] {}", args);
}

fn debug(args: fmt::Arguments) {
    if unsafe { DEBUG } {
        printerr(args);
    }
}

// Signals we care about are numbered from 1 to 31, inclusive.
// (32 and above are real-time signals.)
// TODO: this is likely not portable outside of Linux, or on strange architectures
const MAXSIG: libc::c_int = 31;

#[derive(Debug, Copy, Clone)]
enum RewriteSignal {
    Drop,
    Rewrite(Signal),
}

// Indices are one-indexed (signal 1 is at index 1). Index zero is unused.
// User-specified signal rewriting.
static mut SIGNAL_REWRITE: [Option<RewriteSignal>; MAXSIG as usize + 1] =
    [None; MAXSIG as usize + 1];

// One-time ignores due to TTY quirks. 0 = no skip, 1 = skip the next-received signal.
static mut SIGNAL_TEMPORARY_IGNORES: [bool; MAXSIG as usize + 1] = [false; MAXSIG as usize + 1];

static mut CHILD_PID: Option<Pid> = None;
static mut DEBUG: bool = false;
static mut USE_SETSID: bool = true;

fn translate_signal(signum: Signal) -> Option<Signal> {
    if signum as i32 <= 0 || signum as i32 > MAXSIG {
        Some(signum)
    } else {
        let translation = unsafe { SIGNAL_REWRITE[signum as usize] };

        match translation {
            // not present in our translation set
            None => Some(signum),
            Some(translated) => {
                debug(format_args!(
                    "Translating signal {} to {:?}.",
                    signum, translated
                ));

                if let RewriteSignal::Rewrite(signal) = translated {
                    Some(signal)
                } else {
                    None
                }
            }
        }
    }
}

fn forward_signal(signum: Signal) {
    let translated: Option<Signal> = translate_signal(signum);
    match translated {
        Some(signum) => {
            let pid = unsafe { CHILD_PID.unwrap() };

            let pid_to_kill = if unsafe { USE_SETSID } {
                Pid::from_raw(-pid.as_raw())
            } else {
                pid
            };

            let _ = kill(pid_to_kill, signum);

            debug(format_args!(
                "Forwarded signal {} to children.",
                signum as i32
            ));
        }
        None => {
            debug(format_args!(
                "Not forwarding signal {} to children (ignored).",
                signum
            ));
        }
    }
}

/*
 * The dumb-init signal handler.
 *
 * The main job of this signal handler is to forward signals along to our child
 * process(es). In setsid mode, this means signaling the entire process group
 * rooted at our child. In non-setsid mode, this is just signaling the primary
 * child.
 *
 * In most cases, simply proxying the received signal is sufficient. If we
 * receive a job control signal, however, we should not only forward it, but
 * also sleep dumb-init itself.
 *
 * This allows users to run foreground processes using dumb-init and to
 * control them using normal shell job control features (e.g. Ctrl-Z to
 * generate a SIGTSTP and suspend the process).
 *
 * The libc manual is useful:
 * https://www.gnu.org/software/libc/manual/html_node/Job-Control-Signals.html
 *
*/
fn handle_signal(signum: Signal) {
    debug(format_args!("Received signal {}.", signum as i32));

    if unsafe { SIGNAL_TEMPORARY_IGNORES[signum as usize] } {
        debug(format_args!(
            "Ignoring tty hand-off signal {}.",
            signum as i32
        ));
        unsafe { SIGNAL_TEMPORARY_IGNORES[signum as usize] = false };
    } else if signum == Signal::SIGCHLD {
        loop {
            let exit_status: i32;
            let killed_pid: Pid;

            let result = waitpid(Pid::from_raw(-1), Some(WaitPidFlag::WNOHANG));

            if result.is_err() {
                break;
            }

            let result_unwrapped = result.unwrap();

            match result_unwrapped {
                WaitStatus::StillAlive => break,
                WaitStatus::Exited(pid, status) => {
                    exit_status = status;
                    killed_pid = pid;
                    debug(format_args!(
                        "A child with PID {} exited with exit status {}.",
                        killed_pid, exit_status
                    ));
                }
                WaitStatus::Signaled(pid, status, _) => {
                    killed_pid = pid;
                    exit_status = 128 + status as i32;
                    debug(format_args!(
                        "A child with PID {} was terminated by signal {}.",
                        killed_pid,
                        exit_status - 128
                    ));
                }
                _ => {
                    assert!(matches!(result_unwrapped, WaitStatus::Signaled(_, _, _)));
                    break;
                }
            }

            if unsafe { Some(killed_pid) == CHILD_PID } {
                forward_signal(Signal::SIGTERM); // send SIGTERM to any remaining children
                debug(format_args!(
                    "Child exited with status {}. Goodbye.",
                    exit_status
                ));

                exit(exit_status);
            }
        }
    } else {
        forward_signal(signum);
        if signum == Signal::SIGTSTP || signum == Signal::SIGTTOU || signum == Signal::SIGTTIN {
            debug(format_args!("Suspending self due to TTY signal."));
            let _ = kill(getpid(), Signal::SIGSTOP);
        }
    }
}

fn parse_rewrite_signum(arg: &str) {
    let regex = Regex::new(r"^(\d{1,2}?):(-1|\d{1,2}?)$").unwrap();

    match regex.captures(arg) {
        Some(captures) if captures.len() == 3 => {
            let signum = str::parse::<i32>(&captures[1]);
            let replacement = str::parse::<i32>(&captures[2]);

            match (signum, replacement) {
                (Ok(s), Ok(r)) if (1..=MAXSIG).contains(&s) && (0..=MAXSIG).contains(&r) => {
                    let rewrite = if r == 0 {
                        Some(RewriteSignal::Drop)
                    } else {
                        Some(RewriteSignal::Rewrite(Signal::try_from(r).unwrap()))
                    };

                    unsafe {
                        SIGNAL_REWRITE[s as usize] = rewrite;
                    }

                    return;
                }
                _ => {}
            }
        }
        _ => {}
    }

    print_rewrite_signum_help();
}

fn print_help(version: &str, executable_name: &str) {
    eprintln!(
        "dumb-init v{}
Usage: {} [option] command [[arg] ...]

dumb-init is a simple process supervisor that forwards signals to children.
It is designed to run as PID1 in minimal container environments.

Optional arguments:
   -c, --single-child   Run in single-child mode.
                        In this mode, signals are only proxied to the
                        direct child and not any of its descendants.
   -r, --rewrite s:r    Rewrite received signal s to new signal r before proxying.
                        To ignore (not proxy) a signal, rewrite it to 0.
                        This option can be specified multiple times.
   -v, --verbose        Print debugging information to stderr.
   -h, --help           Print this help message and exit.
   -V, --version        Print the current version and exit.

Full help is available online at https://github.com/Yelp/dumb-init",
        version, executable_name
    );
}

fn print_rewrite_signum_help() {
    eprintln!("Usage: -r option takes <signum>:<signum>, where <signum> is between 1 and {}.\nThis option can be specified multiple times.\nUse --help for full usage.",         MAXSIG    );

    exit(1);
}

unsafe fn set_rewrite_to_sigstop_if_not_defined(signum: Signal) {
    if SIGNAL_REWRITE[signum as usize].is_none() {
        SIGNAL_REWRITE[signum as usize] = Some(RewriteSignal::Rewrite(Signal::SIGSTOP));
    }
}

fn parse_command() -> Vec<String> {
    let args: Vec<String> = env::args().collect();

    let mut opts = Options::new();
    opts.parsing_style(ParsingStyle::StopAtFirstFree);
    opts.optflag("c", "single-child", "");
    opts.optmulti("r", "rewrite", "", "");
    opts.optflag("v", "verbose", "");
    opts.optflag("h", "help", "");
    opts.optflag("V", "version", "");

    let matches = match opts.parse(&args[1..]) {
        Ok(m) => m,
        Err(f) => match f {
            Fail::UnrecognizedOption(option) => {
                eprintln!("dumb-init: unrecognized option: {}", option);
                exit(1)
            }
            Fail::ArgumentMissing(_) => todo!(),
            Fail::OptionMissing(_) => todo!(),
            Fail::OptionDuplicated(_) => todo!(),
            Fail::UnexpectedArgument(_) => todo!(),
        },
    };

    if matches.opt_present("h") {
        print_help(env!("CARGO_PKG_VERSION"), env!("CARGO_PKG_NAME"));
        exit(0);
    }
    if matches.opt_present("v") {
        unsafe {
            DEBUG = true;
        }
    }
    if matches.opt_present("V") {
        eprintln!("dumb-init v{}", env!("CARGO_PKG_VERSION"));

        exit(0);
    }
    if matches.opt_present("c") {
        unsafe {
            USE_SETSID = false;
        }
    }

    matches.opt_strs("r").iter().for_each(|value| {
        parse_rewrite_signum(value);
    });

    let rest = matches.free;

    if rest.is_empty() {
        eprintln!(
            "Usage: {} [option] program [args]\nTry {} --help for full usage.",
            env!("CARGO_PKG_NAME"),
            env!("CARGO_PKG_NAME")
        );

        exit(1);
    }

    let debug_env = std::env::var("DUMB_INIT_DEBUG");

    if debug_env.unwrap_or_default() == *"1" {
        unsafe { DEBUG = true };
        debug(format_args!("Running in debug mode."));
    }

    let setsid_env = std::env::var("DUMB_INIT_SETSID");

    if setsid_env.unwrap_or_default() == *"0" {
        unsafe { USE_SETSID = false };
        debug(format_args!("Not running in setsid mode."));
    }

    if unsafe { USE_SETSID } {
        unsafe {
            set_rewrite_to_sigstop_if_not_defined(Signal::SIGTSTP);
            set_rewrite_to_sigstop_if_not_defined(Signal::SIGTTOU);
            set_rewrite_to_sigstop_if_not_defined(Signal::SIGTTIN);
        }
    }

    rest
}

// A dummy signal handler used for signals we care about.
// On the FreeBSD kernel, ignored signals cannot be waited on by `sigwait` (but
// they can be on Linux). We must provide a dummy handler.
// https://lists.freebsd.org/pipermail/freebsd-ports/2009-October/057340.html
extern "C" fn dummy(_signum: libc::c_int) {}

fn main() {
    let remainder = parse_command();

    let all_signals: SigSet = SigSet::all();

    let _ = sigprocmask(SigmaskHow::SIG_BLOCK, Some(&all_signals), None);

    for i in 1..=MAXSIG {
        unsafe {
            let _ = signal(Signal::try_from(i).unwrap(), SigHandler::Handler(dummy));
        }
    }

    /*
     * Detach dumb-init from controlling tty, so that the child's session can
     * attach to it instead.
     *
     * We want the child to be able to be the session leader of the TTY so that
     * it can do normal job control.
     */
    if unsafe { USE_SETSID } {
        let ioctl_result;
        unsafe { ioctl_result = ioctl_tiocnotty(libc::STDIN_FILENO) }
        if let Err(err) = ioctl_result {
            debug(format_args!(
                "Unable to detach from controlling tty (errno={} {}).",
                err,
                err.desc()
            ));
        } else {
            /*
             * When the session leader detaches from its controlling tty via
             * TIOCNOTTY, the kernel sends SIGHUP and SIGCONT to the process
             * group. We need to be careful not to forward these on to the
             * dumb-init child so that it doesn't receive a SIGHUP and
             * terminate itself (#136).
             */

            let sid = getsid(Some(Pid::from_raw(0)));
            let pid = getpid();

            match sid {
                Ok(p) if p == pid => {
                    debug(format_args!("Detached from controlling tty, ignoring the first SIGHUP and SIGCONT we receive."));
                    unsafe {
                        SIGNAL_TEMPORARY_IGNORES[Signal::SIGHUP as usize] = true;
                        SIGNAL_TEMPORARY_IGNORES[Signal::SIGCONT as usize] = true;
                    }
                }
                _ => {
                    debug(format_args!(
                        "Detached from controlling tty, but was not session leader."
                    ));
                }
            }
        }
    }

    match unsafe { nix::unistd::fork() } {
        Err(_) => {
            printerr(format_args!("Unable to fork. Exiting."));
            exit(1);
        }
        Ok(ForkResult::Child) => {
            /* child */
            let _ = sigprocmask(SigmaskHow::SIG_UNBLOCK, Some(&all_signals), None);

            if unsafe { USE_SETSID } {
                if let Err(errno) = nix::unistd::setsid() {
                    printerr(format_args!(
                        "Unable to setsid (errno={} {}). Exiting.",
                        errno as i32,
                        errno.desc()
                    ));

                    exit(1)
                }

                if let Err(errno) = unsafe { ioctl_tiocsctty(libc::STDIN_FILENO, 0) } {
                    debug(format_args!(
                        "Unable to attach to controlling tty (errno={} {}).",
                        errno as i32,
                        errno.desc()
                    ));
                }
                debug(format_args!("setsid complete."));
            }

            let mut for_vp: Vec<CString> = remainder
                .into_iter()
                .map(|f| std::ffi::CString::new(f).unwrap())
                .collect();

            for_vp.shrink_to_fit();

            let error = nix::unistd::execvp(&for_vp[0], &for_vp).unwrap_err();

            // if this point is reached, exec failed, so we should exit nonzero
            printerr(format_args!(
                "{}: {}",
                &for_vp[0].to_str().unwrap(),
                error.desc()
            ));

            exit(2);
        }
        Ok(ForkResult::Parent { child }) => {
            unsafe { CHILD_PID = Some(child) };
            /* parent */
            debug(format_args!("Child spawned with PID {}.", child));

            if let Err(err) = nix::unistd::chdir("/") {
                debug(format_args!(
                    "Unable to chdir(\"/\") (errno={} {})",
                    err as i32,
                    err.desc()
                ));
            }

            loop {
                let signum = all_signals.wait().unwrap();
                handle_signal(signum);
            }
        }
    }
}
