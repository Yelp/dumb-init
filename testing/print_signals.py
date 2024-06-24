#!/usr/bin/env python
"""Print received signals to stdout.

Since all signals are printed and otherwise ignored, you'll need to send
SIGKILL (kill -9) to this process to actually end it.
"""
import os
import signal
import sys
import time


CATCHABLE_SIGNALS = frozenset(
    set(range(1, 32)) - {signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD},
)


print_queue = []
last_signal = None


def unbuffered_print(line):
    sys.stdout.write('{}\n'.format(line))
    sys.stdout.flush()


def print_signal(signum, _):
    print_queue.append(signum)


if __name__ == '__main__':
    for signum in CATCHABLE_SIGNALS:
        signal.signal(signum, print_signal)

    unbuffered_print('ready (pid: {})'.format(os.getpid()))

    # loop forever just printing signals
    while True:
        if print_queue:
            signum = print_queue.pop()
            unbuffered_print(signum)

            if signum == signal.SIGINT and last_signal == signal.SIGINT:
                print('Received SIGINT twice, exiting.')
                exit(0)
            last_signal = signum

        time.sleep(0.01)
