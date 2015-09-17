#!/usr/bin/env python
"""Print received signals to stdout.

Since all signals are printed and otherwise ignored, you'll need to send
SIGKILL (kill -9) to this process to actually end it.
"""
from __future__ import print_function

import os
import signal
import sys
import time

from tests.lib.testing import CATCHABLE_SIGNALS


print_queue = []


def unbuffered_print(line):
    sys.stdout.write('{0}\n'.format(line))
    sys.stdout.flush()


def print_signal(signum, _):
    print_queue.append(signum)


if __name__ == '__main__':
    for signum in CATCHABLE_SIGNALS:
        signal.signal(signum, print_signal)

    unbuffered_print('ready (pid: {0})'.format(os.getpid()))

    # loop forever just printing signals
    while True:
        if print_queue:
            unbuffered_print(print_queue.pop())

        time.sleep(0.01)
