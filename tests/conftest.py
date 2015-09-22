import os

import pytest


@pytest.fixture(params=['1', '0'])
def both_debug_modes(request):
    os.environ['DUMB_INIT_DEBUG'] = request.param


@pytest.fixture
def debug_disabled():
    os.environ['DUMB_INIT_DEBUG'] = '0'


@pytest.fixture(params=['1', '0'])
def both_pgroup_modes(request):
    os.environ['DUMB_INIT_PGROUP'] = request.param


@pytest.fixture
def pgroup_enabled():
    os.environ['DUMB_INIT_PGROUP'] = '1'


@pytest.fixture
def pgroup_disabled():
    os.environ['DUMB_INIT_PGROUP'] = '0'
