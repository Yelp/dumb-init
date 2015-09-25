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

pid_t forward_signals_to = -1;
char debug = 0;
char use_setsid = 1;


void forward_signal(int signum) {
    kill(forward_signals_to, signum);
    DEBUG("Forwarded signal %d to PID %d.\n", signum, forward_signals_to);
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


void register_signal_handlers_for(pid_t pid) {
    forward_signals_to = pid;
    for (int signum = 1; signum < 32; signum++) {
        if (signum == SIGKILL || signum == SIGSTOP || signum == SIGCHLD)
            continue;

        if (signal(signum, handle_signal) == SIG_ERR) {
            fprintf(stderr, "Error: Couldn't register signal handler for signal `%d`. Exiting.\n", signum);
            exit(1);
        }
    }
}


void reap_children_forever_until_pid(pid_t target_pid) {
    int status;
    int exit_status;
    pid_t killed_pid;
    while ((killed_pid = waitpid(-1, &status, 0))) {
        exit_status = WEXITSTATUS(status);
        DEBUG("A child with PID %d exited with exit status %d.\n", killed_pid, exit_status);

        if (killed_pid == target_pid) {
            // send SIGTERM to any remaining children
            forward_signal(SIGTERM);

            DEBUG("Child exited with status %d. Goodbye.\n", exit_status);
            exit(exit_status);
        }
    }
}


void drop_controlling_tty(void) {
    int fd = open("/dev/tty", O_RDWR);
    if (fd >= 0) {
        ioctl(fd, TIOCNOTTY);
        close(fd);
        DEBUG("Dropped our controlling TTY.\n");
    } else {
        DEBUG("Unable to open /dev/tty, assuming we had no controlling TTY.\n");
    }
}


int main(int argc, char *argv[]) {
    char *debug_env, *setsid_env;

    if (argc < 2) {
        print_help(argv);
        return 1;
    }

    debug_env = getenv("DUMB_INIT_DEBUG");
    if (debug_env && strcmp(debug_env, "1") == 0) {
        debug = 1;
        DEBUG("Running in debug mode.\n");
    }

    setsid_env = getenv("DUMB_INIT_SETSID");
    if (setsid_env && strcmp(setsid_env, "0") == 0) {
        use_setsid = 0;
        DEBUG("Not running in setsid mode.\n");
    }

    if (use_setsid) {
        /*
         * If running in setsid mode, we need to make sure of the following:
         *
         *   - The child must not be in an orphaned process group, because we
         *     want it to handle signals like SIGTSTP correctly.
         *
         *   - The child must not be in a new process group but still have a
         *     controlling terminal, or it will recevive SIGTTOU when it tries
         *     to print.
         *
         *  To achieve this, we fork off another dumb-init process (called the
         *  `slave`) which drops its controlling TTY and then spawns a child in
         *  a new process group.
         */
        pid_t slave_pid = fork();
        if (slave_pid < 0) {
            fprintf(stderr, "Unable to fork for slave. Exiting.\n");
            return 1;
        } else if (slave_pid == 0) {
            // slave process
            drop_controlling_tty();
            pid_t child_pid = fork();

            if (child_pid < 0) {
                fprintf(stderr, "Unable to fork for child. Exiting.\n");
                return 1;
            } else if (child_pid == 0) {
                // child process, exec after establishing pgroup
                if (setpgid(0, 0) != 0) {
                    fprintf(stderr, "Unable to setpgid (errno=%d %s).\n", errno, strerror(errno));
                    exit(1);
                }
                execvp(argv[1], &argv[1]);
            } else {
                // slave process, register signal handlers and wait() repeatedly
                DEBUG("Child spawned with PID %d.\n", child_pid);
                register_signal_handlers_for(-child_pid);
                reap_children_forever_until_pid(child_pid);
            }
        } else {
            // master process
            register_signal_handlers_for(slave_pid);
            reap_children_forever_until_pid(slave_pid);
        }
    } else {
        /*
         * If not running in setsid mode, simply spawn a single child and proxy
         * signals to it directly.
         */
        pid_t child_pid = fork();
        if (child_pid < 0) {
            fprintf(stderr, "Unable to fork for child. Exiting.\n");
            return 1;
        } else if (child_pid == 0) {
            execvp(argv[1], &argv[1]);
        } else {
            DEBUG("Child spawned with PID %d.\n", child_pid);
            register_signal_handlers_for(child_pid);
            reap_children_forever_until_pid(child_pid);
        }
    }
}
