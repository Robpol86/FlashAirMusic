"""Test functions in module."""

import asyncio

import py
import pytest

from flash_air_music.convert import control

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


@pytest.mark.parametrize('mode', ['none', 'static', 'wait'])
def test_scan_wait(monkeypatch, tmpdir, caplog, mode):
    """Test scan_wait() function.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param mode: Scenario to test for.
    """
    source_file = tmpdir.join('source').ensure_dir().join('song.mp3')
    config = {'--music-source': source_file.dirname, '--working-dir': str(tmpdir)}
    monkeypatch.setattr(control, 'GLOBAL_MUTABLE_CONFIG', config)
    if mode != 'none':
        HERE.join('1khz_sine.mp3').copy(source_file)

    # Run.
    loop = asyncio.get_event_loop()
    if mode == 'wait':
        nested_results = loop.run_until_complete(asyncio.wait([
            write_to_file_slowly(caplog, str(source_file)), control.scan_wait(loop)
        ]))
        songs, delete_files, remove_dirs = [s for s in nested_results[0] if s.result()][0].result()
    else:
        songs, delete_files, remove_dirs = loop.run_until_complete(control.scan_wait(loop))

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
