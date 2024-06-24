import signal
import sys
from subprocess import Popen

import pytest


@pytest.mark.parametrize('exit_status', [0, 1, 2, 32, 64, 127, 254, 255])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_exit_status_regular_exit(exit_status):
    """dumb-init should exit with the same exit status as the process that it
    supervises when that process exits normally.
    """
    proc = Popen(('dumb-init', 'sh', '-c', 'exit {}'.format(exit_status)))
    proc.wait()
    assert proc.returncode == exit_status


@pytest.mark.parametrize(
    'signal', [
        signal.SIGTERM,
        signal.SIGHUP,
        signal.SIGQUIT,
        signal.SIGKILL,
    ],
)
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_exit_status_terminated_by_signal(signal):
    """dumb-init should exit with status 128 + signal when the child process is
    terminated by a signal.
    """
    # We use Python because sh is "dash" on Debian and "bash" on others.
    # https://github.com/Yelp/dumb-init/issues/115
    proc = Popen((
        'dumb-init', sys.executable, '-c', 'import os; os.kill(os.getpid(), {})'.format(
            signal,
        ),
    ))
    proc.wait()
    assert proc.returncode == 128 + signal
