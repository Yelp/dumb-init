import os
import re
import signal
import sys
from subprocess import PIPE
from subprocess import Popen

from tests.lib.testing import NORMAL_SIGNALS
from tests.lib.testing import pid_tree


def test_proxies_signals(both_debug_modes, both_setsid_modes):
    """Ensure dumb-init proxies regular signals to its child."""
    proc = Popen(
        ('dumb-init', sys.executable, '-m', 'tests.lib.print_signals'),
        stdout=PIPE,
    )

    assert re.match(b'^ready \(pid: (?:[0-9]+)\)\n$', proc.stdout.readline())

    for signum in NORMAL_SIGNALS:
        proc.send_signal(signum)
        assert proc.stdout.readline() == '{0}\n'.format(signum).encode('ascii')

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)
