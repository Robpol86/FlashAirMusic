"""Test functions in module."""

import asyncio

import pytest

from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError, FlashAirURLTooLong
from flash_air_music.upload import run
from flash_air_music.upload.discover import Song
from flash_air_music.upload.interface import epoch_to_ftime
from tests import HERE, TZINFO


@pytest.mark.parametrize('exc', [FlashAirNetworkError, FlashAirError, None])
def test_scan(monkeypatch, exc):
    """Test scan().

    :param monkeypatch: pytest fixture.
    :param exception exc: Exception to test for.
    """
    def func(_):
        """Mock function.

        :param _: unused.
        """
        if exc:
            raise exc('Error')
        return TZINFO
    monkeypatch.setattr(run, 'GLOBAL_MUTABLE_CONFIG', {'--music-source': ''})
    monkeypatch.setattr(run, 'get_card_time_zone', func)
    monkeypatch.setattr(run, 'get_songs', lambda *_: ([1, 2, 3], None, None, None))
    monkeypatch.setattr(run, 'files_dirs_to_delete', lambda *_: {4, 5, 6})

    if exc != FlashAirNetworkError:
        actual = run.scan('', asyncio.Future())
        expected = (list(), set(), None) if exc == FlashAirError else ([1, 2, 3], {4, 5, 6}, TZINFO)
        assert actual == expected
        return

    with pytest.raises(FlashAirNetworkError):
        run.scan('', asyncio.Future())


@pytest.mark.parametrize('exc', [FlashAirURLTooLong, FlashAirNetworkError, FlashAirError, None])
def test_upload_cleanup_initialize_upload(monkeypatch, tmpdir, caplog, exc):
    """Test upload_cleanup() with initialize_upload() exception handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param exception exc: Exception to test for.
    """
    def func(*_):
        """Mock function.

        :param _: unused.
        """
        if exc:
            raise exc('Error')
    monkeypatch.setattr(run, 'initialize_upload', func)
    monkeypatch.setattr(run, 'delete_files_dirs', lambda *_: None)
    monkeypatch.setattr(run, 'upload_files', lambda *_: None)

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('song.mp3'))
    songs = [Song(str(tmpdir.join('song.mp3')), str(tmpdir), '/MUSIC', dict(), TZINFO)]
    delete_paths = ['/MUSIC/empty']

    if exc == FlashAirNetworkError:
        with pytest.raises(FlashAirNetworkError):
            run.upload_cleanup('', songs, delete_paths, TZINFO, asyncio.Future())
    else:
        run.upload_cleanup('', songs, delete_paths, TZINFO, asyncio.Future())
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    if exc:
        assert 'Deleting 1 file(s)/dir(s) on the FlashAir card.' not in messages
        assert 'Uploading 1 song(s).' not in messages
        if exc == FlashAirURLTooLong:
            assert messages[-1] == 'Lua script path is too long for some reason???'
        elif exc == FlashAirNetworkError:
            assert messages[-1] == 'Preparing FlashAir card for changes.'
        elif exc == FlashAirError:
            assert messages[-1] == 'Unexpected exception.'
    else:
        assert 'Deleting 1 file(s)/dir(s) on the FlashAir card.' in messages
        assert 'Uploading 1 song(s).' in messages


@pytest.mark.parametrize('exc', [FlashAirNetworkError, FlashAirError, None])
def test_upload_cleanup_delete_files_dirs(monkeypatch, caplog, exc):
    """Test upload_cleanup() with delete_files_dirs() exception handling.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    :param exception exc: Exception to test for.
    """
    def func(*_):
        """Mock function.

        :param _: unused.
        """
        if exc:
            raise exc('Error')
    monkeypatch.setattr(run, 'initialize_upload', lambda *_: None)
    monkeypatch.setattr(run, 'delete_files_dirs', func)
    monkeypatch.setattr(run, 'upload_files', lambda *_: None)

    delete_paths = ['/MUSIC/empty']

    if exc == FlashAirNetworkError:
        with pytest.raises(FlashAirNetworkError):
            run.upload_cleanup('', list(), delete_paths, TZINFO, asyncio.Future())
    else:
        run.upload_cleanup('', list(), delete_paths, TZINFO, asyncio.Future())
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    assert 'Uploading 1 song(s).' not in messages
    assert 'Deleting 1 file(s)/dir(s) on the FlashAir card.' in messages


