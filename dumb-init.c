/*
 * dumb-init is a simple wrapper program designed to run as PID 1 and pass
 * signals to its children.
 *
 * Usage:
 *   ./dumb-init python -c 'while True: pass'
 *
 * To get debug output on stderr, run with DUMB_INIT_DEBUG=1.
 */

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

pid_t child = -1;
char debug = 0;

void signal_handler(int signum) {
    if (debug)
        fprintf(stderr, "Received signal %d.\n", signum);

    if (child > 0) {
        kill(child, signum);

        if (debug)
            fprintf(stderr, "Forwarded signal to child.\n");
    }
}

void print_help(char *argv[]) {
    fprintf(stderr,
        "Usage: %s COMMAND [[ARG] ...]\n"
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
        "Docker anyway).\n",
        argv[0]
    );
}

int main(int argc, char *argv[]) {
    int signum, exit_status, status = 0;
    char *debug_env;

    if (argc < 2) {
        print_help(argv);
        return 1;
    }

    debug_env = getenv("DUMB_INIT_DEBUG");
    if (debug_env && strcmp(debug_env, "1") == 0)
        debug = 1;


    /* register signal handlers */
    for (signum = 1; signum < 32; signum++) {
        if (signum == SIGKILL || signum == SIGSTOP || signum == SIGCHLD)
            continue;

        if (signal(signum, signal_handler) == SIG_ERR) {
            fprintf(stderr, "Error: Couldn't register signal handler for signal `%d`. Exiting.\n", signum);
            return 1;
        }
    }

    /* launch our process */
    child = fork();

    if (child < 0) {
        fprintf(stderr, "Unable to fork. Exiting.\n");
        return 1;
    }

    if (child == 0) {
        execvp(argv[1], &argv[1]);
    } else {
        if (debug)
            fprintf(stderr, "Child spawned with PID %d.\n", child);

        waitpid(child, &status, 0);
        exit_status = WEXITSTATUS(status);

        if (debug)
            fprintf(stderr, "Child exited with status %d, goodbye.\n", exit_status);

        return exit_status;
    }

    return 0;
}
