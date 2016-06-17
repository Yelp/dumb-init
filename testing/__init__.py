import os
import re
import signal
import sys
from contextlib import contextmanager
from subprocess import PIPE
from subprocess import Popen

from py._path.local import LocalPath


# these signals cause dumb-init to suspend itself
SUSPEND_SIGNALS = frozenset([
    signal.SIGTSTP,
    signal.SIGTTOU,
    signal.SIGTTIN,
])

NORMAL_SIGNALS = frozenset(
    set(range(1, 32)) -
    set([signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD]) -
    SUSPEND_SIGNALS
)


@contextmanager
def print_signals(args=()):
    """Start print_signals and yield dumb-init process and print_signals PID."""
    proc = Popen(
        (
            ('dumb-init',) +
            tuple(args) +
            (sys.executable, '-m', 'testing.print_signals')
        ),
        stdout=PIPE,
    )
    line = proc.stdout.readline()
    m = re.match(b'^ready \(pid: ([0-9]+)\)\n$', line)
    assert m, line

    yield proc, m.group(1).decode('ascii')

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)


def child_pids(pid):
    """Return a list of direct child PIDs for the given PID."""
    pid = str(pid)
    tasks = LocalPath('/proc').join(pid, 'task').listdir()
    return set(
        int(child_pid)
        for task in tasks
        for child_pid in task.join('children').read().split()
    )


def pid_tree(pid):
    """Return a list of all descendant PIDs for the given PID."""
    children = child_pids(pid)
    return set(
        pid
        for child in children
        for pid in pid_tree(child)
    ) | children


def is_alive(pid):
    """Return whether a process is running with the given PID."""
    return LocalPath('/proc').join(str(pid)).isdir()


def process_state(pid):
    """Return a process' state, such as "stopped" or "running"."""
    status = LocalPath('/proc').join(str(pid), 'status').read()
    m = re.search('^State:\s+[A-Z] \(([a-z]+)\)$', status, re.MULTILINE)
    return m.group(1)
