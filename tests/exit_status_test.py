import distutils.spawn
import signal
from subprocess import Popen

import pytest


@pytest.mark.parametrize('exit_status', [0, 1, 2, 32, 64, 127, 254, 255])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_exit_status_regular_exit(exit_status):
    """dumb-init should exit with the same exit status as the process that it
    supervises when that process exits normally.
    """
    proc = Popen(('dumb-init', 'sh', '-c', 'exit {0}'.format(exit_status)))
    proc.wait()
    assert proc.returncode == exit_status


@pytest.mark.parametrize('signal', [
    signal.SIGTERM,
    signal.SIGINT,
    signal.SIGQUIT,
    signal.SIGKILL,
])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_exit_status_terminated_by_signal(signal):
    """dumb-init should exit with status 128 + signal when the child process is
    terminated by a signal.
    """
    # We need to make sure not to use the built-in kill (if on Bash):
    # https://github.com/Yelp/dumb-init/issues/115
    proc = Popen(('dumb-init', 'sh', '-c', '{0} -{1} $$'.format(
        distutils.spawn.find_executable('kill'),
        signal,
    )))
    proc.wait()
    assert proc.returncode == 128 + signal
