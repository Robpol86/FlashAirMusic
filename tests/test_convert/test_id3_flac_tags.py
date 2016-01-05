"""Test functions in module."""

import json

import py
import pytest
from mutagen.id3 import COMM, ID3

from flash_air_music.convert import id3_flac_tags


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
        py.path.local(__file__).dirpath().join('1khz_sine.mp3').copy(path)

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
