import os
from signal import SIGCONT

import pytest

from testing import print_signals
from testing import process_state
from testing import sleep_until
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

            def assert_both_stopped():
                assert process_state(proc.pid) == process_state(pid) == 'stopped'

            sleep_until(assert_both_stopped)

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
