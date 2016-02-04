"""Test functions in module."""

import json

import pytest
from mutagen.id3 import COMM, ID3

from flash_air_music.convert import id3_flac_tags
from flash_air_music.convert.discover import Song
from flash_air_music.exceptions import CorruptedTargetFile
from tests import HERE


@pytest.mark.parametrize('mode', ['dne', 'empty', 'corrupted', 'no comment', 'bad comment', 'partial', 'good'])
def test_read_stored_metadata(tmpdir, caplog, mode):
    """Test read_stored_metadata().

    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    path = tmpdir.join('song.mp3')

    # Copy sample mp3.
    if mode == 'empty':
        path.ensure()
    elif mode == 'corrupted':
        path.write('\x00\x00\x00\x00')
    elif mode != 'dne':
        HERE.join('1khz_sine.mp3').copy(path)

    # Write ID3 tag.
    text, expected = '', dict()
    if mode == 'bad comment':
        text = 'invalid'
    elif mode == 'partial':
        text = json.dumps(dict(source_mtime=123))
    elif mode == 'good':
        text = json.dumps(dict(source_mtime=123, source_size=456, target_mtime=123, target_size=456))
        expected = dict(source_mtime=123, source_size=456, target_mtime=123, target_size=456)
    if text:
        id3 = ID3(str(path))
        id3.add(COMM(desc=id3_flac_tags.COMMENT_DESCRIPTION, encoding=3, lang='eng', text=text))
        id3.save()

    # Run.
    actual = id3_flac_tags.read_stored_metadata(str(path))

    # Verify.
    assert actual == expected
    messages = [r.message for r in caplog.records]
    if mode in ('good', 'dne'):
        assert not messages
    elif mode in ('empty', 'corrupted'):
        assert messages[-1].startswith('Corrupted mp3 file')
    elif mode == 'no comment':
        assert messages[-1].startswith('No comment tag in mp3 file')
    elif mode == 'bad comment':
        assert messages[-1].startswith('Comment tag not JSON in mp3 file')
    else:
        assert messages[-1].startswith('Comment tag JSON has missing/invalid data mp3 file')


def test_write_stored_metadata(tmpdir, caplog):
    """Test write_stored_metadata().

    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    source_file = tmpdir.ensure_dir('source').ensure('song.mp3')
    target_file = tmpdir.ensure_dir('target').ensure('song.mp3')
    song = Song(str(source_file), source_file.dirname, target_file.dirname)

    # Test empty file.
    with pytest.raises(CorruptedTargetFile):
        id3_flac_tags.write_stored_metadata(song)
    messages = [r.message for r in caplog.records]
    assert messages[-1].startswith('Corrupted mp3 file')

    # Run.
    HERE.join('1khz_sine.mp3').copy(source_file)
    HERE.join('1khz_sine.mp3').copy(target_file)
    assert song.needs_action is True
    id3_flac_tags.write_stored_metadata(song)

    # Verify.
    song = Song(str(source_file), source_file.dirname, target_file.dirname)
    assert song.needs_action is False
