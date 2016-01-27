"""Test flash_air_music.__main__ functions/classes."""

import os
import re
import signal
import subprocess
import sys
import time
from distutils.spawn import find_executable
from textwrap import dedent

import pytest

from flash_air_music.configuration import CONVERTED_MUSIC_SUBDIR, DEFAULT_FFMPEG_BINARY
from tests import HERE


def test_error(tmpdir):
    """Test config error handling.

    :param tmpdir: pytest fixture.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {0}
    verbose = true
    working-dir = {0}
    """).format(tmpdir))
    command = [find_executable('FlashAirMusic'), 'run', '--config', str(config_file)]
    assert os.path.isfile(command[0])

    with pytest.raises(subprocess.CalledProcessError) as exc:
        subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=1)
    stdout = exc.value.output.decode('utf-8')
    assert 'Working directory converted music subdir cannot be in music source dir.' in stdout
    assert 'Failure.' in stdout
    assert 'BUG!' not in stdout


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_sighup(tmpdir):
    """Test config reloading.

    :param tmpdir: pytest fixture.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {}
    verbose = true
    working-dir = {}
    """).format(tmpdir.ensure_dir('source'), tmpdir.ensure_dir('working')))
    command = [find_executable('FlashAirMusic'), 'run', '--config', str(config_file)]

    # Run.
    stdout_file = tmpdir.join('stdout.log')
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout_file.open('w'))
    for _ in range(100):
        if 'watch_directory() sleeping' in stdout_file.read() or process.poll() is not None:
            break
        time.sleep(0.1)

    # Update config.
    log_file = tmpdir.join('log.log')
    if process.poll() is None:
        config_file.write('log = {}'.format(log_file), mode='a')
        process.send_signal(signal.SIGHUP)
        for _ in range(100):
            if 'Done reloading configuration.' in stdout_file.read() or process.poll() is not None:
                break
            time.sleep(0.1)

    # Stop.
    try:
        process.kill()
    except ProcessLookupError:
        pass

    # Verify.
    stdout = stdout_file.read()
    print(stdout, file=sys.stderr)
    log = log_file.read()
    print(log, file=sys.stderr)
    assert 'Configured logging.' in stdout
    assert re.search(r'Caught signal 1 \([\w/_]+\)\. Reloading configuration\.', stdout)
    assert 'Done reloading configuration.' in stdout
    assert 'Done reloading configuration.' in log
    assert 'Traceback' not in stdout
    assert 'Traceback' not in log
    assert 'ERROR' not in stdout
    assert 'ERROR' not in log
    for line in log.splitlines():
        assert line in stdout
    assert 'BUG!' not in stdout


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_empty(tmpdir):
    """Test with no music to convert.

    :param tmpdir: pytest fixture.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {}
    verbose = true
    working-dir = {}
    """).format(tmpdir.ensure_dir('source'), tmpdir.ensure_dir('working')))
    command = [find_executable('FlashAirMusic'), 'run', '--config', str(config_file)]

    # Run.
    stdout_file = tmpdir.join('stdout.log')
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout_file.open('w'))
    for _ in range(100):
        if 'watch_directory() sleeping' in stdout_file.read() or process.poll() is not None:
            break
        time.sleep(0.1)

    # Stop.
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        for _ in range(100):
            if process.poll() is not None:
                break
            time.sleep(0.1)

    # Verify.
    stdout = stdout_file.read()
    print(stdout, file=sys.stderr)
    assert 'watch_directory() file system changed, calling run().' in stdout
    assert 'Found: 0 new source songs, 0 orphaned target songs, 0 empty directories.' in stdout
    assert 'watch_directory() saw shutdown signal.' in stdout
    assert 'Stopping loop.' in stdout
    assert 'Main loop has exited.' in stdout
    assert 'Traceback' not in stdout
    assert 'ERROR' not in stdout
    assert 'BUG!' not in stdout
    assert process.poll() == 0


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
def test_songs(tmpdir):
    """Test with a few music files.

    :param tmpdir: pytest fixture.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {}
    verbose = false
    working-dir = {}
    """).format(tmpdir.ensure_dir('source'), tmpdir.ensure_dir('working')))
    command = [find_executable('FlashAirMusic'), 'run', '--config', str(config_file)]

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song3.mp3'))

    # Run.
    stdout_file = tmpdir.join('stdout.log')
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout_file.open('w'))
    for _ in range(100):
        if 'watch_directory() sleeping' in stdout_file.read() or process.poll() is not None:
            break
        time.sleep(0.1)

    # Stop.
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        for _ in range(100):
            if process.poll() is not None:
                break
            time.sleep(0.1)

    # Verify.
    stdout = stdout_file.read()
    print(stdout, file=sys.stderr)
    assert 'Found: 3 new source songs, 0 orphaned target songs, 0 empty directories.' in stdout
    assert 'Done converting 3 file(s) (0 failed).' in stdout
    assert 'Stopping loop.' in stdout
    assert 'Main loop has exited.' in stdout
    assert 'Traceback' not in stdout
    assert 'ERROR' not in stdout
    assert 'BUG!' not in stdout
    assert process.poll() == 0
    assert tmpdir.join('working', CONVERTED_MUSIC_SUBDIR, 'song1.mp3').check(file=True)
    assert tmpdir.join('working', CONVERTED_MUSIC_SUBDIR, 'song2.mp3').check(file=True)
    assert tmpdir.join('working', CONVERTED_MUSIC_SUBDIR, 'song3.mp3').check(file=True)


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
def test_interrupt_ffmpeg(monkeypatch, tmpdir, signum):
    """Test stopping with ffmpeg hanging.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param int signum: Terminating signal to send.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {}
    threads = 3
    verbose = true
    working-dir = {}
    """).format(tmpdir.ensure_dir('source'), tmpdir.ensure_dir('working')))
    command = [find_executable('FlashAirMusic'), 'run', '--config', str(config_file)]

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song3.mp3'))

    ffmpeg = tmpdir.ensure_dir('bin').join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/usr/bin/env python
    import signal, sys, time
    signal.signal(signal.SIGINT, lambda n, _: sys.exit(n))
    signal.signal(signal.SIGTERM, lambda n, _: sys.exit(n))
    for i in range(30):
        print(i)
        time.sleep(1)
    sys.exit(1)
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setenv('PATH', '{}:{}'.format(ffmpeg.dirname, os.environ['PATH']))

    # Run.
    stdout_file = tmpdir.join('stdout.log')
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout_file.open('w'))
    for _ in range(100):
        if 'still running...' in stdout_file.read() or process.poll() is not None:
            break
        time.sleep(0.1)

    # Stop.
    if process.poll() is None:
        process.send_signal(signum)
        for _ in range(100):
            if process.poll() is not None:
                break
            time.sleep(0.1)

    # Verify.
    stdout = stdout_file.read()
    print(stdout, file=sys.stderr)
    assert 'Found: 3 new source songs, 0 orphaned target songs, 0 empty directories.' in stdout
    assert 'Beginning to convert 3 file(s) up to 3 at a time.' in stdout
    assert 'Failed to convert song1.mp3! ffmpeg exited {}.'.format(signum) in stdout
    assert 'Failed to convert song2.mp3! ffmpeg exited {}.'.format(signum) in stdout
    assert 'Failed to convert song3.mp3! ffmpeg exited {}.'.format(signum) in stdout
    assert 'Done converting 3 file(s) (3 failed).' in stdout
    assert 'Stopping loop.' in stdout
    assert 'Main loop has exited.' in stdout
    assert 'Traceback' not in stdout
    assert 'BUG!' not in stdout
    assert process.poll() == 0


