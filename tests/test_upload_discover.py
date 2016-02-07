"""Test functions in module."""

import asyncio

import pytest

from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError, FlashAirURLTooLong
from flash_air_music.upload import discover
from tests import HERE, TZINFO


@pytest.mark.parametrize('mode', ['no target', 'tt', 'ts', 'up to date'])
def test_song(tmpdir, mode):
    """Test Song class metadata handling.

    :param tmpdir: pytest fixture.
    :param str mode: Scenario to test for.
    """
    source_file = tmpdir.ensure_dir('source').join('song.mp3')
    HERE.join('1khz_sine.mp3').copy(source_file)

    # Write metadata.
    remote_metadata = dict()
    if mode != 'no target':
        remote_metadata['/MUSIC/song.mp3'] = [source_file.stat().size, source_file.stat().mtime]
    if mode == 'ts':
        remote_metadata['/MUSIC/song.mp3'][0] -= 20
    elif mode == 'tt':
        remote_metadata['/MUSIC/song.mp3'][1] -= 20

    # Run.
    song = discover.Song(str(source_file), source_file.dirname, '/MUSIC', remote_metadata)

    # Verify.
    assert song.source == str(source_file)
    assert song.target == '/MUSIC/song.mp3'
    assert song.needs_action is (False if mode == 'up to date' else True)
    assert song.attrs == (str(source_file), '/MUSIC/song.mp3', int(source_file.stat().mtime))


def test_song_path(tmpdir):
    """Test Song class with long and unicode translations.

    :param tmpdir: pytest fixture.
    """
    source_file = tmpdir.ensure_dir('source').join('šöñgæ.mp3')
    HERE.join('1khz_sine.mp3').copy(source_file)

    # Generate long path.
    target_dir = '/'.join(['', 'MUSIC', 'a' * 100, 'b' * 120, 'c' * 140, 'd'])

    # Run.
    song = discover.Song(str(source_file), source_file.dirname, target_dir, dict())

    # Verify.
    assert song.source == str(source_file)
    assert song.target == '/MUSIC/' + ('a' * 75) + '/' + ('b' * 75) + '/' + ('c' * 75) + '/d/song.mp3'
    assert len(song.target) < 255
    assert song.needs_action is True

    # Test too long path. Too long path will be handled in caller function.
    target_dir = '/'.join(['', 'MUSIC'] + (['0000000000'] * 55))
    song = discover.Song(str(source_file), source_file.dirname, target_dir, dict())
    assert song.source == str(source_file)
    assert song.target == '/MUSIC/' + ('00000/' * 55) + 'song.mp3'
    assert len(song.target) > 255
    assert song.needs_action is True


def test_get_songs(monkeypatch, tmpdir):
    """Test get_songs() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    """
    shutdown_future = asyncio.Future()
    source_dir = tmpdir.ensure_dir('source')
    remote_files, remote_empty_dirs = dict(), list()
    monkeypatch.setattr(discover, 'get_files', lambda *_: (remote_files, remote_empty_dirs))

    # Test empty.
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert not songs
    assert not valid_targets
    assert files == remote_files
    assert empty_dirs == remote_empty_dirs

    # Test ignore.
    source_dir.ensure('ignore.txt')
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert not songs
    assert not valid_targets
    assert files == remote_files
    assert empty_dirs == remote_empty_dirs

    # Test working.
    existing = source_dir.join('existing.mp3')
    new = source_dir.join('new.mp3')
    HERE.join('1khz_sine.mp3').copy(existing)
    HERE.join('1khz_sine.mp3').copy(new)
    remote_empty_dirs.append('/MUSIC/empty_dir')
    remote_files['/MUSIC/existing.mp3'] = (existing.stat().size, existing.stat().mtime)
    remote_files['/MUSIC/delete.mp3'] = (existing.stat().size, existing.stat().mtime)
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert len(songs) == 1
    assert len(valid_targets) == 2
    assert songs[0].source == str(new)
    assert songs[0].target == '/MUSIC/new.mp3'
    assert sorted(valid_targets) == ['/MUSIC/existing.mp3', '/MUSIC/new.mp3']
    assert files == remote_files
    assert empty_dirs == remote_empty_dirs

    # Test shutdown.
    shutdown_future.set_result(True)
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert not songs
    assert not valid_targets
    assert not files
    assert not empty_dirs

    # Test unexpected exception.
    def func(*_):
        """Raise exception."""
        raise FlashAirError('Error')
    monkeypatch.setattr(discover, 'get_files', func)
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert not songs
    assert not valid_targets
    assert not files
    assert not empty_dirs

    # Test url too long.
    def func(*_):
        """Raise exception."""
        raise FlashAirURLTooLong('Error')
    monkeypatch.setattr(discover, 'get_files', func)
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)
    assert not songs
    assert not valid_targets
    assert not files
    assert not empty_dirs

    # Test network error.
    def func(*_):
        """Raise exception."""
        raise FlashAirNetworkError('Error')
    monkeypatch.setattr(discover, 'get_files', func)
    with pytest.raises(FlashAirNetworkError):
        discover.get_songs(str(source_dir), 'flashair', TZINFO, shutdown_future)


