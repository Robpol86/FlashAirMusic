"""Test functions in module."""

import json
import os
import time

import py
import pytest
from mutagen.id3 import COMM, ID3

from flash_air_music.convert import discover, id3_flac_tags

HERE = py.path.local(__file__).dirpath()


@pytest.mark.parametrize('mode', ['no target', 'no prev metadata', 'st', 'ss', 'tt', 'ts', 'up to date'])
def test_song(tmpdir, mode):
    """Test Song class.

    :param tmpdir: pytest fixture.
    :param str mode: Scenario to test for.
    """
    source_file = tmpdir.ensure_dir('source').join('song.mp3')
    target_file = tmpdir.ensure_dir('target').join('song.mp3')
    HERE.join('1khz_sine.mp3').copy(source_file)

    # Write metadata.
    if mode != 'no target':
        source_file.copy(target_file)
        if mode != 'no prev metadata':
            ID3(str(target_file)).save(padding=lambda _: 200)
            metadata = dict(
                source_mtime=int(source_file.stat().mtime) - (20 if mode == 'st' else 0),
                source_size=int(source_file.stat().size) - (20 if mode == 'ss' else 0),
                target_mtime=int(target_file.stat().mtime) - (20 if mode == 'tt' else 0),
                target_size=int(target_file.stat().size) - (20 if mode == 'ts' else 0),
            )
            atime, mtime = time.time(), target_file.stat().mtime
            id3 = ID3(str(target_file))
            id3.add(COMM(desc=id3_flac_tags.COMMENT_DESCRIPTION, encoding=3, lang='eng', text=json.dumps(metadata)))
            id3.save()
            os.utime(str(target_file), (atime, mtime))

    # Run.
    song = discover.Song(str(source_file), source_file.dirname, target_file.dirname)

    # Verify.
    assert song.source == str(source_file)
    assert song.target == str(target_file)
    assert song.needs_conversion is (False if mode == 'up to date' else True)
    assert repr(song) == '<Song name=song.mp3 changed=False needs_conversion={}>'.format(song.needs_conversion)
    assert song.changed is False

    # Test changed.
    ID3(str(source_file)).save(padding=lambda _: 200)
    assert song.changed is True
    song.refresh_current_metadata()
    assert song.changed is False


def test_get_songs(tmpdir):
    """Test get_songs() function.

    :param tmpdir: pytest fixture.
    """
    source_dir = tmpdir.ensure_dir('source')
    target_dir = tmpdir.ensure_dir('target')

    # Test empty.
    songs, valid_targets = discover.get_songs(str(source_dir), str(target_dir))
    assert not songs
    assert not valid_targets

    # Test ignore.
    source_dir.ensure('ignore.txt')
    songs, valid_targets = discover.get_songs(str(source_dir), str(target_dir))
    assert not songs
    assert not valid_targets

    # Create mp3 that needs conversion and FLAC that doesn't.
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    HERE.join('1khz_sine.flac').copy(source_dir.join('song2.flac'))
    HERE.join('1khz_sine.mp3').copy(target_dir.join('song2.mp3'))
    ID3(str(target_dir.join('song2.mp3'))).save(padding=lambda _: 200)
    metadata = dict(
        source_mtime=int(source_dir.join('song2.flac').stat().mtime),
        source_size=int(source_dir.join('song2.flac').stat().size),
        target_mtime=int(target_dir.join('song2.mp3').stat().mtime),
        target_size=int(target_dir.join('song2.mp3').stat().size),
    )
    atime, mtime = time.time(), target_dir.join('song2.mp3').stat().mtime
    id3 = ID3(str(target_dir.join('song2.mp3')))
    id3.add(COMM(desc=id3_flac_tags.COMMENT_DESCRIPTION, encoding=3, lang='eng', text=json.dumps(metadata)))
    id3.save()
    os.utime(str(target_dir.join('song2.mp3')), (atime, mtime))

    # Test those files.
    songs, valid_targets = discover.get_songs(str(source_dir), str(target_dir))
    assert len(songs) == 1
    assert len(valid_targets) == 2
    assert songs[0].source == str(source_dir.join('song1.mp3'))
    assert songs[0].target == str(target_dir.join('song1.mp3'))
    assert sorted(valid_targets) == [str(target_dir.join('song1.mp3')), str(target_dir.join('song2.mp3'))]


def test_get_songs_subdirectories(tmpdir):
    """Test get_songs() with nested subdirectories.

    :param tmpdir: pytest fixture.
    """
    # Setup directory structure.
    source_dir = tmpdir.ensure_dir('source')
    source_dir_a = source_dir.ensure_dir('a')
    source_dir_b = source_dir.ensure_dir('b')
    source_dir_c = source_dir.ensure_dir('b', 'c')
    source_dir_d = source_dir.ensure_dir('b', 'c', 'd')
    target_dir = tmpdir.ensure_dir('target')

    # Copy files.
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_a.join('song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_b.join('song3.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_c.join('song4.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir_d.join('song5.mp3'))

    # Test those files.
    songs, valid_targets = discover.get_songs(str(source_dir), str(target_dir))
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
        str(target_dir.join('song1.mp3')),
        str(target_dir.join('a', 'song2.mp3')),
        str(target_dir.join('b', 'song3.mp3')),
        str(target_dir.join('b', 'c', 'song4.mp3')),
        str(target_dir.join('b', 'c', 'd', 'song5.mp3')),
    }
    assert {s.target for s in songs} == expected
    assert sorted(valid_targets) == sorted(expected)


def test_files_dirs_to_delete(tmpdir):
    """Test files_dirs_to_delete() function.

    :param tmpdir: pytest fixture.
    """
    target_dir = tmpdir.ensure_dir('target')
    valid_targets = list()

    # Test empty.
    delete_files, remove_dirs = discover.files_dirs_to_delete(str(target_dir), valid_targets)
    assert not delete_files
    assert not remove_dirs

    # Test ignore.
    target_dir.ensure('ignore.txt')
    target_dir.ensure_dir('not_empty').ensure('ignore.txt')
    delete_files, remove_dirs = discover.files_dirs_to_delete(str(target_dir), valid_targets)
    assert not delete_files
    assert not remove_dirs

    # Setup filesystem.
    expected_delete, expected_remove = set(), {str(target_dir.ensure_dir('remove_this_dir'))}
    expected_delete.add(str(target_dir.ensure('remove_this_dir', 'remove_me.mp3')))
    expected_delete.add(str(target_dir.ensure('remove_me_too.mp3')))
    expected_remove.add(str(target_dir.ensure_dir('remove_this_dir_too')))
    valid_targets.append(str(target_dir.ensure('keep_me.mp3')))
    valid_targets.append(str(target_dir.ensure_dir('keep_this').ensure('keep_me.mp3')))

    # Test those files.
    delete_files, remove_dirs = discover.files_dirs_to_delete(str(target_dir), valid_targets)
    assert delete_files == expected_delete
    assert remove_dirs == expected_remove
