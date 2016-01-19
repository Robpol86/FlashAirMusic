"""Test functions in module."""

import asyncio
import re
import signal
from textwrap import dedent

import py
import pytest

from flash_air_music.__main__ import shutdown
from flash_air_music.configuration import CONVERTED_MUSIC_SUBDIR, DEFAULT_FFMPEG_BINARY
from flash_air_music.convert import discover, run, transcode

HERE = py.path.local(__file__).dirpath()


@asyncio.coroutine
def write_to_file_slowly(caplog, path):
    """Write to file as needed.

    :param caplog: pytest extension fixture.
    :param str path: File path to write to.
    """
    with open(path, 'w') as handle:
        while not any(True for r in caplog.records if r.message.startswith('Size/mtime changed for ')):
            handle.write('.')
            handle.flush()
            yield from asyncio.sleep(0.1)


@asyncio.coroutine
def shutdown_after_start(loop, shutdown_future, caplog, signum):
    """Stop currently running conversions.

    :param loop: AsyncIO event loop object.
    :param asyncio.Future shutdown_future: Shutdown signal.
    :param caplog: pytest extension fixture.
    :param int signum: Signal to simulate.
    """
    while not any(True for r in caplog.records if re.match(r'Process \d+ still running\.\.\.', r.message)):
        yield from asyncio.sleep(0.1, loop=loop)
    yield from shutdown(signum, shutdown_future)


