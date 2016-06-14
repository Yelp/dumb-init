import os
import re
import signal
import sys
from contextlib import contextmanager
from itertools import chain
from subprocess import PIPE
from subprocess import Popen

import pytest

from tests.lib.testing import NORMAL_SIGNALS
from tests.lib.testing import pid_tree
from tests.lib.testing import process_state


@contextmanager
def _print_signals(args=()):
    """Start print_signals and return dumb-init process."""
    proc = Popen(
        (
            ('dumb-init',) +
            tuple(args) +
            (sys.executable, '-m', 'tests.lib.print_signals')
        ),
        stdout=PIPE,
    )
    assert re.match(b'^ready \(pid: (?:[0-9]+)\)\n$', proc.stdout.readline())

    yield proc

    for pid in pid_tree(proc.pid):
        os.kill(pid, signal.SIGKILL)


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_proxies_signals():
    """Ensure dumb-init proxies regular signals to its child."""
    with _print_signals() as proc:
        for signum in NORMAL_SIGNALS:
            proc.send_signal(signum)
            assert proc.stdout.readline() == '{0}\n'.format(signum).encode('ascii')


def _rewrite_map_to_args(rewrite_map):
    return chain.from_iterable(
        ('-r', '{0}:{1}'.format(src, dst)) for src, dst in rewrite_map.items()
    )


@pytest.mark.parametrize('rewrite_map,sequence,expected', [
    (
        {},
        [signal.SIGTERM, signal.SIGQUIT, signal.SIGCONT, signal.SIGINT],
        [signal.SIGTERM, signal.SIGQUIT, signal.SIGCONT, signal.SIGINT],
    ),

    (
        {signal.SIGTERM: signal.SIGINT},
        [signal.SIGTERM, signal.SIGQUIT, signal.SIGCONT, signal.SIGINT],
        [signal.SIGINT, signal.SIGQUIT, signal.SIGCONT, signal.SIGINT],
    ),

    (
        {
            signal.SIGTERM: signal.SIGINT,
            signal.SIGINT: signal.SIGTERM,
            signal.SIGQUIT: signal.SIGQUIT,
        },
        [signal.SIGTERM, signal.SIGQUIT, signal.SIGCONT, signal.SIGINT],
        [signal.SIGINT, signal.SIGQUIT, signal.SIGCONT, signal.SIGTERM],
    ),

    # Lowest possible and highest possible signals.
    (
        {1: 31, 31: 1},
        [1, 31],
        [31, 1],
    ),
])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_proxies_signals_with_rewrite(rewrite_map, sequence, expected):
    """Ensure dumb-init can rewrite signals."""
    with _print_signals(_rewrite_map_to_args(rewrite_map)) as proc:
        for send, expect_receive in zip(sequence, expected):
            proc.send_signal(send)
            assert proc.stdout.readline() == '{0}\n'.format(expect_receive).encode('ascii')


@pytest.mark.usefixtures('both_debug_modes', 'setsid_enabled')
def test_default_rewrites_can_be_overriden_with_setsid_enabled():
    """In setsid mode, dumb-init should allow overwriting the default
    rewrites (but still suspend itself).
    """
    rewrite_map = {
        signal.SIGTTIN: signal.SIGTERM,
        signal.SIGTTOU: signal.SIGINT,
        signal.SIGTSTP: signal.SIGHUP,
    }
    with _print_signals(_rewrite_map_to_args(rewrite_map)) as proc:
        for send, expect_receive in rewrite_map.items():
            assert process_state(proc.pid) in ['running', 'sleeping']
            proc.send_signal(send)

            assert proc.stdout.readline() == '{0}\n'.format(expect_receive).encode('ascii')
            os.waitpid(proc.pid, os.WUNTRACED)
            assert process_state(proc.pid) == 'stopped'

            proc.send_signal(signal.SIGCONT)
            assert proc.stdout.readline() == '{0}\n'.format(signal.SIGCONT).encode('ascii')
            assert process_state(proc.pid) in ['running', 'sleeping']
