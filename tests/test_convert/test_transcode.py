"""Test functions in module."""

import asyncio
import re
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
    command_str = str(command)
    assert 'Converting song1.mp3' in messages
    assert 'Storing metadata in song1.mp3' in messages
    assert any(command_str in m for m in messages)
    assert any(re.match(r'^Process \d+ exited 0$', m) for m in messages)


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
@pytest.mark.parametrize('delete', [False, True])
def test_convert_file_failure(monkeypatch, tmpdir, caplog, delete):
    """Test convert_file() with errors.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param bool delete: Test removing bad target file.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/bin/bash
    exit 1
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': str(ffmpeg)})
    monkeypatch.setattr(transcode, 'SLEEP_FOR', 0.1)
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    if delete:
        HERE.join('1khz_sine.mp3').copy(target_dir.join('song1.mp3'))
    song = Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir))
    assert song.needs_conversion is True

    # Run.
    loop = asyncio.get_event_loop()
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, song))[1:]

    # Verify.
    assert exit_status == 1
    assert not target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is True

    # Verify log.
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    command_str = str(command)
    assert 'Converting song1.mp3' in messages
    assert 'Storing metadata in song1.mp3' not in messages
    assert 'Failed to convert song1.mp3! ffmpeg exited 1.' in messages
    assert any(command_str in m for m in messages)
    assert any(re.match(r'^Process \d+ exited 1$', m) for m in messages)
    if delete:
        assert 'Removing {}'.format(str(target_dir.join('song1.mp3'))) in messages
    else:
        assert 'Removing {}'.format(str(target_dir.join('song1.mp3'))) not in messages


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
    command_str = str(command)
    assert 'Converting song1.mp3' in messages
    assert 'Storing metadata in song1.mp3' in messages
    assert any(command_str in m for m in messages)
    assert any(re.match(r'^Process \d+ exited 0$', m) for m in messages)
    assert any(re.match(r'^Process \d+ still running\.\.\.$', m) for m in messages)
    assert any(m.endswith('test_stdout10240') for m in messages)
    assert any(m.endswith('test_stderr10240') for m in messages)


@pytest.mark.parametrize('exit_signal', ['SIGINT', 'SIGTERM', 'SIGKILL'])
def test_convert_file_timeout(monkeypatch, tmpdir, caplog, exit_signal):
    """Test convert_file() with a stalled process.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str exit_signal: Script exits on this signal.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/bin/bash
    trap "echo Ignoring signal." SIGINT SIGTERM
    [ -n "$EXIT_SIGNAL" ] && trap "{ echo Catching $EXIT_SIGNAL; exit 2; }" $EXIT_SIGNAL
    for i in {1..10}; do echo $i; sleep 0.1; done
    exit 1
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': str(ffmpeg)})
    monkeypatch.setattr(transcode, 'SLEEP_FOR', 0.1)
    monkeypatch.setattr(transcode, 'TIMEOUT', 0.5)
    monkeypatch.setenv('EXIT_SIGNAL', exit_signal)
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    song = Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir))

    # Run.
    loop = asyncio.get_event_loop()
    exit_status = loop.run_until_complete(transcode.convert_file(loop, song))[-1]

    # Verify.
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert exit_status == 2 if exit_signal != 'SIGKILL' else -1
    assert 'Converting song1.mp3' in messages
    assert 'Storing metadata in song1.mp3' not in messages
    assert any(re.match(r'^Process \d+ exited {}$'.format(exit_status), m) for m in messages)
    assert any(re.match(r'^Process \d+ still running\.\.\.$', m) for m in messages)

    # Verify based on exit_signal.
    sent_signals = [m for m in messages if m.startswith('Timeout exceeded')]
    assert sent_signals[0].startswith('Timeout exceeded, sending signal 2')
    if exit_signal in ('SIGTERM', 'SIGKILL'):
        assert sent_signals[1].startswith('Timeout exceeded, sending signal 15')
    if exit_signal == 'SIGKILL':
        assert sent_signals[2].startswith('Timeout exceeded, sending signal 9')
