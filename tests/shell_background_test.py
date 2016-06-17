import os
import time
from signal import SIGCONT

import pytest

from testing import print_signals
from testing import process_state
from testing import SUSPEND_SIGNALS


@pytest.mark.usefixtures('both_debug_modes', 'setsid_enabled')
def test_shell_background_support_setsid():
    """In setsid mode, dumb-init should suspend itself and its children when it
    receives SIGTSTP, SIGTTOU, or SIGTTIN.
    """
    with print_signals() as (proc, pid):
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


@pytest.mark.usefixtures('both_debug_modes', 'setsid_disabled')
def test_shell_background_support_without_setsid():
    """In non-setsid mode, dumb-init should forward the signals SIGTSTP,
    SIGTTOU, and SIGTTIN, and then suspend itself.
    """
    with print_signals() as (proc, _):
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
