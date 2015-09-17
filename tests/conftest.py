import os

import pytest


@pytest.fixture(params=['1', '0'])
def both_debug_modes(request):
    os.environ['DUMB_INIT_DEBUG'] = request.param


@pytest.fixture(params=['1', '0'])
def both_setsid_modes(request):
    os.environ['DUMB_INIT_SETSID'] = request.param
