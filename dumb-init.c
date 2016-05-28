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

pid_t child_pid = -1;
char debug = 0;
char use_setsid = 1;

void forward_signal(int signum) {
    kill(use_setsid ? -child_pid : child_pid, signum);
    DEBUG("Forwarded signal %d to children.\n", signum);
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
 * When running in setsid mode, however, it is not sufficient to forward
 * SIGTSTP/SIGTTIN/SIGTTOU in most cases. If the process has not added a custom
 * signal handler for these signals, then the kernel will not apply default
 * signal handling behavior (which would be suspending the process) since it is
 * a member of an orphaned process group.
 *
 * Sadly this doesn't appear to be well documented except in the kernel itself:
 * https://github.com/torvalds/linux/blob/v4.2/kernel/signal.c#L2296-L2299
 *
 * Forwarding SIGSTOP instead is effective, though not ideal; unlike SIGTSTP,
 * SIGSTOP cannot be caught, and so it doesn't allow processes a change to
 * clean up before suspending. In non-setsid mode, we proxy the original signal
 * instead of SIGSTOP for this reason.
*/
void handle_signal(int signum) {
    DEBUG("Received signal %d.\n", signum);
    if (signum == SIGCHLD) {
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
    } else if (
        signum == SIGTSTP || // tty: background yourself
        signum == SIGTTIN || // tty: stop reading
        signum == SIGTTOU    // tty: stop writing
    ) {
        if (use_setsid) {
            DEBUG("Running in setsid mode, so forwarding SIGSTOP instead.\n");
            forward_signal(SIGSTOP);
        } else {
            DEBUG("Not running in setsid mode, so forwarding the original signal (%d).\n", signum);
            forward_signal(signum);
        }

        DEBUG("Suspending self due to TTY signal.\n");
        kill(getpid(), SIGSTOP);
    } else {
        forward_signal(signum);
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
        "   -v, --verbose        Print debugging information to stderr.\n"
        "   -h, --help           Print this help message and exit.\n"
        "   -V, --version        Print the current version and exit.\n"
        "\n"
        "Full help is available online at https://github.com/Yelp/dumb-init\n",
        VERSION,
        argv[0]
    );
}


char **parse_command(int argc, char *argv[]) {
    int opt;
    struct option long_options[] = {
        {"help",         no_argument, NULL, 'h'},
        {"single-child", no_argument, NULL, 'c'},
        {"verbose",      no_argument, NULL, 'v'},
        {"version",      no_argument, NULL, 'V'},
    };
    while ((opt = getopt_long(argc, argv, "+hvVc", long_options, NULL)) != -1) {
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

    return &argv[optind];
}

int main(int argc, char *argv[]) {
    char **cmd = parse_command(argc, argv);

    child_pid = fork();
    if (child_pid < 0) {
        PRINTERR("Unable to fork. Exiting.\n");
        return 1;
    } else if (child_pid == 0) {
        /* child */
        if (use_setsid) {
            if (setsid() == -1) {
                PRINTERR(
                    "Unable to setsid (errno=%d %s). Exiting.\n",
                    errno,
                    strerror(errno)
                );
                exit(1);
            }
            DEBUG("setsid complete.\n");
        }
        execvp(cmd[0], &cmd[0]);

        // if this point is reached, exec failed, so we should exit nonzero
        PRINTERR("%s: %s\n", cmd[0], strerror(errno));
        return 2;
    } else {
        /* parent */
        int signum;
        sigset_t all_signals;
        sigfillset(&all_signals);
        sigprocmask(SIG_BLOCK, &all_signals, NULL);

        DEBUG("Child spawned with PID %d.\n", child_pid);
        for (;;) {
            sigwait(&all_signals, &signum);
            handle_signal(signum);
        }
    }
}