@pytest.mark.parametrize('mode', ['none', 'static', 'wait'])
def test_scan_wait(monkeypatch, tmpdir, caplog, mode):
    """Test scan_wait() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    source_file = tmpdir.join('source').ensure_dir().join('song.mp3')
    monkeypatch.setattr(run, 'GLOBAL_MUTABLE_CONFIG',
                        {'--music-source': source_file.dirname, '--working-dir': str(tmpdir)})
    if mode != 'none':
        HERE.join('1khz_sine.mp3').copy(source_file)

    # Run.
    loop = asyncio.get_event_loop()
    if mode == 'wait':
        nested_results = loop.run_until_complete(asyncio.wait([
            write_to_file_slowly(caplog, str(source_file)), run.scan_wait(loop)
        ], timeout=30))
        songs, delete_files, remove_dirs = [s for s in nested_results[0] if s.result()][0].result()
    else:
        songs, delete_files, remove_dirs = loop.run_until_complete(run.scan_wait(loop))

    # Verify.
    assert [s.source for s in songs] == ([] if mode == 'none' else [str(source_file)])
    assert not delete_files
    assert not remove_dirs

    # Verify logs.
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert 'Scanning for new/changed songs...' in messages
    if mode == 'none':
        assert messages[-1] == 'Found: 0 new source songs, 0 orphaned target songs, 0 empty directories.'
    else:
        assert 'Found: 1 new source song, 0 orphaned target songs, 0 empty directories.' in messages
        if mode == 'wait':
            assert 'Size/mtime changed for {}'.format(str(source_file)) in messages
            assert '1 song still being written to, waiting 0.5 seconds...'
        else:
            assert 'Size/mtime changed for {}'.format(str(source_file)) not in messages


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
@pytest.mark.parametrize('mode', ['nothing', 'normal', 'error'])
def test_convert_cleanup(monkeypatch, tmpdir, caplog, mode):
    """Test convert_cleanup() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', {'--ffmpeg-bin': DEFAULT_FFMPEG_BINARY, '--threads': '2'})
    loop = asyncio.get_event_loop()

    if mode == 'nothing':
        loop.run_until_complete(run.convert_cleanup(loop, asyncio.Future(), [], [], []))
        assert not [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
        return

    source_dir = tmpdir.join('source').ensure_dir()
    target_dir = tmpdir.join('target').ensure_dir()
    target_dir.join('empty').ensure_dir().join('subdir').ensure_dir()
    target_dir.join('empty', 'song2.mp3').ensure()

    if mode == 'normal':
        HERE.join('1khz_sine.mp3').copy(source_dir.join('song1.mp3'))
    else:
        target_dir.join('empty').ensure_dir().chmod(0o0544)

    songs, valid_targets = discover.get_songs(str(source_dir), str(target_dir))
    delete_files, remove_dirs = discover.files_dirs_to_delete(str(target_dir), valid_targets)

    # Run.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run.convert_cleanup(loop, asyncio.Future(), songs, delete_files, remove_dirs))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert target_dir.listdir() == [target_dir.join('song1.mp3') if mode == 'normal' else target_dir.join('empty')]
    if mode == 'normal':
        assert 'Storing metadata in song1.mp3' in messages
    assert 'Deleting {}'.format(str(target_dir.join('empty', 'song2.mp3'))) in messages
    assert 'Removing empty directory {}'.format(str(target_dir.join('empty', 'subdir'))) in messages
    assert 'Removing empty directory {}'.format(str(target_dir.join('empty'))) in messages
    if mode == 'error':
        assert 'Failed to delete {}'.format(str(target_dir.join('empty', 'song2.mp3'))) in messages
        assert 'Failed to remove {}'.format(str(target_dir.join('empty', 'subdir'))) in messages
        assert 'Failed to remove {}'.format(str(target_dir.join('empty'))) in messages
    else:
        assert 'Failed to delete {}'.format(str(target_dir.join('empty', 'song2.mp3'))) not in messages
        assert 'Failed to remove {}'.format(str(target_dir.join('empty', 'subdir'))) not in messages
        assert 'Failed to remove {}'.format(str(target_dir.join('empty'))) not in messages


@pytest.mark.skipif(str(DEFAULT_FFMPEG_BINARY is None))
@pytest.mark.parametrize('mode', ['nothing', 'something'])
def test_run(monkeypatch, tmpdir, mode):
    """Test run() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param str mode: Scenario to test for.
    """
    source_file = tmpdir.join('source').ensure_dir().join('song.mp3')
    config = {
        '--ffmpeg-bin': DEFAULT_FFMPEG_BINARY,
        '--music-source': source_file.dirname,
        '--threads': '2',
        '--working-dir': str(tmpdir),
    }
    monkeypatch.setattr(run, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', config)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(loop=loop)

    if mode == 'nothing':
        loop.run_until_complete(run.run(loop, semaphore, asyncio.Future()))
        assert not semaphore.locked()
        assert not tmpdir.join(CONVERTED_MUSIC_SUBDIR, 'song.mp3').check()
        return

    tmpdir.join(CONVERTED_MUSIC_SUBDIR).ensure_dir()
    HERE.join('1khz_sine.mp3').copy(source_file)
    assert not tmpdir.join(CONVERTED_MUSIC_SUBDIR, 'song.mp3').check()
    loop.run_until_complete(run.run(loop, semaphore, asyncio.Future()))
    assert not semaphore.locked()
    assert tmpdir.join(CONVERTED_MUSIC_SUBDIR, 'song.mp3').check(file=True)


@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
def test_run_cancel(monkeypatch, tmpdir, caplog, signum):
    """Test run() cancellation handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param int signum: Signal to simulate.
    """
    ffmpeg = tmpdir.join('ffmpeg')
    ffmpeg.write(dedent("""\
    #!/usr/bin/env python
    import signal, sys, time
    time.sleep(10)
    sys.exit(3)
    """))
    ffmpeg.chmod(0o0755)
    source_dir = tmpdir.join('source').ensure_dir()
    for i in range(10):
        source_dir.join('song{}.mp3'.format(i)).ensure()
    tmpdir.join(CONVERTED_MUSIC_SUBDIR).ensure_dir()

    config = {
        '--ffmpeg-bin': str(ffmpeg),
        '--music-source': str(source_dir),
        '--threads': '2',
        '--working-dir': str(tmpdir),
    }
    monkeypatch.setattr(run, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(transcode, 'GLOBAL_MUTABLE_CONFIG', config)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(loop=loop)
    shutdown_future = asyncio.Future()

    loop.run_until_complete(asyncio.wait([
        shutdown_after_start(loop, shutdown_future, caplog, signum),
        run.run(loop, semaphore, shutdown_future),
    ], timeout=30))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    assert [i for i in messages if i.startswith('Caught signal {}'.format(signum))]
    killed = [i for i in messages
              if re.match(r'Process \d+ exited {}'.format(1 if signum == signal.SIGINT else -signal.SIGTERM), i)]
    skipped = [i for i in messages if i == 'Skipping due to shutdown_future signal.']
    assert len(killed) + len(skipped) == 10
