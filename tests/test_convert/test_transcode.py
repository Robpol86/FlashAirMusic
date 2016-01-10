"""Test functions in module."""

import asyncio
from textwrap import dedent

import py
import pytest

from flash_air_music.configuration import DEFAULT_FFMPEG_BINARY
from flash_air_music.convert import transcode
from flash_air_music.convert.discover import Song

HERE = py.path.local(__file__).dirpath()


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_convert_file_success(monkeypatch, tmpdir, caplog):
    """Test convert_file() with no errors.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': DEFAULT_FFMPEG_BINARY})
    monkeypatch.setattr(transcode, 'SLEEP_FOR', 0.1)
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    song = Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir))
    assert song.needs_conversion is True

    # Run.
    loop = asyncio.get_event_loop()
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, song))[1:]

    # Verify.
    assert exit_status == 0
    assert target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is False

    # Verify log.
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert messages[0] == 'Converting song1.mp3'
    assert str(command) in messages[1]
    assert messages[-4].endswith('exited 0')
    assert messages[-1] == 'Storing metadata in song1.mp3'


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_convert_file_deadlock(monkeypatch, tmpdir, caplog):
    """Test convert_file() with ffmpeg outputting a lot of data, filling up buffers.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/bin/bash
    ffmpeg $@
    for i in {1..10240}; do echo -n test_stdout$i; done
    for i in {1..10240}; do echo -n test_stderr$i >&2; done
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': str(ffmpeg)})
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    song = Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir))

    # Run.
    loop = asyncio.get_event_loop()
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, song))[1:]

    # Verify.
    assert exit_status == 0
    assert target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is False

    # Verify log.
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert messages[0] == 'Converting song1.mp3'
    assert str(command) in messages[1]
    assert messages[2].endswith('still running...')
    assert messages[-4].endswith('exited 0')
    assert messages[-3].endswith('test_stdout10240')
    assert messages[-2].endswith('test_stderr10240')
    assert messages[-1] == 'Storing metadata in song1.mp3'
