import os
import re
import sys
import time
from signal import SIGCONT
from signal import SIGKILL
from subprocess import PIPE
from subprocess import Popen

from tests.lib.testing import pid_tree
from tests.lib.testing import process_state
from tests.lib.testing import SUSPEND_SIGNALS


def test_shell_background_support_setsid(both_debug_modes, setsid_enabled):
    """In setsid mode, dumb-init should suspend itself and its children when it
    receives SIGTSTP, SIGTTOU, or SIGTTIN.
    """
    proc = Popen(
        ('dumb-init', sys.executable, '-m', 'tests.lib.print_signals'),
        stdout=PIPE,
    )
    match = re.match(b'^ready \(pid: ([0-9]+)\)\n$', proc.stdout.readline())
    pid = match.group(1).decode('ascii')

    for signum in SUSPEND_SIGNALS:
        # both dumb-init and print_signals should be running or sleeping
        assert process_state(pid) in ['running', 'sleeping']
        assert process_state(proc.pid) in ['running', 'sleeping']

        # both should now suspend
        proc.send_signal(signum)

        for _ in range(1000):
            time.sleep(0.001)
            try:
                assert process_state(proc.pid) == 'stopped'
                assert process_state(pid) == 'stopped'
            except AssertionError:
                pass
            else:
                break
        else:
            raise RuntimeError('Timed out waiting for processes to stop.')

        # and then both wake up again
        proc.send_signal(SIGCONT)
        assert (
            proc.stdout.readline() == '{0}\n'.format(SIGCONT).encode('ascii')
        )
        assert process_state(pid) in ['running', 'sleeping']
        assert process_state(proc.pid) in ['running', 'sleeping']

    for pid in pid_tree(proc.pid):
        os.kill(pid, SIGKILL)


def test_shell_background_support_without_setsid(both_debug_modes, setsid_disabled):
    """In non-setsid mode, dumb-init should forward the signals SIGTSTP,
    SIGTTOU, and SIGTTIN, and then suspend itself.
    """
    proc = Popen(
        ('dumb-init', sys.executable, '-m', 'tests.lib.print_signals'),
        stdout=PIPE,
    )

    assert re.match(b'^ready \(pid: (?:[0-9]+)\)\n$', proc.stdout.readline())

    for signum in SUSPEND_SIGNALS:
        assert process_state(proc.pid) in ['running', 'sleeping']
        proc.send_signal(signum)
        assert proc.stdout.readline() == '{0}\n'.format(signum).encode('ascii')
        os.waitpid(proc.pid, os.WUNTRACED)
        assert process_state(proc.pid) == 'stopped'

        proc.send_signal(SIGCONT)
        assert (
            proc.stdout.readline() == '{0}\n'.format(SIGCONT).encode('ascii')
        )
        assert process_state(proc.pid) in ['running', 'sleeping']

    for pid in pid_tree(proc.pid):
        os.kill(pid, SIGKILL)
