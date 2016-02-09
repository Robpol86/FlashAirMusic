"""Test functions in module."""

import asyncio

import pytest

from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError, FlashAirURLTooLong
from flash_air_music.upload import run
from flash_air_music.upload.discover import Song
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
    songs = [Song(str(tmpdir.join('song.mp3')), str(tmpdir), '/MUSIC', dict())]
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
    def func(*_):
        """Mock function.

        :param _: unused.
        """
        if exc:
            raise exc('Error')
    monkeypatch.setattr(run, 'initialize_upload', lambda *_: None)
    monkeypatch.setattr(run, 'delete_files_dirs', lambda *_: None)
    monkeypatch.setattr(run, 'upload_files', func)

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('song.mp3'))
    songs = [Song(str(tmpdir.join('song.mp3')), str(tmpdir), '/MUSIC', dict())]

    if exc == FlashAirNetworkError:
        with pytest.raises(FlashAirNetworkError):
            run.upload_cleanup('', songs, list(), TZINFO, asyncio.Future())
    else:
        run.upload_cleanup('', songs, list(), TZINFO, asyncio.Future())
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    assert 'Uploading 1 song(s).' in messages
    assert 'Deleting 1 file(s)/dir(s) on the FlashAir card.' not in messages
