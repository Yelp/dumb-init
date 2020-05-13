"""Sanity checks for command-line options."""
import re
import signal
from subprocess import PIPE
from subprocess import Popen

import pytest


@pytest.fixture
def current_version():
    return open('VERSION').read().strip()


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_no_arguments_prints_usage():
    proc = Popen(('dumb-init'), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode != 0
    assert stderr == (
        b'Usage: dumb-init [option] program [args]\n'
        b'Try dumb-init --help for full usage.\n'
    )


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_exits_invalid_with_invalid_args():
    proc = Popen(('dumb-init', '--yolo', '/bin/true'), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode == 1
    assert stderr in (
        b"dumb-init: unrecognized option '--yolo'\n",  # glibc
        b'dumb-init: unrecognized option: yolo\n',  # musl
    )


@pytest.mark.parametrize('flag', ['-h', '--help'])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_help_message(flag, current_version):
    """dumb-init should say something useful when called with the help flag,
    and exit zero.
    """
    proc = Popen(('dumb-init', flag), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode == 0
    assert stderr == (
        b'dumb-init v' + current_version.encode('ascii') + b'\n'
        b'Usage: dumb-init [option] command [[arg] ...]\n'
        b'\n'
        b'dumb-init is a simple process supervisor that forwards signals to children.\n'
        b'It is designed to run as PID1 in minimal container environments.\n'
        b'\n'
        b'Optional arguments:\n'
        b'   -c, --single-child   Run in single-child mode.\n'
        b'                        In this mode, signals are only proxied to the\n'
        b'                        direct child and not any of its descendants.\n'
        b'   -r, --rewrite s:r    Rewrite received signal s to new signal r before proxying.\n'
        b'                        Signals may be specified as numbers or names like USR1 or\n'
        b'                        SIGINT (see -l/--list). To ignore (not proxy) a signal,\n'
        b'                        rewrite it to 0. This option can be specified multiple\n'
        b'                        times.\n'
        b'   -l, --list           Print signal number to name mapping and exit.\n'
        b'   -v, --verbose        Print debugging information to stderr.\n'
        b'   -h, --help           Print this help message and exit.\n'
        b'   -V, --version        Print the current version and exit.\n'
        b'\n'
        b'Full help is available online at https://github.com/Yelp/dumb-init\n'
    )


@pytest.mark.parametrize('flag', ['-V', '--version'])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_version_message(flag, current_version):
    """dumb-init should print its version when asked to."""

    proc = Popen(('dumb-init', flag), stderr=PIPE)
    _, stderr = proc.communicate()
    assert proc.returncode == 0
    assert stderr == b'dumb-init v' + current_version.encode('ascii') + b'\n'


@pytest.mark.parametrize('flag', ['-v', '--verbose'])
def test_verbose(flag):
    """dumb-init should print debug output when asked to."""
    proc = Popen(('dumb-init', flag, 'echo', 'oh,', 'hi'), stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0
    assert stdout == b'oh, hi\n'

    # child/parent race to print output after the fork(), can't guarantee exact order
    assert re.search(b'(^|\n)\\[dumb-init\\] setsid complete\\.\n', stderr), stderr  # child
    assert re.search(  # parent
        (
            '(^|\n)\\[dumb-init\\] Child spawned with PID [0-9]+\\.\n'
            '.*'  # child might print here
            '\\[dumb-init\\] Received signal {signal.SIGCHLD} \\(CHLD\\)\\.\n'
            '\\[dumb-init\\] A child with PID [0-9]+ exited with exit status 0.\n'
            '\\[dumb-init\\] Forwarded signal 15 \\(TERM\\) to children\\.\n'
            '\\[dumb-init\\] Child exited with status 0\\. Goodbye\\.\n$'
        ).format(signal=signal).encode('utf8'),
        stderr,
        re.DOTALL,
    ), stderr


@pytest.mark.parametrize('flag1', ['-v', '--verbose'])
@pytest.mark.parametrize('flag2', ['-c', '--single-child'])
def test_verbose_and_single_child(flag1, flag2):
    """dumb-init should print debug output when asked to."""
    proc = Popen(('dumb-init', flag1, flag2, 'echo', 'oh,', 'hi'), stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0
    assert stdout == b'oh, hi\n'
    assert re.match(
        (
            '^\\[dumb-init\\] Child spawned with PID [0-9]+\\.\n'
            '\\[dumb-init\\] Received signal {signal.SIGCHLD} \\(CHLD\\)\\.\n'
            '\\[dumb-init\\] A child with PID [0-9]+ exited with exit status 0.\n'
            '\\[dumb-init\\] Forwarded signal 15 \\(TERM\\) to children\\.\n'
            '\\[dumb-init\\] Child exited with status 0\\. Goodbye\\.\n$'
        ).format(signal=signal).encode('utf8'),
        stderr,
    )


@pytest.mark.parametrize(
    'extra_args', [
        ('-r',),
        ('-r', ''),
        ('-r', 'herp'),
        ('-r', 'herp:derp'),
        ('-r', '15'),
        ('-r', '15::12'),
        ('-r', '15:derp'),
        ('-r', '15:SIGBAR'),
        ('-r', 'TERM:SIGBAR'),
        ('-r', 'FOO:12'),
        ('-r', '15:12', '-r'),
        ('-r', '15:12', '-r', '0'),
        ('-r', '15:12', '-r', '1:32'),
    ],
)
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_rewrite_errors(extra_args):
    proc = Popen(
        ('dumb-init',) + extra_args + ('echo', 'oh,', 'hi'),
        stdout=PIPE, stderr=PIPE,
    )
    stdout, stderr = proc.communicate()
    assert proc.returncode == 1
    assert stderr == (
        b'Usage: -r option takes <signum>:<signum>, where <signum> '
        b'is between 1 and 31, specified by number or name.\n'
        b'This option can be specified multiple times.\n'
        b'Use --help for full usage.\n'
    )
