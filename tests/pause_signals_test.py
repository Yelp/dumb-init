import os
import signal
import time

import pytest

from testing import NORMAL_SIGNALS
from testing import print_signals
from testing import process_state
from testing import signum_and_time_from_stdout

def signum_from_args(args):
    return int(args[1].split(":")[0])

def duration_from_args(args):
    return int(args[1].split(":")[1])

def rewrite_signum_from_args(args):
    return int(args[3].split(":")[1])

@pytest.mark.parametrize("pause_args", [
    ("-p", "15:3"),
    ("-p", "2:3"),
])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_pause_and_proxy_signals(pause_args):
    """Ensure dumb-init can pause on signals before proxying them."""
    signum = signum_from_args(pause_args)
    duration = duration_from_args(pause_args)
    with print_signals(pause_args) as (proc, _):
        start_time = int(time.time())
        proc.send_signal(signum)
        received_signum, end_time = signum_and_time_from_stdout(proc.stdout)   
        assert received_signum == signum
        assert (end_time - start_time) >= duration


@pytest.mark.parametrize("pause_rewrite_args", [
    ("-p", "15:2", "-r", "15:3"),
])
@pytest.mark.usefixtures('both_debug_modes', 'both_setsid_modes')
def test_pause_and_proxy_signals_with_rewrite(pause_rewrite_args):
    """Ensure dumb-init can pause on signals and rewrite them."""
    signum = signum_from_args(pause_rewrite_args)
    duration = duration_from_args(pause_rewrite_args)
    rewrite_signum = rewrite_signum_from_args(pause_rewrite_args)
    with print_signals(pause_rewrite_args) as (proc, _):
        start_time = int(time.time())
        proc.send_signal(signum)
        received_signum, end_time = signum_and_time_from_stdout(proc.stdout)   
        assert received_signum == rewrite_signum
        assert (end_time - start_time) >= duration
    
 
