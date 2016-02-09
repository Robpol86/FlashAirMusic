"""Test functions in module."""

import asyncio
import signal

import pytest

from flash_air_music.__main__ import shutdown
from flash_air_music.convert.triggers import periodically_convert, watch_directory


@asyncio.coroutine
def shutdown_after_string(loop, shutdown_future, caplog, stop_after):
    """Stop loop after `stop_after` is found in log records.

    :param loop: AsyncIO event loop object.
    :param asyncio.Future shutdown_future: Shutdown signal.
    :param caplog: pytest extension fixture.
    :param str stop_after: String to watch for in caplog.records.
    """
    while not any(True for r in caplog.records if r.message == stop_after):
        yield from asyncio.sleep(0.1)
    yield from shutdown(loop, signal.SIGTERM, shutdown_future)


@asyncio.coroutine
def alter_file_system(loop, shutdown_future, caplog, tmpdir):
    """Alter file system during different loop iterations to test watch_directory().

    :param loop: AsyncIO event loop object.
    :param asyncio.Future shutdown_future: Shutdown signal.
    :param caplog: pytest extension fixture.
    :param tmpdir: pytest fixture.
    """
    # Wait for first pass to finish and second pass to skip run().
    while not any(True for r in caplog.records if r.message.startswith('watch_directory() no change in file system')):
        yield from asyncio.sleep(0.1)

    # Alter file system.
    before_count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
    tmpdir.join('song1.mp3').write('\x00')
    while True:
        count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
        if count > before_count:
            break
        yield from asyncio.sleep(0.1)

    # Alter again in subdirectory by adding new file.
    before_count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
    tmpdir.ensure('subdir', 'subdir2', 'subdir3', 'song5.mp3').write('\x00\x00\x00')
    while True:
        count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
        if count > before_count:
            break
        yield from asyncio.sleep(0.1)

    # Alter final time by removing file.
    before_count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
    tmpdir.join('subdir', 'song3.mp3').remove()
    while True:
        count = len([True for r in caplog.records if r.message.startswith('watch_directory() file system changed')])
        if count > before_count:
            break
        yield from asyncio.sleep(0.1)

    # Wait for no change iteration.
    before_count = len([True for r in caplog.records if r.message.startswith('watch_directory() no change in file sy')])
    while True:
        count = len([True for r in caplog.records if r.message.startswith('watch_directory() no change in file sy')])
        if count > before_count:
            break
        yield from asyncio.sleep(0.1)

    # End it.
    yield from shutdown(loop, signal.SIGTERM, shutdown_future)


@pytest.mark.parametrize('mode', ['locked', 'normal'])
def test_periodically_convert(monkeypatch, tmpdir, caplog, mode):
    """Test periodically_convert() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = {
        '--music-source': str(tmpdir.ensure_dir('source')),
        '--threads': '2',
        '--working-dir': str(tmpdir),
    }
    monkeypatch.setattr('flash_air_music.convert.triggers.EVERY_SECONDS_PERIODIC', 1)
    monkeypatch.setattr('flash_air_music.convert.run.GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr('flash_air_music.convert.transcode.GLOBAL_MUTABLE_CONFIG', config)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(0 if mode == 'locked' else 1)
    shutdown_future = asyncio.Future()

    loop.run_until_complete(asyncio.wait([
        shutdown_after_string(loop, shutdown_future, caplog, 'periodically_convert() waking up.'),
        periodically_convert(loop, semaphore, shutdown_future),
    ], timeout=30))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    if mode == 'locked':
        assert 'Semaphore is locked, skipping this iteration.' in messages
        assert 'Waiting for semaphore...' not in messages
    else:
        assert 'Semaphore is locked, skipping this iteration.' not in messages
        assert 'Waiting for semaphore...' in messages


def test_watch_directory(monkeypatch, tmpdir, caplog):
    """Test watch_directory() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    tmpdir.join('song1.mp3').write('\x00\x00\x00\x00\x00')
    tmpdir.join('song2.mp3').write('\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    tmpdir.ensure('subdir', 'song3.mp3').write('\x00\x00')
    tmpdir.ensure('subdir', 'subdir2', 'song4.mp3').write('\x00\x00\x00')

    monkeypatch.setattr('flash_air_music.convert.triggers.EVERY_SECONDS_WATCH', 1)
    monkeypatch.setattr('flash_air_music.convert.triggers.GLOBAL_MUTABLE_CONFIG', {'--music-source': str(tmpdir)})
    monkeypatch.setattr('flash_air_music.convert.run.scan_wait', asyncio.coroutine(lambda: (None, None, None)))
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore()
    shutdown_future = asyncio.Future()

    nested_results = loop.run_until_complete(asyncio.wait([
        alter_file_system(loop, shutdown_future, caplog, tmpdir),
        watch_directory(loop, semaphore, shutdown_future),
    ], timeout=30))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    for result in (b for a in nested_results for b in a):
        result.result()  # Will raise exception if there's a bug.
        assert not result.exception()
    assert messages.count('watch_directory() file system changed, calling run().') == 4
    assert messages.count('watch_directory() no change in file system, not calling run().') >= 2
