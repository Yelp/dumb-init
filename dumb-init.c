/*
 * dumb-init is a simple wrapper program designed to run as PID 1 and pass
 * signals to its children.
 *
 * Usage:
 *   ./dumb-init python -c 'while True: pass'
 *
 * To get debug output on stderr, run with '-v'.
 */

#include <assert.h>
#include <errno.h>
#include <getopt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include "VERSION.h"

#define PRINTERR(...) do { \
    fprintf(stderr, "[dumb-init] " __VA_ARGS__); \
} while (0)

#define DEBUG(...) do { \
    if (debug) { \
        PRINTERR(__VA_ARGS__); \
    } \
} while (0)

// Signals we care about are numbered from 1 to 31, inclusive.
// (32 and above are real-time signals.)
// TODO: this is likely not portable outside of Linux, or on strange architectures
#define MAXSIG 31

// Indices are one-indexed (signal 1 is at index 1). Index zero is unused.
// User-specified signal rewriting.
int signal_rewrite[MAXSIG + 1] = {[0 ... MAXSIG] = -1};
// One-time ignores due to TTY quirks. 0 = no skip, 1 = skip the next-received signal.
char signal_temporary_ignores[MAXSIG + 1] = {[0 ... MAXSIG] = 0};

pid_t child_pid = -1;
char debug = 0;
char use_setsid = 1;

typedef struct signame_map_entry {
    const int signum;
    const char *signame;
} signame_map_entry;

static const signame_map_entry signame_map[] = {
#ifdef SIGABRT
    { SIGABRT,   "ABRT"   },
#endif
#ifdef SIGALRM
    { SIGALRM,   "ALRM"   },
#endif
#ifdef SIGBUS
    { SIGBUS,    "BUS"    },
#endif
#ifdef SIGCHLD
    { SIGCHLD,   "CHLD"   },
#endif
#ifdef SIGCONT
    { SIGCONT,   "CONT"   },
#endif
#ifdef SIGEMT
    { SIGEMT,    "EMT"    },
#endif
#ifdef SIGFPE
    { SIGFPE,    "FPE"    },
#endif
#ifdef SIGHUP
    { SIGHUP,    "HUP"    },
#endif
#ifdef SIGILL
    { SIGILL,    "ILL"    },
#endif
#ifdef SIGINFO
    { SIGINFO,   "INFO"   },
#endif
#ifdef SIGINT
    { SIGINT,    "INT"    },
#endif
#ifdef SIGIO
    { SIGIO,     "IO"     },
#endif
#ifdef SIGIOT
    { SIGIOT,    "IOT"    },
#endif
#ifdef SIGKILL
    { SIGKILL,   "KILL"   },
#endif
#ifdef SIGLOST
    { SIGLOST,   "LOST"   },
#endif
#ifdef SIGPIPE
    { SIGPIPE,   "PIPE"   },
#endif
#ifdef SIGPOLL
    { SIGPOLL,   "POLL"   },
#endif
#ifdef SIGPROF
    { SIGPROF,   "PROF"   },
#endif
#ifdef SIGPWR
    { SIGPWR,    "PWR"    },
#endif
#ifdef SIGQUIT
    { SIGQUIT,   "QUIT"   },
#endif
#ifdef SIGSEGV
    { SIGSEGV,   "SEGV"   },
#endif
#ifdef SIGSTKFLT
    { SIGSTKFLT, "STKFLT" },
#endif
#ifdef SIGSTOP
    { SIGSTOP,   "STOP"   },
#endif
#ifdef SIGSYS
    { SIGSYS,    "SYS"    },
#endif
#ifdef SIGTERM
    { SIGTERM,   "TERM"   },
#endif
#ifdef SIGTRAP
    { SIGTRAP,   "TRAP"   },
#endif
#ifdef SIGTSTP
    { SIGTSTP,   "TSTP"   },
#endif
#ifdef SIGTTIN
    { SIGTTIN,   "TTIN"   },
#endif
#ifdef SIGTTOU
    { SIGTTOU,   "TTOU"   },
#endif
#ifdef SIGUNUSED
    { SIGUNUSED, "UNUSED" },
#endif
#ifdef SIGURG
    { SIGURG,    "URG"    },
#endif
#ifdef SIGUSR1
    { SIGUSR1,   "USR1"   },
#endif
#ifdef SIGUSR2
    { SIGUSR2,   "USR2"   },
#endif
#ifdef SIGVTALRM
    { SIGVTALRM, "VTALRM" },
#endif
#ifdef SIGWINCH
    { SIGWINCH,  "WINCH"  },
#endif
#ifdef SIGXCPU
    { SIGXCPU,   "XCPU"   },
#endif
#ifdef SIGXFSZ
    { SIGXFSZ,   "XFSZ"   },
#endif
};
int signame_map_size = sizeof(signame_map) / sizeof(signame_map[0]);

