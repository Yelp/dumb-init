import os
import re
import signal
import sys
from subprocess import PIPE
from subprocess import Popen

import pytest

from testing import is_alive
from testing import kill_if_alive
from testing import pid_tree
from testing import sleep_until


def spawn_and_kill_pipeline():
    proc = Popen((
        'dumb-init',
        'sh', '-c',
        "yes 'oh, hi' | tail & yes error | tail >&2",
    ))

    def assert_living_pids():
        assert len(living_pids(pid_tree(os.getpid()))) == 6

    sleep_until(assert_living_pids)

    pids = pid_tree(os.getpid())
    proc.send_signal(signal.SIGTERM)
    proc.wait()
    return pids


def living_pids(pids):
    return {pid for pid in pids if is_alive(pid)}


@pytest.mark.usefixtures('both_debug_modes', 'setsid_enabled')
def test_setsid_signals_entire_group():
    """When dumb-init is running in setsid mode, it should signal the entire
    process group rooted at it.
    """
    pids = spawn_and_kill_pipeline()

    def assert_no_living_pids():
        assert len(living_pids(pids)) == 0

    sleep_until(assert_no_living_pids)


@pytest.mark.usefixtures('both_debug_modes', 'setsid_disabled')
def test_no_setsid_doesnt_signal_entire_group():
    """When dumb-init is not running in setsid mode, it should only signal its
    immediate child.
    """
    pids = spawn_and_kill_pipeline()

    def assert_four_living_pids():
        assert len(living_pids(pids)) == 4

    sleep_until(assert_four_living_pids)

    for pid in living_pids(pids):
        kill_if_alive(pid)


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
            '{python} -m testing.print_signals & sleep 1'.format(
                python=sys.executable,
            ),
        ),
        stdout=PIPE,
    )
    proc.wait()
    assert proc.returncode == 0

    # read a line from print_signals, figure out its pid
    line = proc.stdout.readline()
    match = re.match(b'ready \\(pid: ([0-9]+)\\)\n', line)
    assert match, line
    child_pid = int(match.group(1))

    # at this point, the shell and dumb-init have both exited, but
    # print_signals may or may not still be running (depending on whether
    # setsid mode is enabled)

    return child_pid, proc.stdout


@pytest.mark.usefixtures('both_debug_modes', 'setsid_enabled')
def test_all_processes_receive_term_on_exit_if_setsid():
    """If the child exits for some reason, dumb-init should send TERM to all
    processes in its session if setsid mode is enabled."""
    child_pid, child_stdout = spawn_process_which_dies_with_children()

    # print_signals should have received TERM
    assert child_stdout.readline() == b'15\n'

    os.kill(child_pid, signal.SIGKILL)


@pytest.mark.usefixtures('both_debug_modes', 'setsid_disabled')
def test_processes_dont_receive_term_on_exit_if_no_setsid():
    """If the child exits for some reason, dumb-init should not send TERM to
    any other processes if setsid mode is disabled."""
    child_pid, child_stdout = spawn_process_which_dies_with_children()

    # print_signals should not have received TERM; to test this, we send it
    # some other signals and ensure they were received (and TERM wasn't)
    for signum in [1, 2, 3]:
        os.kill(child_pid, signum)
        assert child_stdout.readline() == str(signum).encode('ascii') + b'\n'

    os.kill(child_pid, signal.SIGKILL)


@pytest.mark.parametrize(
    'args', [
        ('/doesnotexist',),
        ('--', '/doesnotexist'),
        ('-c', '/doesnotexist'),
        ('--single-child', '--', '/doesnotexist'),
    ],
)
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_fails_nonzero_with_bad_exec(args):
    """If dumb-init can't exec as requested, it should exit nonzero."""
    proc = Popen(('dumb-init',) + args, stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode != 0
    assert (
        b'[dumb-init] /doesnotexist: No such file or directory\n'
        in stderr
    )
