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
#include <limits.h>
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
char *signal_observers[MAXSIG + 1] = {[0 ... MAXSIG] = NULL};
// One-time ignores due to TTY quirks. 0 = no skip, 1 = skip the next-received signal.
char signal_temporary_ignores[MAXSIG + 1] = {[0 ... MAXSIG] = 0};

pid_t child_pid = -1;
char debug = 0;
char use_setsid = 1;

int translate_signal(int signum) {
    if (signum <= 0 || signum > MAXSIG) {
        return signum;
    } else {
        int translated = signal_rewrite[signum];
        if (translated == -1) {
            return signum;
        } else {
            DEBUG("Translating signal %d to %d.\n", signum, translated);
            return translated;
        }
    }
}

void forward_signal(int signum) {
    int replacement = translate_signal(signum);
    char *observer = signal_observers[signum];
    char s[10];

    if (observer) {
        pid_t observer_pid = fork();

        if (observer_pid < 0) {
            PRINTERR("%s: unable to fork observer\n", observer);
        } else if (observer_pid == 0) {
            /* child */
            sigset_t all_signals;

            sigfillset(&all_signals);
            sigprocmask(SIG_UNBLOCK, &all_signals, NULL);

            snprintf(s, 10, "%d", signum);
            setenv("DUMB_INIT_SIGNUM", s, 1);
            snprintf(s, 10, "%d", replacement);
            setenv("DUMB_INIT_REPLACEMENT_SIGNUM", s, 1);

            execl(observer, observer, NULL);

            PRINTERR("%s: %s\n", observer, strerror(errno));
        } else {
            /* parent */
            DEBUG("%s: Observer spawned with PID %d.\n", observer, observer_pid);
        }
    }

    if (replacement != 0) {
        kill(use_setsid ? -child_pid : child_pid, replacement);
        DEBUG("Forwarded signal %d to children.\n", replacement);
    } else {
        DEBUG("Not forwarding signal %d to children (ignored).\n", replacement);
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
    DEBUG("Received signal %d.\n", signum);

    if (signal_temporary_ignores[signum] == 1) {
        DEBUG("Ignoring tty hand-off signal %d.\n", signum);
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
                DEBUG("A child with PID %d was terminated by signal %d.\n", killed_pid, exit_status - 128);
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
        "   -r, --rewrite s:r[:observer]\n"
        "                        Rewrite received signal s to new signal r before\n"
        "                        proxying. To ignore (not proxy) a signal, rewrite it\n"
        "                        to 0. The optional observer is a script or executable\n"
        "                        to execute when signal s is received (regardless\n"
        "                        of any rewriting). It must expect no arguments, but\n"
        "                        the DUMB_INIT_SIGNUM and DUMB_INIT_REPLACEMENT_SIGNUM\n"
        "                        environment variables will be set. This option can be\n"
        "                        specified multiple times.\n"
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
        "Usage: -r option takes <signum>:<signum>[:<observer>], "
        "where <signum> is between 1 and %d.\n"
        "<observer> must be a path to an executable or an executable "
        "that can be found in the PATH. It must expect no arguments.\n"
        "This option can be specified multiple times.\n"
        "Use --help for full usage.\n",
        MAXSIG
    );
    exit(1);
}

char *find_path(const char *partial) {
    static char **path_entries = NULL;
    static int path_count = 0;

    if (strchr(partial, '/')) {
        return !access(partial, X_OK) ? strdup(partial) : NULL;
    } else {
        int i;
        size_t plen;
        char file[PATH_MAX];

        if (!path_entries) {
            char *path, *tokpath, *s;

            path = getenv("PATH");

            if (!(tokpath = strdup(path && strlen(path) ? path : "/bin:/usr/bin:/sbin:/usr/sbin"))) {
                PRINTERR("cannot get PATH\n");
                exit(1);
            }

            for (path_count = 1, s = tokpath; (s = strchr(s, ':')); path_count++, s++) {
                ;
            }

            if (!(path_entries = (char**)malloc(path_count * sizeof(char*)))) {
                PRINTERR("cannot not create PATH entries\n");
                exit(1);
            }

            for(i = 0, s = strtok(tokpath, ":"); s; s = strtok(NULL, ":"),  i++) {
                path_entries[i] = strdup(s);
            }

            free(tokpath);
        }

        for (plen = strlen(partial), i = 0; i < path_count; i++) {
            if (plen + strlen(path_entries[i]) < (PATH_MAX - 2)) {
                sprintf(file, "%s/%s", path_entries[i], partial);

                if (!access(file, X_OK)) {
                    return strdup(file);
                }
            }
        }
    }

    return NULL;
}

void parse_rewrite_signum(char *arg) {
    int signum, replacement, position;
    size_t length;
    char *observer, *path;

    if (
        sscanf(arg, "%d:%d%n", &signum, &replacement, &position) == 2 &&
        (signum >= 1 && signum <= MAXSIG) &&
        (replacement >= 0 && replacement <= MAXSIG)
    ) {
        signal_rewrite[signum] = replacement;
    } else {
        print_rewrite_signum_help();
    }

    observer = arg + position;

    if ((*observer++ == ':') && (length = strlen(observer))) {
      if (!(path = find_path(observer))) {
          PRINTERR("%s: observer not found or not executable\n", observer);
          exit(1);
      }

      signal_observers[signum] = path;
    }
}

void set_rewrite_to_sigstop_if_not_defined(int signum) {
    if (signal_rewrite[signum] == -1) {
        signal_rewrite[signum] = SIGSTOP;
    }
}

char **parse_command(int argc, char *argv[]) {
    int opt;
    struct option long_options[] = {
        {"help",         no_argument,       NULL, 'h'},
        {"single-child", no_argument,       NULL, 'c'},
        {"rewrite",      required_argument, NULL, 'r'},
        {"verbose",      no_argument,       NULL, 'v'},
        {"version",      no_argument,       NULL, 'V'},
        {NULL,                     0,       NULL,   0},
    };
    while ((opt = getopt_long(argc, argv, "+hvVcr:", long_options, NULL)) != -1) {
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