def test_bug_hangs(monkeypatch, tmpdir):
    """Make sure program times out and exits even with pending tasks.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    """
    config_file = tmpdir.join('config.ini')
    config_file.write(dedent("""\
    [FlashAirMusic]
    music-source = {}
    threads = 3
    verbose = true
    working-dir = {}
    """).format(tmpdir.ensure_dir('source'), tmpdir.ensure_dir('working')))

    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song1.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song2.mp3'))
    HERE.join('1khz_sine.mp3').copy(tmpdir.join('source', 'song3.mp3'))

    ffmpeg = tmpdir.ensure_dir('bin').join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/usr/bin/env python
    import signal, sys, time
    signal.signal(signal.SIGTERM, lambda *_: None)
    for i in range(30):
        print(i)
        time.sleep(1)
    sys.exit(1)
    """))
    ffmpeg.chmod(0o0755)
    monkeypatch.setenv('PATH', '{}:{}'.format(ffmpeg.dirname, os.environ['PATH']))

    intercept = tmpdir.join('intercept.py')
    intercept.write(dedent("""\
    #!/usr/bin/env python
    import signal
    from flash_air_music.__main__ import entry_point
    signal.SIGKILL = signal.SIGTERM
    entry_point()
    """))
    intercept.chmod(0o0755)

    # Run.
    command = [str(intercept), 'run', '--config', str(config_file)]
    stdout_file = tmpdir.join('stdout.log')
    process = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=stdout_file.open('w'))
    for _ in range(100):
        if 'still running...' in stdout_file.read() or process.poll() is not None:
            break
        time.sleep(0.1)

    # Stop.
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        for _ in range(100):
            if process.poll() is not None:
                break
            time.sleep(0.1)

    # Verify.
    stdout = stdout_file.read()
    print(stdout, file=sys.stderr)
    assert 'Found: 3 new source songs, 0 orphaned target songs, 0 empty directories.' in stdout
    assert 'Beginning to convert 3 file(s) up to 3 at a time.' in stdout
    assert 'Failed to convert song1.mp3!' not in stdout
    assert 'Failed to convert song2.mp3!' not in stdout
    assert 'Failed to convert song3.mp3!' not in stdout
    assert 'Done converting 3 file(s)' not in stdout
    assert 'Stopping loop.' in stdout
    assert 'Main loop has exited.' in stdout
    assert 'Task was destroyed but it is pending!' in stdout
    assert 'task: <Task pending coro=<watch_directory() running at' in stdout
    assert 'Traceback' in stdout
    assert 'BUG!' not in stdout
    assert process.poll() == 0
