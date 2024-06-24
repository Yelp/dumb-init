import os
import shutil
from subprocess import PIPE
from subprocess import run

import pytest


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_working_directories():
    """The child process must start in the working directory in which
    dumb-init was invoked, but dumb-init itself should not keep a
    reference to that."""

    # We need absolute path to dumb-init since we pass cwd=/tmp to get
    # predictable output - so we can't rely on dumb-init being found
    # in the "." directory.
    dumb_init = os.path.realpath(shutil.which('dumb-init'))
    proc = run(
        (
            dumb_init,
            'sh', '-c', 'readlink /proc/$PPID/cwd && readlink /proc/$$/cwd',
        ),
        cwd='/tmp', stdout=PIPE, stderr=PIPE,
    )

    assert proc.returncode == 0
    assert proc.stdout == b'/\n/tmp\n'
