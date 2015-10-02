import os
import re
import signal
import sys
import time
from subprocess import PIPE
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
    return set(pid for pid in pids if is_alive(pid))


def test_setsid_signals_entire_group(both_debug_modes, setsid_enabled):
    """When dumb-init is running in setsid mode, it should only signal the
    entire process group rooted at it.
    """
    pids = spawn_and_kill_pipeline()
    assert len(living_pids(pids)) == 0


def test_no_setsid_doesnt_signal_entire_group(
        both_debug_modes,
        setsid_disabled,
):
    """When dumb-init is not running in setsid mode, it should only signal its
    immediate child.
    """
    pids = spawn_and_kill_pipeline()

    living = living_pids(pids)
    assert len(living) == 4
    for pid in living:
        os.kill(pid, signal.SIGKILL)


def spawn_process_which_dies_with_children():
    """Spawn a process which spawns some children and then dies without
    signaling them, wrapped in dumb-init.

    Returns a tuple (child pid, child stdout pipe), where the child is
    print_signals. This is useful because you can signal the PID and see if
    anything gets printed onto the stdout pipe.
    """
    proc = Popen(
        (
            'dumb-init',
            'sh', '-c',

            # we need to sleep before the shell exits, or dumb-init might send
            # TERM to print_signals before it has had time to register custom
            # signal handlers
            '{python} -m tests.lib.print_signals & sleep 0.1'.format(
                python=sys.executable,
            ),
        ),
        stdout=PIPE,
    )
    proc.wait()
    assert proc.returncode == 0

    # read a line from print_signals, figure out its pid
    line = proc.stdout.readline()
    match = re.match(b'ready \(pid: ([0-9]+)\)\n', line)
    assert match, 'print_signals should print "ready" and its pid, not ' + \
        str(line)
    child_pid = int(match.group(1))

    # at this point, the shell and dumb-init have both exited, but
    # print_signals may or may not still be running (depending on whether
    # setsid mode is enabled)

    return child_pid, proc.stdout


def test_all_processes_receive_term_on_exit_if_setsid(
        both_debug_modes,
        setsid_enabled,
):
    """If the child exits for some reason, dumb-init should send TERM to all
    processes in its session if setsid mode is enabled."""
    child_pid, child_stdout = spawn_process_which_dies_with_children()

    # print_signals should have received TERM
    assert child_stdout.readline() == b'15\n'

    os.kill(child_pid, signal.SIGKILL)


def test_processes_dont_receive_term_on_exit_if_no_setsid(
        both_debug_modes,
        setsid_disabled,
):
    """If the child exits for some reason, dumb-init should not send TERM to
    any other processes if setsid mode is disabled."""
    child_pid, child_stdout = spawn_process_which_dies_with_children()

    # print_signals should not have received TERM; to test this, we send it
    # some other signals and ensure they were received (and TERM wasn't)
    for signum in [1, 2, 3]:
        os.kill(child_pid, signum)
        assert child_stdout.readline() == str(signum).encode('ascii') + b'\n'

    os.kill(child_pid, signal.SIGKILL)


def test_fails_nonzero_with_bad_exec(both_debug_modes, both_setsid_modes):
    """If dumb-init can't exec as requested, it should exit nonzero."""
    proc = Popen(('dumb-init', '/doesnotexist'), stderr=PIPE)
    proc.wait()
    assert proc.returncode != 0
    assert (
        b'[dumb-init] /doesnotexist: No such file or directory\n'
        in proc.stderr
    )