def test_get_songs_subdirectories(monkeypatch, tmpdir):
    """Test get_songs() with nested subdirectories.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    """
    monkeypatch.setattr(discover, 'get_files', lambda *_: (dict(), list()))

    # Setup directory structure.
    source_dir = tmpdir.ensure_dir('source')
    source_dir_a = source_dir.ensure_dir('a')
    source_dir_b = source_dir.ensure_dir('b')
    source_dir_c = source_dir.ensure_dir('b', 'c')
    source_dir_d = source_dir.ensure_dir('b', 'c', 'd')

    # Copy files.
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_a.join('song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_b.join('song3.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_c.join('song4.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_d.join('song5.mp3'))

    # Test those files.
    songs, valid_targets, files, empty_dirs = discover.get_songs(str(source_dir), 'flashair', TZINFO, asyncio.Future())
    assert len(songs) == 5
    assert len(valid_targets) == 5
    expected = {
        str(source_dir.join('song1.mp3')),
        str(source_dir_a.join('song2.mp3')),
        str(source_dir_b.join('song3.mp3')),
        str(source_dir_c.join('song4.mp3')),
        str(source_dir_d.join('song5.mp3')),
    }
    assert {s.source for s in songs} == expected
    expected = {
        '/MUSIC/song1.mp3',
        '/MUSIC/a/song2.mp3',
        '/MUSIC/b/song3.mp3',
        '/MUSIC/b/c/song4.mp3',
        '/MUSIC/b/c/d/song5.mp3',
    }
    assert {s.target for s in songs} == expected
    assert sorted(valid_targets) == sorted(expected)


def test_files_dirs_to_delete():
    """Test files_dirs_to_delete() function."""
    valid_targets, files, empty_dirs = list(), list(), list()

    # Test empty.
    delete_files_dirs = discover.files_dirs_to_delete(valid_targets, files, empty_dirs)
    assert not delete_files_dirs

    # Test ignore.
    files.append('/MUSIC/ignore.txt')
    delete_files_dirs = discover.files_dirs_to_delete(valid_targets, files, empty_dirs)
    assert not delete_files_dirs

    # Setup.
    expected = {'/MUSIC/empty', '/MUSIC/remove_me.mp3', '/MUSIC/keep_this/remove_me_too.mp3'}
    valid_targets.append('/MUSIC/keep_me.mp3')
    valid_targets.append('/MUSIC/keep_this/keep_me.mp3')
    files.append('/MUSIC/keep_me.mp3')
    files.append('/MUSIC/keep_this/keep_me.mp3')
    files.append('/MUSIC/keep_this/remove_me_too.mp3')
    files.append('/MUSIC/remove_me.mp3')
    empty_dirs.append('/MUSIC/empty')

    # Test.
    actual = discover.files_dirs_to_delete(valid_targets, files, empty_dirs)
    assert actual == expected
