"""Configure tests."""

import httpretty
import pytest


@pytest.fixture(autouse=True, scope='session')
def config_httpretty():
    """Configure httpretty global variables."""
    httpretty.HTTPretty.allow_net_connect = False


@pytest.fixture(scope='module')
def tmpdir_module(request, tmpdir_factory):
    """A tmpdir fixture for the module scope. Persists throughout the module.

    :param request: pytest fixture.
    :param tmpdir_factory: pytest fixture.
    """
    return tmpdir_factory.mktemp(request.module.__name__)
