from subprocess import PIPE
from subprocess import Popen


def test_exit_status(both_debug_modes, both_pgroup_modes):
    """dumb-init should say something useful when called with no arguments, and
    exit nonzero.
    """
    proc = Popen(('dumb-init'), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode != 0
    assert len(stderr) >= 50
