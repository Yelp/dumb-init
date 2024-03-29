import errno
import os
import re
import signal
import sys
import time
from contextlib import contextmanager
from subprocess import PIPE
from subprocess import Popen

# these signals cause dumb-init to suspend itself
SUSPEND_SIGNALS = frozenset([
    signal.SIGTSTP,
    signal.SIGTTOU,
    signal.SIGTTIN,
])

NORMAL_SIGNALS = frozenset(
    set(range(1, 32)) -
    {signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD} -
    SUSPEND_SIGNALS,
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
    m = re.match(b'^ready \\(pid: ([0-9]+)\\)\n$', line)
    assert m, line

    yield proc, m.group(1).decode('ascii')

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)


def child_pids(pid):
    """Return a list of direct child PIDs for the given PID."""
    children = set()
    for p in os.listdir('/proc'):
        try:
            with open(os.path.join('/proc', p, 'stat')) as f:
                stat = f.read()
            m = re.match(
                r'^\d+ \(.+?\) '
                # This field, state, is normally a single letter, but can be
                # "0" if there are some unusual security settings that prevent
                # reading the process state (happens under GitHub Actions with
                # QEMU for some reason).
                '[0a-zA-Z] '
                r'(\d+) ',
                stat,
            )
            assert m, stat
            ppid = int(m.group(1))
            if ppid == pid:
                children.add(int(p))
        except OSError:
            # Happens when the process exits after listing it, or between
            # opening stat and reading it.
            pass
    return children


def pid_tree(pid):
    """Return a list of all descendant PIDs for the given PID."""
    children = child_pids(pid)
    return {
        pid
        for child in children
        for pid in pid_tree(child)
    } | children


def is_alive(pid):
    """Return whether a process is running with the given PID."""
    return os.path.isdir(os.path.join('/proc', str(pid)))


def process_state(pid):
    """Return a process' state, such as "stopped" or "running"."""
    with open(os.path.join('/proc', str(pid), 'status')) as f:
        status = f.read()
    m = re.search(r'^State:\s+[A-Z] \(([a-z]+)\)$', status, re.MULTILINE)
    return m.group(1)


def sleep_until(fn, timeout=1.5):
    """Sleep until fn succeeds, or we time out."""
    interval = 0.01
    so_far = 0
    while True:
        try:
            fn()
        except Exception:
            if so_far >= timeout:
                raise
        else:
            break
        time.sleep(interval)
        so_far += interval


def kill_if_alive(pid, signum=signal.SIGKILL):
    """Kill a process, ignoring "no such process" errors."""
    try:
        os.kill(pid, signum)
    except OSError as ex:
        if ex.errno != errno.ESRCH:  # No such process
            raise
