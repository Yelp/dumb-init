import os

import pytest

from testing import print_signals


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_execs_observers():
    """Ensure dumb-init executes observers."""
    with print_signals(('-r', '10:0:/bin/pwd', '-r', '12:12:pwd',)) as (proc, _):
        proc.send_signal(10)
        assert proc.stdout.readline() == '{}\n'.format(os.getcwd()).encode('ascii')
        proc.send_signal(12)
        assert (proc.stdout.readline() + proc.stdout.readline()) in (
            '12\n{}\n'.format(os.getcwd()).encode('ascii'),
            '{}\n12\n'.format(os.getcwd()).encode('ascii'),
        )