@pytest.mark.parametrize('exc', [FlashAirNetworkError, FlashAirError, None])
def test_upload_cleanup_upload_files(monkeypatch, tmpdir, caplog, exc):
    """Test upload_cleanup() with upload_files() exception handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param exception exc: Exception to test for.
    """
    attrs = list()

    def func(*args):
        """Mock function.

        :param list args: Arguments given by caller.
        """
        if exc:
            raise exc('Error')
        attrs.extend(args[1])
    monkeypatch.setattr(run, 'initialize_upload', lambda *_: None)
    monkeypatch.setattr(run, 'delete_files_dirs', lambda *_: None)
    monkeypatch.setattr(run, 'upload_files', func)

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('song.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('bigger.mp3'))
    tmpdir.join('bigger.mp3').write(b'\x00' * 1024, mode='ab')
    songs = [
        Song(str(tmpdir.join('song.mp3')), str(tmpdir), '/MUSIC', dict(), TZINFO),
        Song(str(tmpdir.join('bigger.mp3')), str(tmpdir), '/MUSIC', dict(), TZINFO),
    ]
    assert songs[0].live_metadata['source_size'] < songs[1].live_metadata['source_size']

    if exc == FlashAirNetworkError:
        with pytest.raises(FlashAirNetworkError):
            run.upload_cleanup('', songs, list(), TZINFO, asyncio.Future())
    else:
        run.upload_cleanup('', songs, list(), TZINFO, asyncio.Future())
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    assert 'Uploading 2 song(s).' in messages
    assert 'Deleting 1 file(s)/dir(s) on the FlashAir card.' not in messages

    if exc:
        expected = list()
    else:
        expected = [
            (songs[0].source, songs[0].target, epoch_to_ftime(songs[0].live_metadata['source_mtime'], TZINFO)),
            (songs[1].source, songs[1].target, epoch_to_ftime(songs[1].live_metadata['source_mtime'], TZINFO)),
        ]
    assert attrs == expected


@pytest.mark.parametrize('mode', ['shutdown', 'nothing to do', 'success'])
def test_run_quick(monkeypatch, caplog, mode):
    """Test run() without needing to iterate.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    monkeypatch.setattr(run, 'scan', lambda *_: (list(), [] if mode == 'nothing to do' else ['/MUSIC/empty'], None))
    monkeypatch.setattr(run, 'upload_cleanup', lambda *_: None)

    shutdown_future = asyncio.Future()
    if mode == 'shutdown':
        shutdown_future.set_result(True)

    # Run.
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(run.run(asyncio.Semaphore(), '', shutdown_future))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    if mode == 'shutdown':
        expected = [
            'Waiting for semaphore...',
            'Got semaphore lock.',
            'Service shutdown initiated, stop trying to update FlashAir card.',
            'Released lock.',
            'Failed to fully update FlashAir card. Maybe next time.',
        ]
        assert not success
    elif mode == 'nothing to do':
        expected = [
            'Waiting for semaphore...',
            'Got semaphore lock.',
            'Released lock.',
            'No changes detected on FlashAir card.',
        ]
        assert success
    else:
        expected = [
            'Waiting for semaphore...',
            'Got semaphore lock.',
            'Released lock.',
            'Done updating FlashAir card.',
        ]
        assert success
    assert messages == expected


@pytest.mark.parametrize('mode', ['delay', 'timeout'])
def test_run_slow(monkeypatch, caplog, mode):
    """Test run() with multiple iterations.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    def func(*_):
        """Mock function.

        :param _: Unused.
        """
        if mode == 'timeout' or not hasattr(func, 'already_ran'):
            setattr(func, 'already_ran', True)
            raise FlashAirNetworkError('Error')
    monkeypatch.setattr(run, 'GIVE_UP_AFTER', 5)
    monkeypatch.setattr(run, 'scan', lambda *_: (list(), ['/MUSIC/empty'], None))
    monkeypatch.setattr(run, 'upload_cleanup', func)

    # Run.
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(run.run(asyncio.Semaphore(), '', asyncio.Future()))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    if mode == 'timeout':
        assert messages[-1] == 'Failed to fully update FlashAir card. Maybe next time.'
        assert not success
    else:
        assert messages[-1] == 'Done updating FlashAir card.'
        assert success
