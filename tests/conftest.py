"""Configure tests."""

import asyncio

import pytest


@pytest.fixture(scope='module')
def tmpdir_module(request, tmpdir_factory):
    """A tmpdir fixture for the module scope. Persists throughout the module.

    :param request: pytest fixture.
    :param tmpdir_factory: pytest fixture.
    """
    return tmpdir_factory.mktemp(request.module.__name__)


@pytest.fixture(scope='function')
def shutdown_future(monkeypatch):
    """Monkeypatch flash_air_music.lib.SHUTDOWN.

    :param monkeypatch: pytest fixture.
    """
    shutdown = asyncio.Future()
    monkeypatch.setattr('flash_air_music.__main__.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.convert.transcode.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.convert.triggers.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.lib.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.upload.discover.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.upload.interface.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.upload.run.SHUTDOWN', shutdown)
    monkeypatch.setattr('flash_air_music.upload.triggers.SHUTDOWN', shutdown)
    return shutdown
