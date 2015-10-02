from subprocess import PIPE
from subprocess import Popen

import pytest


def test_exit_status(both_debug_modes, both_setsid_modes):
    """dumb-init should say something useful when called with no arguments, and
    exit nonzero.
    """
    proc = Popen(('dumb-init'), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode != 0
    assert stderr == (
        b'Usage: dumb-init [option] program [args]\n'
        b'Try dumb-init --help for full usage.\n'
    )


@pytest.mark.parametrize('flag', ['-h', '--help'])
def test_help_message(flag, both_debug_modes, both_setsid_modes):
    """dumb-init should say something useful when called with the help flag,
    and exit zero.
    """
    proc = Popen(('dumb-init', flag), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode == 0
    assert len(stderr) >= 50


@pytest.mark.parametrize('flag', ['-V', '--version'])
def test_version_message(flag, both_debug_modes, both_setsid_modes):
    """dumb-init should print its version when asked to."""
    version = open('VERSION', 'rb').read()

    proc = Popen(('dumb-init', flag), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode == 0
    assert stderr == b'dumb-init v' + version
