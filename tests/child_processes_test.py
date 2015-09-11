import os
import signal
import time
from subprocess import Popen

from tests.lib.testing import is_alive
from tests.lib.testing import pid_tree


def spawn_and_kill_pipeline():
    proc = Popen((
        'dumb-init',
        'sh', '-c',
        "yes 'oh, hi' | tail & yes error | tail >&2"
    ))
    time.sleep(0.1)

    pids = pid_tree(os.getpid())
    assert len(living_pids(pids)) == 6

    proc.send_signal(signal.SIGTERM)
    proc.wait()

    time.sleep(0.1)
    return pids


def living_pids(pids):
    return {pid for pid in pids if is_alive(pid)}


def test_setsid_signals_entire_group(both_debug_modes):
    """When dumb-init is running in setsid mode, it should only signal the
    entire process group rooted at it.
    """
    os.environ['DUMB_INIT_SETSID'] = '1'
    pids = spawn_and_kill_pipeline()
    assert len(living_pids(pids)) == 0


def test_no_setsid_doesnt_signal_entire_group(both_debug_modes):
    """When dumb-init is not running in setsid mode, it should only signal its
    immediate child.
    """
    os.environ['DUMB_INIT_SETSID'] = '0'
    pids = spawn_and_kill_pipeline()

    living = living_pids(pids)
    assert len(living) == 4
    for pid in living:
        os.kill(pid, signal.SIGKILL)
