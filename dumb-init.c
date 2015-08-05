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

int main(int argc, char *argv[]) {
	int signum;
	char* debug_env;

	if (argc < 2) {
		fprintf(stderr, "Try providing some arguments.\n");
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

		waitpid(child, NULL, 0);

		if (debug)
			fprintf(stderr, "Child exited, goodbye.\n");
	}

	return 0;
}
