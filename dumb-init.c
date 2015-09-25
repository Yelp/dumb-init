/*
 * dumb-init is a simple wrapper program designed to run as PID 1 and pass
 * signals to its children.
 *
 * Usage:
 *   ./dumb-init python -c 'while True: pass'
 *
 * To get debug output on stderr, run with DUMB_INIT_DEBUG=1
 */

#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define DEBUG(...) do { \
    if (debug) { \
        fprintf(stderr, __VA_ARGS__); \
    } \
} while (0)

void handle_signal(int signum);


pid_t child_pid = -1;
char debug = 0;
char use_setsid = 1;

void forward_signal(int signum) {
    if (child_pid > 0) {
        if (use_setsid) {
            // flush signal queue and re-register the handler
            kill(0, signum);
            signal(signum, SIG_IGN);
            signal(signum, handle_signal);

            DEBUG("Forwarded signal %d to process group.\n", signum);
        } else {
            kill(child_pid, signum);
            DEBUG("Forwarded signal %d to child.\n", signum);
        }
    } else {
        DEBUG("Didn't forward signal %d, no child exists yet.\n", signum);
    }
}

void handle_signal(int signum) {
    DEBUG("Received signal %d.\n", signum);
    forward_signal(signum);
}

void print_help(char *argv[]) {
    fprintf(stderr,
        "Usage: %s COMMAND [[ARG] ...]\n"
        "\n"
        "dumb-init is a simple process designed to run as PID 1 inside Docker\n"
        "containers and proxy signals to child processes.\n"
        "\n"
        "Docker runs your processes as PID1. The kernel doesn't apply default signal\n"
        "handling to PID1 processes, so if your process doesn't register a custom\n"
        "signal handler, signals like TERM will just bounce off your process.\n"
        "\n"
        "This can result in cases where sending signals to a `docker run` process\n"
        "results in the run process exiting, but the container continuing in the\n"
        "background.\n"
        "\n"
        "A workaround is to wrap your script in this proxy, which runs as PID1. Your\n"
        "process then runs as some other PID, and the kernel won't treat the signals\n"
        "that are proxied to them specially.\n"
        "\n"
        "The proxy dies when your process dies, so it must not double-fork or do other\n"
        "weird things (this is basically a requirement for doing things sanely in\n"
        "Docker anyway).\n"
        "\n"
        "By default, dumb-init starts a process group (and session, see: man 2 setsid)\n"
        "and signals all processes in it. This is usually useful behavior, but if for\n"
        "some reason you wish to disable it, run with DUMB_INIT_SETSID=0.\n",
        argv[0]
    );
}

int main(int argc, char *argv[]) {
    int signum;
    char *debug_env, *setsid_env;

    if (argc < 2) {
        print_help(argv);
        return 1;
    }

    debug_env = getenv("DUMB_INIT_DEBUG");
    if (debug_env && strcmp(debug_env, "1") == 0) {
        debug = 1;
        DEBUG("Running in debug mode with pid %d.\n", getpid());
    }

    setsid_env = getenv("DUMB_INIT_SETSID");
    if (setsid_env && strcmp(setsid_env, "0") == 0) {
        use_setsid = 0;
        DEBUG("Not running in setsid mode.\n");
    }

    /* register signal handlers */
    for (signum = 1; signum < 32; signum++) {
        if (signum == SIGKILL || signum == SIGSTOP || signum == SIGCHLD)
            continue;

        if (signal(signum, handle_signal) == SIG_ERR) {
            fprintf(stderr, "Error: Couldn't register signal handler for signal `%d`. Exiting.\n", signum);
            return 1;
        }
    }

    if (use_setsid) {
        /*
         * In setsid mode, we need to ensure that we are the process group
         * leader.
         *
         * If we are already the process group leader, then we are done.
         *
         * If we aren't, then we need to establish ourself as a new process
         * group leader. This requires dropping our controlling TTY, as
         * otherwise we will be considered backgrounded and attempts to print
         * will raise SIGTTOU.
         */
        if (getpgrp() != getpid()) {
            DEBUG("dumb-init is not already process group leader, starting a new pgroup.\n");

            // establish new process group
            pid_t result = setpgid(0, 0);
            if (result != 0) {
                fprintf(
                    stderr,
                    "Unable to create process group (errno=%d %s). Exiting.\n",
                    errno,
                    strerror(errno)
                );
                return 1;
            }
            DEBUG("Process group created.\n");

            // drop our controlling tty, if we have one
            int fd = open("/dev/tty", 0);
            if (fd != -1) {
                // we have a controlling tty, so drop it
                ioctl(fd, TIOCNOTTY);
                DEBUG("Dropped our controlling TTY.\n");
            } else {
                DEBUG("Unable to open /dev/tty, assuming we had no controlling TTY.\n");
            }
        } else {
            DEBUG("dumb-init is already process group leader.\n");
        }
    }

    /* launch our process */
    child_pid = fork();

    if (child_pid < 0) {
        fprintf(stderr, "Unable to fork. Exiting.\n");
        return 1;
    }

    if (child_pid == 0) {
        execvp(argv[1], &argv[1]);
    } else {
        pid_t killed_pid;
        int exit_status, status;

        DEBUG("Child spawned with PID %d.\n", child_pid);

        while ((killed_pid = waitpid(-1, &status, 0))) {
            exit_status = WEXITSTATUS(status);
            DEBUG("A child with PID %d exited with exit status %d.\n", killed_pid, exit_status);

            if (killed_pid == child_pid) {
                // send SIGTERM to any remaining children
                forward_signal(SIGTERM);

                DEBUG("Child exited with status %d. Goodbye.\n", exit_status);
                exit(exit_status);
            }
        }
    }

    return 0;
}
