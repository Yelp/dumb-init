import signal

from py._path.local import LocalPath


CATCHABLE_SIGNALS = frozenset(
    set(range(1, 32)) - set([signal.SIGKILL, signal.SIGSTOP, signal.SIGCHLD])
)


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
