"""Test functions in module."""

import asyncio
import signal

import pytest

from flash_air_music.__main__ import shutdown
from flash_air_music.convert.periodicals import periodically_convert


@asyncio.coroutine
def shutdown_after_string(loop, shutdown_future, caplog, stop_after):
    """Stop loop after `stop_after` is found in log records.

    :param loop: AsyncIO event loop object.
    :param asyncio.Future shutdown_future: Shutdown signal.
    :param caplog: pytest extension fixture.
    :param str stop_after: String to watch for in caplog.records.
    """
    while not any(True for r in caplog.records if r.message == stop_after):
        yield from asyncio.sleep(0.1, loop=loop)
    yield from shutdown(signal.SIGTERM, shutdown_future)


@pytest.mark.parametrize('mode', ['locked', 'normal'])
def test_periodically_convert(monkeypatch, tmpdir, caplog, mode):
    """Test periodically_convert() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = {
        '--music-source': str(tmpdir.join('source').ensure_dir()),
        '--threads': '2',
        '--working-dir': str(tmpdir),
    }
    monkeypatch.setattr('flash_air_music.convert.run.GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr('flash_air_music.convert.transcode.GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr('flash_air_music.convert.periodicals.EVERY_SECONDS_PERIODIC', 1)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(0 if mode == 'locked' else 1, loop=loop)
    shutdown_future = asyncio.Future()

    loop.run_until_complete(asyncio.wait([
        shutdown_after_string(loop, shutdown_future, caplog, 'periodically_convert() waking up.'),
        periodically_convert(loop, semaphore, shutdown_future),
    ]))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    if mode == 'locked':
        assert 'Semaphore is locked, skipping this iteration.' in messages
        assert 'Waiting for semaphore...' not in messages
    else:
        assert 'Semaphore is locked, skipping this iteration.' not in messages
        assert 'Waiting for semaphore...' in messages
