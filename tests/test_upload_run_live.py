"""Test functions in module on a real live FlashAir card."""

import asyncio
import logging
import os
import time

import pytest

from flash_air_music.__main__ import __doc__ as doc
from flash_air_music.configuration import initialize_config, REGEX_IP_ADDR
from flash_air_music.upload import run
from tests import HERE

IP_ADDR = os.environ.get('FAM_TEST_IP_ADDR', '')
pytestmark = pytest.mark.skipif(str(not REGEX_IP_ADDR.match(IP_ADDR)))
TARGET_DIR = '/TEST_{}'.format(int(time.time()))


@pytest.fixture(autouse=True)
def initialize(monkeypatch, tmpdir_module):
    """Setup environment before every test function.

    :param monkeypatch: pytest fixture.
    :param tmpdir_module: conftest fixture.
    """
    monkeypatch.setattr('flash_air_music.configuration.setup_logging', lambda _: None)
    monkeypatch.setattr('flash_air_music.upload.discover.REMOTE_ROOT_DIRECTORY', TARGET_DIR)
    monkeypatch.setattr('flash_air_music.upload.interface.REMOTE_ROOT_DIRECTORY', TARGET_DIR)
    monkeypatch.setattr('flash_air_music.upload.run.GIVE_UP_AFTER', 15)
    monkeypatch.setattr('sys.argv', ['FlashAirMusic', 'run'])
    monkeypatch.setenv('HOME', tmpdir_module)
    if not tmpdir_module.join('fam_working_dir').check():
        tmpdir_module.ensure_dir('fam_working_dir')
        HERE.join('1khz_sine_2.mp3').copy(tmpdir_module.ensure('fam_music_source', 'song1.mp3'))
        initialize_config(doc)


def test_scan_empty(caplog):
    """Test new/empty test directory.

    :param caplog: pytest extension fixture.
    """
    songs, delete_paths, tzinfo = run.scan(IP_ADDR, asyncio.Future())
    assert [s.target for s in songs] == [TARGET_DIR + '/song1.mp3']
    assert not delete_paths
    assert tzinfo

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    errors = [r.message for r in caplog.records if r.name.startswith('flash_air_music') and r.levelno > logging.INFO]
    assert not errors
    assert 'Directory {} does not exist on FlashAir card.'.format(TARGET_DIR) in messages


def test_run_upload_one(tmpdir_module, caplog):
    """Upload one songs in the root directory and verify everything is ok so far. Use the run() coroutine.

    :param caplog: pytest extension fixture.
    :param tmpdir_module: conftest fixture.
    """
    # Run.
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(run.run(asyncio.Semaphore(), IP_ADDR, asyncio.Future()))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    errors = [r.message for r in caplog.records if r.name.startswith('flash_air_music') and r.levelno > logging.INFO]

    # Check logs.
    assert not errors
    actual = [m for m in messages if m.startswith('Uploading file: ')]
    expected = ['Uploading file: {}'.format(tmpdir_module.join('fam_music_source', 'song1.mp3'))]
    assert actual == expected
    actual = [m for m in messages if m.startswith('Deleting: ')]
    assert not actual
    assert 'Done updating FlashAir card.' in messages
    assert success

    # Verify consistency.
    songs, delete_paths = run.scan(IP_ADDR, asyncio.Future())[:2]
    assert not songs
    assert not delete_paths


def test_run_upload_subdir(tmpdir_module, caplog):
    """Now upload more files in subdirectories.

    :param caplog: pytest extension fixture.
    :param tmpdir_module: conftest fixture.
    """
    tmpdir_module.ensure('fam_music_source', 'song2.mp3').write('a' * 100)
    tmpdir_module.ensure('fam_music_source', 'subdir1', 'song3.mp3').write('a' * 50)
    tmpdir_module.ensure('fam_music_source', 'subdir2', 'a', 'b', 'c', 'song4.mp3').write('a' * 10)

    # Run.
    loop = asyncio.get_event_loop()
    success = loop.run_until_complete(run.run(asyncio.Semaphore(), IP_ADDR, asyncio.Future()))
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    errors = [r.message for r in caplog.records if r.name.startswith('flash_air_music') and r.levelno > logging.INFO]

    # Check logs.
    assert not errors
    actual = [m for m in messages if m.startswith('Uploading file: ')]
    expected = [
        'Uploading file: {}'.format(tmpdir_module.join('fam_music_source', 'subdir2', 'a', 'b', 'c', 'song4.mp3')),
        'Uploading file: {}'.format(tmpdir_module.join('fam_music_source', 'subdir1', 'song3.mp3')),
        'Uploading file: {}'.format(tmpdir_module.join('fam_music_source', 'song2.mp3')),
    ]
    assert actual == expected
    actual = [m for m in messages if m.startswith('Deleting: ')]
    assert not actual
    assert 'Done updating FlashAir card.' in messages
    assert success

    # Verify consistency.
    songs, delete_paths = run.scan(IP_ADDR, asyncio.Future())[:2]
    assert not songs
    assert not delete_paths


def test_delete_and_spaces(tmpdir_module, caplog):
    """Test file/dir deletion and spaces in file paths.

    :param caplog: pytest extension fixture.
    :param tmpdir_module: conftest fixture.
    """
    tmpdir_module.remove(rec=True)
    tmpdir_module.ensure_dir()
    HERE.join('1khz_sine_2.mp3').copy(tmpdir_module.ensure('fam_music_source', 'Cool Artist', 'Cool Artist - 1994.mp3'))

    # Run multiple times for directory removal.
    for i in range(5, -1, -1):
        # Run.
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(run.run(asyncio.Semaphore(), IP_ADDR, asyncio.Future()))
        messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
        errors = [r.message for r in caplog.records if r.name.startswith('flash_air_mus') and r.levelno > logging.INFO]

        # Check logs.
        assert not errors
        if i:  # Not done yet.
            assert messages[-1] == 'Done updating FlashAir card.'
        else:  # 0, last iter.
            assert messages[-1] == 'No changes detected on FlashAir card.'
        assert success

        # Verify consistency.
        songs, delete_paths = run.scan(IP_ADDR, asyncio.Future())[:2]
        assert not songs
        if i not in (1, 0):
            assert delete_paths
        else:
            assert not delete_paths
