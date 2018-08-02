#!/usr/bin/env python
"""Print received signals with current timestamp to stdout.

Since all signals are printed and otherwise ignored, you'll need to send
SIGKILL (kill -9) to this process to actually end it.
"""
from __future__ import print_function

import os
import signal
import sys
import time


CATCHABLE_SIGNALS = frozenset(
    set(range(1, 32)) - set([signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD])
)


print_queue = []
last_signal = None


def unbuffered_print(line):
    sys.stdout.write('{0}\n'.format(line))
    sys.stdout.flush()


def print_signal(signum, _):
    msg = '{}:{}'.format(signum, time.time())
    print_queue.append(msg)

def signum_from_msg(msg):
    return msg.split(':')[0]

if __name__ == '__main__':
    for signum in CATCHABLE_SIGNALS:
        signal.signal(signum, print_signal)

    unbuffered_print('ready (pid: {0})'.format(os.getpid()))

    # loop forever just printing signals
    while True:
        if print_queue:
            msg = print_queue.pop()
            unbuffered_print(msg)
            signum = signum_from_msg(msg)
            if signum == signal.SIGINT and last_signal == signal.SIGINT:
                print('Received SIGINT twice, exiting.')
                exit(0)
            last_signal = signum

        time.sleep(0.01)
