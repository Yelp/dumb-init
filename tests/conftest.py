import os

import pytest


@pytest.fixture(params=['1', '0'])
def both_debug_modes(request):
    os.environ['DUMB_INIT_DEBUG'] = request.param


@pytest.fixture
def debug_disabled():
    os.environ['DUMB_INIT_DEBUG'] = '0'


@pytest.fixture(params=['1', '0'])
def both_setsid_modes(request):
    os.environ['DUMB_INIT_SETSID'] = request.param


@pytest.fixture
def setsid_enabled():
    os.environ['DUMB_INIT_SETSID'] = '1'


@pytest.fixture
def setsid_disabled():
    os.environ['DUMB_INIT_SETSID'] = '0'
