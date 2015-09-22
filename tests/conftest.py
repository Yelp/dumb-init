import os

import pytest


@pytest.fixture(autouse=True, scope='function')
def clean_environment():
    """Ensure tests don't pollute each others' environment variables."""
    os.environ.pop('DUMB_INIT_DEBUG', None)
    os.environ.pop('DUMB_INIT_SETSID', None)


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
