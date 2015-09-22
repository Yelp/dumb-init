import os
import re
import signal
import sys
from subprocess import PIPE
from subprocess import Popen

from tests.lib.testing import CATCHABLE_SIGNALS
from tests.lib.testing import pid_tree


def test_prints_signals(both_debug_modes, both_pgroup_modes):
    proc = Popen(
        ('dumb-init', sys.executable, '-m', 'tests.lib.print_signals'),
        stdout=PIPE,
    )

    assert re.match(b'^ready \(pid: (?:[0-9]+)\)\n$', proc.stdout.readline())

    for signum in CATCHABLE_SIGNALS:
        proc.send_signal(signum)
        assert proc.stdout.readline() == '{0}\n'.format(signum).encode('ascii')

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)
