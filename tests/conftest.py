import os
from unittest import mock

import pytest


@pytest.fixture(autouse=True, scope='function')
def clean_environment():
    """Ensure all tests start with a clean environment.

    Even if tests properly clean up after themselves, we still need this in
    case the user runs tests with an already-polluted environment.
    """
    with mock.patch.dict(
        os.environ,
        {'DUMB_INIT_DEBUG': '', 'DUMB_INIT_SETSID': ''},
    ):
        yield


@pytest.fixture(params=['1', '0'])
def both_debug_modes(request):
    with mock.patch.dict(os.environ, {'DUMB_INIT_DEBUG': request.param}):
        yield


@pytest.fixture
def debug_disabled():
    with mock.patch.dict(os.environ, {'DUMB_INIT_DEBUG': '0'}):
        yield


@pytest.fixture(params=['1', '0'])
def both_setsid_modes(request):
    with mock.patch.dict(os.environ, {'DUMB_INIT_SETSID': request.param}):
        yield


@pytest.fixture
def setsid_enabled():
    with mock.patch.dict(os.environ, {'DUMB_INIT_SETSID': '1'}):
        yield


@pytest.fixture
def setsid_disabled():
    with mock.patch.dict(os.environ, {'DUMB_INIT_SETSID': '0'}):
        yield
