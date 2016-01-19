"""Test functions in module."""

import asyncio
import itertools
import re
from textwrap import dedent

import py
import pytest

from flash_air_music.configuration import DEFAULT_FFMPEG_BINARY
from flash_air_music.convert import transcode
from flash_air_music.convert.discover import get_songs, Song

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
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, asyncio.Future(), song))[1:]
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert exit_status == 0
    assert target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is False

    # Verify log.
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
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, asyncio.Future(), song))[1:]
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert exit_status == 1
    assert not target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is True

    # Verify log.
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
    command, exit_status = loop.run_until_complete(transcode.convert_file(loop, asyncio.Future(), song))[1:]
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert exit_status == 0
    assert target_dir.join('song1.mp3').check(file=True)
    assert Song(str(source_dir.join('song1.mp3')), str(source_dir), str(target_dir)).needs_conversion is False

    # Verify log.
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
    trap "echo Ignoring SIGINT." SIGINT
    trap "echo Ignoring SIGTERM." SIGTERM
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
    exit_status = loop.run_until_complete(transcode.convert_file(loop, asyncio.Future(), song))[-1]
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
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


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
@pytest.mark.parametrize('mode', ['failure', 'exception'])
def test_convert_songs_errors(monkeypatch, tmpdir, caplog, mode):
    """Test convert_songs()'s error handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    if mode != 'exception':
        ffmpeg.write(dedent("""\
        #!/bin/bash
        [ "$ERROR_ON" == "$(basename $2)" ] && exit 2
        ffmpeg $@
        """))
        ffmpeg.chmod(0o0755)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': str(ffmpeg), '--threads': '2'})
    monkeypatch.setenv('ERROR_ON', 'song1.mp3' if mode == 'failure' else '')
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song2.mp3'))
    songs = get_songs(str(source_dir), str(target_dir))[0]

    # Run.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(transcode.convert_songs(loop, asyncio.Future(), songs))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify files.
    assert not target_dir.join('song1.mp3').check()
    if mode == 'exception':
        assert not target_dir.join('song2.mp3').check()
    else:
        assert target_dir.join('song2.mp3').check(file=True)

    # Verify log.
    assert 'Storing metadata in song1.mp3' not in messages
    if mode == 'exception':
        assert 'Storing metadata in song2.mp3' not in messages
        assert len([True for m in messages if m.startswith('BUG!')]) == 2
        assert any(re.match(r'Beginning to convert 2 file\(s\) up to 2 at a time\.$', m) for m in messages)
        assert any(re.match(r'Done converting 2 file\(s\) \(2 failed\)\.$', m) for m in messages)
    elif mode == 'failure':
        assert 'Storing metadata in song2.mp3' in messages
        assert len([True for m in messages if m.startswith('BUG!')]) == 0
        assert any(re.match(r'Beginning to convert 2 file\(s\) up to 2 at a time\.$', m) for m in messages)
        assert any(re.match(r'Done converting 2 file\(s\) \(1 failed\)\.$', m) for m in messages)


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_convert_songs_single(monkeypatch, tmpdir, caplog):
    """Test convert_songs() with one file.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': DEFAULT_FFMPEG_BINARY, '--threads': '2'})
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    songs = get_songs(str(source_dir), str(target_dir))[0]

    # Run.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(transcode.convert_songs(loop, asyncio.Future(), songs))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert target_dir.join('song1.mp3').check(file=True)
    assert 'Storing metadata in song1.mp3' in messages
    assert any(re.match(r'Beginning to convert 1 file\(s\) up to 2 at a time\.$', m) for m in messages)
    assert any(re.match(r'Done converting 1 file\(s\) \(0 failed\)\.$', m) for m in messages)


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_convert_songs_semaphore(monkeypatch, tmpdir, caplog):
    """Test convert_songs() concurrency limit.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/bin/bash
    python -c "import time; print('$(basename $2) START_TIME:', time.time())"
    ffmpeg $@
    python -c "import time; print('$(basename $2) END_TIME:', time.time())"
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': str(ffmpeg), '--threads': '2'})
    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song3.mp3'))
    HERE.join('1khz_sine.mp3').copy(source_dir.join('song4.mp3'))
    songs = get_songs(str(source_dir), str(target_dir))[0]

    # Run.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(transcode.convert_songs(loop, asyncio.Future(), songs))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert target_dir.join('song1.mp3').check(file=True)
    assert 'Storing metadata in song1.mp3' in messages
    assert 'Storing metadata in song2.mp3' in messages
    assert 'Storing metadata in song3.mp3' in messages
    assert 'Storing metadata in song4.mp3' in messages
    assert any(re.match(r'Beginning to convert 4 file\(s\) up to 2 at a time\.$', m) for m in messages)
    assert any(re.match(r'Done converting 4 file\(s\) \(0 failed\)\.$', m) for m in messages)

    # Verify overlaps.
    regex = re.compile(r'(song\d\.mp3) START_TIME: ([\d\.]+)\n\1 END_TIME: ([\d\.]+)')
    intervals = [(float(p[0]), float(p[1])) for p in (g.groups()[1:] for g in (regex.search(m) for m in messages) if g)]
    intervals.sort()
    assert len(intervals) == 4
    overlaps = 0
    for a, b in itertools.combinations(range(4), 2):
        if intervals[b][0] < intervals[a][0] < intervals[b][1] or intervals[a][0] < intervals[b][0] < intervals[a][1]:
            overlaps += 1
    assert overlaps <= 3