const char *signum_to_signame(int signum) {
    int i;

    for (i = 0; i < signame_map_size; i++) {
        if (signame_map[i].signum == signum) {
            return signame_map[i].signame;
        }
    }

    return NULL;
}

int signame_to_signum(const char *signame) {
    int i;
    const char *name = signame;

    if (!strncmp(name, "SIG", 3)) {
        name += 3;
    }

    for (i = 0; i < signame_map_size; i++) {
        if (!strcmp(signame_map[i].signame, name)) {
            return signame_map[i].signum;
        }
    }

    return 0;
}

int translate_signal(int signum) {
    if (signum <= 0 || signum > MAXSIG) {
        return signum;
    } else {
        int translated = signal_rewrite[signum];
        if (translated == -1) {
            return signum;
        } else {
            DEBUG("Translating signal %d (%s) to %d (%s).\n", signum, signum_to_signame(signum), translated, signum_to_signame(translated));
            return translated;
        }
    }
}

void forward_signal(int signum) {
    signum = translate_signal(signum);
    if (signum != 0) {
        kill(use_setsid ? -child_pid : child_pid, signum);
        DEBUG("Forwarded signal %d (%s) to children.\n", signum, signum_to_signame(signum));
    } else {
        DEBUG("Not forwarding signal %d to children (ignored).\n", signum);
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
void handle_signal(int signum) {
    DEBUG("Received signal %d (%s).\n", signum, signum_to_signame(signum));

    if (signal_temporary_ignores[signum] == 1) {
        DEBUG("Ignoring tty hand-off signal %d (%s).\n", signum, signum_to_signame(signum));
        signal_temporary_ignores[signum] = 0;
    } else if (signum == SIGCHLD) {
        int status, exit_status;
        pid_t killed_pid;
        while ((killed_pid = waitpid(-1, &status, WNOHANG)) > 0) {
            if (WIFEXITED(status)) {
                exit_status = WEXITSTATUS(status);
                DEBUG("A child with PID %d exited with exit status %d.\n", killed_pid, exit_status);
            } else {
                assert(WIFSIGNALED(status));
                exit_status = 128 + WTERMSIG(status);
                DEBUG("A child with PID %d was terminated by signal %d (%s).\n", killed_pid, exit_status - 128, signum_to_signame(exit_status - 128));
            }

            if (killed_pid == child_pid) {
                forward_signal(SIGTERM);  // send SIGTERM to any remaining children
                DEBUG("Child exited with status %d. Goodbye.\n", exit_status);
                exit(exit_status);
            }
        }
    } else {
        forward_signal(signum);
        if (signum == SIGTSTP || signum == SIGTTOU || signum == SIGTTIN) {
            DEBUG("Suspending self due to TTY signal.\n");
            kill(getpid(), SIGSTOP);
        }
    }
}

void print_help(char *argv[]) {
    fprintf(stderr,
        "dumb-init v%s"
        "Usage: %s [option] command [[arg] ...]\n"
        "\n"
        "dumb-init is a simple process supervisor that forwards signals to children.\n"
        "It is designed to run as PID1 in minimal container environments.\n"
        "\n"
        "Optional arguments:\n"
        "   -c, --single-child   Run in single-child mode.\n"
        "                        In this mode, signals are only proxied to the\n"
        "                        direct child and not any of its descendants.\n"
        "   -r, --rewrite s:r    Rewrite received signal s to new signal r before proxying.\n"
        "                        Signals may be specified as numbers or names like USR1 or\n"
        "                        SIGINT (see -l/--list). To ignore (not proxy) a signal,\n"
        "                        rewrite it to 0. This option can be specified multiple\n"
        "                        times.\n"
        "   -l, --list           Print signal number to name mapping and exit.\n"
        "   -v, --verbose        Print debugging information to stderr.\n"
        "   -h, --help           Print this help message and exit.\n"
        "   -V, --version        Print the current version and exit.\n"
        "\n"
        "Full help is available online at https://github.com/Yelp/dumb-init\n",
        VERSION,
        argv[0]
    );
}

void print_rewrite_signum_help() {
    fprintf(
        stderr,
        "Usage: -r option takes <signum>:<signum>, where <signum> "
        "is between 1 and %d, specified by number or name.\n"
        "This option can be specified multiple times.\n"
        "Use --help for full usage.\n",
        MAXSIG
    );
    exit(1);
}

int scansignal(const char *arg, int min, int *pos) {
    int signum, outpos;
    char signame[10];

    if (
        sscanf(arg, "%d%n", &signum, &outpos) == 1
        && (signum >= min && signum <= MAXSIG)
    ) {
        *pos = outpos;
        return signum;
    } else if (
        (
            sscanf(arg, "SIG%9[A-Z0-9]%n", signame, &outpos) == 1
            || sscanf(arg, "%9[A-Z0-9]%n", signame, &outpos) == 1
        )
        && (signum = signame_to_signum(signame))
        && (signum >= min && signum <= MAXSIG)
    ) {
        *pos = outpos;
        return signum;
    } else {
        print_rewrite_signum_help();
    }

    return -1;
}

void parse_rewrite_signum(char *arg) {
    int signum, replacement, pos;

    if (
        (signum = scansignal(arg, 1, &pos)) >= 1
        && arg[pos] == ':'
        && (replacement = scansignal(arg += pos + 1, 0, &pos)) >= 0
        && arg[pos] == 0
    ) {
        signal_rewrite[signum] = replacement;
    } else {
        print_rewrite_signum_help();
    }
}

void set_rewrite_to_sigstop_if_not_defined(int signum) {
    if (signal_rewrite[signum] == -1) {
        signal_rewrite[signum] = SIGSTOP;
    }
}

char **parse_command(int argc, char *argv[]) {
    int opt, i;
    struct option long_options[] = {
        {"help",         no_argument,       NULL, 'h'},
        {"single-child", no_argument,       NULL, 'c'},
        {"rewrite",      required_argument, NULL, 'r'},
        {"list",         no_argument,       NULL, 'l'},
        {"verbose",      no_argument,       NULL, 'v'},
        {"version",      no_argument,       NULL, 'V'},
        {NULL,                     0,       NULL,   0},
    };
    while ((opt = getopt_long(argc, argv, "+hvVlcr:", long_options, NULL)) != -1) {
        switch (opt) {
            case 'h':
                print_help(argv);
                exit(0);
            case 'v':
                debug = 1;
                break;
            case 'V':
                fprintf(stderr, "dumb-init v%s", VERSION);
                exit(0);
            case 'l':
                for (i = 1; i <= MAXSIG; i++) {
                    fprintf(stderr, "%2d: %s\n", i, signum_to_signame(i));
                }

                exit(0);
            case 'c':
                use_setsid = 0;
                break;
            case 'r':
                parse_rewrite_signum(optarg);
                break;
            default:
                exit(1);
        }
    }

    if (optind >= argc) {
        fprintf(
            stderr,
            "Usage: %s [option] program [args]\n"
            "Try %s --help for full usage.\n",
            argv[0], argv[0]
        );
        exit(1);
    }

    char *debug_env = getenv("DUMB_INIT_DEBUG");
    if (debug_env && strcmp(debug_env, "1") == 0) {
        debug = 1;
        DEBUG("Running in debug mode.\n");
    }

    char *setsid_env = getenv("DUMB_INIT_SETSID");
    if (setsid_env && strcmp(setsid_env, "0") == 0) {
        use_setsid = 0;
        DEBUG("Not running in setsid mode.\n");
    }

    if (use_setsid) {
        set_rewrite_to_sigstop_if_not_defined(SIGTSTP);
        set_rewrite_to_sigstop_if_not_defined(SIGTTOU);
        set_rewrite_to_sigstop_if_not_defined(SIGTTIN);
    }

    return &argv[optind];
}

// A dummy signal handler used for signals we care about.
// On the FreeBSD kernel, ignored signals cannot be waited on by `sigwait` (but
// they can be on Linux). We must provide a dummy handler.
// https://lists.freebsd.org/pipermail/freebsd-ports/2009-October/057340.html
void dummy(int signum) {}

int main(int argc, char *argv[]) {
    char **cmd = parse_command(argc, argv);
    sigset_t all_signals;
    sigfillset(&all_signals);
    sigprocmask(SIG_BLOCK, &all_signals, NULL);

    int i = 0;
    for (i = 1; i <= MAXSIG; i++) {
        signal(i, dummy);
    }

    /*
     * Detach dumb-init from controlling tty, so that the child's session can
     * attach to it instead.
     *
     * We want the child to be able to be the session leader of the TTY so that
     * it can do normal job control.
     */
    if (use_setsid) {
        if (ioctl(STDIN_FILENO, TIOCNOTTY) == -1) {
            DEBUG(
                "Unable to detach from controlling tty (errno=%d %s).\n",
                errno,
                strerror(errno)
            );
        } else {
            /*
             * When the session leader detaches from its controlling tty via
             * TIOCNOTTY, the kernel sends SIGHUP and SIGCONT to the process
             * group. We need to be careful not to forward these on to the
             * dumb-init child so that it doesn't receive a SIGHUP and
             * terminate itself (#136).
             */
            if (getsid(0) == getpid()) {
                DEBUG("Detached from controlling tty, ignoring the first SIGHUP and SIGCONT we receive.\n");
                signal_temporary_ignores[SIGHUP] = 1;
                signal_temporary_ignores[SIGCONT] = 1;
            } else {
                DEBUG("Detached from controlling tty, but was not session leader.\n");
            }
        }
    }

    child_pid = fork();
    if (child_pid < 0) {
        PRINTERR("Unable to fork. Exiting.\n");
        return 1;
    } else if (child_pid == 0) {
        /* child */
        sigprocmask(SIG_UNBLOCK, &all_signals, NULL);
        if (use_setsid) {
            if (setsid() == -1) {
                PRINTERR(
                    "Unable to setsid (errno=%d %s). Exiting.\n",
                    errno,
                    strerror(errno)
                );
                exit(1);
            }

            if (ioctl(STDIN_FILENO, TIOCSCTTY, 0) == -1) {
                DEBUG(
                    "Unable to attach to controlling tty (errno=%d %s).\n",
                    errno,
                    strerror(errno)
                );
            }
            DEBUG("setsid complete.\n");
        }
        execvp(cmd[0], &cmd[0]);

        // if this point is reached, exec failed, so we should exit nonzero
        PRINTERR("%s: %s\n", cmd[0], strerror(errno));
        return 2;
    } else {
        /* parent */
        DEBUG("Child spawned with PID %d.\n", child_pid);
        for (;;) {
            int signum;
            sigwait(&all_signals, &signum);
            handle_signal(signum);
        }
    }
}
