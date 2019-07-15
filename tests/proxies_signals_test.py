import os
import signal
from itertools import chain

import pytest

from testing import NORMAL_SIGNALS
from testing import print_signals
from testing import process_state


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_proxies_signals():
    """Ensure dumb-init proxies regular signals to its child."""
    with print_signals() as (proc, _):
        for signum in NORMAL_SIGNALS:
            proc.send_signal(signum)
            assert proc.stdout.readline() == '{}\n'.format(signum).encode('ascii')


def _rewrite_map_to_args(rewrite_map):
    return chain.from_iterable(
        ('-r', '{}:{}'.format(src, dst)) for src, dst in rewrite_map.items()
    )


@pytest.mark.parametrize(
    'rewrite_map,sequence,expected', [
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
    ],
)
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_proxies_signals_with_rewrite(rewrite_map, sequence, expected):
    """Ensure dumb-init can rewrite signals."""
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        for send, expect_receive in zip(sequence, expected):
            proc.send_signal(send)
            assert proc.stdout.readline() == '{}\n'.format(expect_receive).encode('ascii')


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
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        for send, expect_receive in rewrite_map.items():
            assert process_state(proc.pid) in ['running', 'sleeping']
            proc.send_signal(send)

            assert proc.stdout.readline() == '{}\n'.format(expect_receive).encode('ascii')
            os.waitpid(proc.pid, os.WUNTRACED)
            assert process_state(proc.pid) == 'stopped'

            proc.send_signal(signal.SIGCONT)
            assert proc.stdout.readline() == '{}\n'.format(signal.SIGCONT).encode('ascii')
            assert process_state(proc.pid) in ['running', 'sleeping']


@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_ignored_signals_are_not_proxied():
    """Ensure dumb-init can ignore signals."""
    rewrite_map = {
        signal.SIGTERM: signal.SIGQUIT,
        signal.SIGINT: 0,
        signal.SIGWINCH: 0,
    }
    with print_signals(_rewrite_map_to_args(rewrite_map)) as (proc, _):
        proc.send_signal(signal.SIGTERM)
        proc.send_signal(signal.SIGINT)
        assert proc.stdout.readline() == '{}\n'.format(signal.SIGQUIT).encode('ascii')

        proc.send_signal(signal.SIGWINCH)
        proc.send_signal(signal.SIGHUP)
        assert proc.stdout.readline() == '{}\n'.format(signal.SIGHUP).encode('ascii')
