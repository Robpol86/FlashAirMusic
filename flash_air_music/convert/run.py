"""Main coroutines that fire directory walking, song conversion, file deletion, and directory removal."""

import asyncio
import logging
import os

from flash_air_music.configuration import CONVERTED_MUSIC_SUBDIR, GLOBAL_MUTABLE_CONFIG
from flash_air_music.convert.discover import files_dirs_to_delete, get_songs
from flash_air_music.convert.transcode import convert_songs

CHANGE_WAIT = 0.5  # Seconds.


@asyncio.coroutine
def scan_wait():
    """Walk source directory for new songs and wait until they're done being written to if needed.

    :return: 3 item tuple of lists: Song instances, files to delete, directories to remove.
    """
    log = logging.getLogger(__name__)
    log.debug('Scanning for new/changed songs...')
    source_dir = GLOBAL_MUTABLE_CONFIG['--music-source']
    target_dir = os.path.join(GLOBAL_MUTABLE_CONFIG['--working-dir'], CONVERTED_MUSIC_SUBDIR)
    songs, valid_targets = get_songs(source_dir, target_dir)
    delete_files, remove_dirs = files_dirs_to_delete(target_dir, valid_targets)

    # Log results.
    log.info('Found: %d new source song%s, %d orphaned target song%s, %d empty director%s.',
             len(songs), '' if len(songs) == 1 else 's',
             len(delete_files), '' if len(delete_files) == 1 else 's',
             len(remove_dirs), 'y' if len(remove_dirs) == 1 else 'ies')

    # Make sure files aren't still being written to.
    while songs:
        yield from asyncio.sleep(CHANGE_WAIT)
        changed = [s for s in songs if s.changed]
        if not changed:
            break
        for song in changed:
            log.debug('Size/mtime changed for %s', song.source)
            song.refresh_live_metadata()
        log.info('%d song%s still being written to, waiting %f second%s...',
                 len(changed), '' if len(changed) == 1 else 's',
                 CHANGE_WAIT, '' if CHANGE_WAIT == 1 else 's')

    return songs, delete_files, remove_dirs


@asyncio.coroutine
def convert_cleanup(loop, shutdown_future, songs, delete_files, remove_dirs):
    """Convert songs, delete abandoned songs in target directory, remove empty directories in target directory.

    :param loop: AsyncIO event loop object.
    :param asyncio.Future shutdown_future: Shutdown signal.
    :param songs: List of Song instances from scan_wait().
    :param delete_files: List of files to delete from scan_wait().
    :param remove_dirs: List of directories to delete from scan_wait().
    """
    log = logging.getLogger(__name__)
    if songs:
        yield from convert_songs(loop, shutdown_future, songs)
    for file_ in delete_files:
        log.info('Deleting %s', file_)
        try:
            os.remove(file_)
        except IOError:
            log.info('Failed to delete %s', file_)
    for dir_ in sorted(remove_dirs, reverse=True):
        log.info('Removing empty directory %s', dir_)
        try:
            os.rmdir(dir_)
        except IOError:
            log.info('Failed to remove %s', dir_)


@asyncio.coroutine
def run(loop, semaphore, shutdown_future):
    """Wait for semaphore before running scan_convert_cleanup().

    :param loop: AsyncIO event loop object.
    :param asyncio.Semaphore semaphore: Semaphore() instance.
    :param asyncio.Future shutdown_future: Shutdown signal.
    """
    log = logging.getLogger(__name__)
    log.debug('Waiting for semaphore...')
    with (yield from semaphore):
        log.debug('Got semaphore lock.')
        songs, delete_files, remove_dirs = yield from scan_wait()
        if any([songs, delete_files, remove_dirs]):
            yield from convert_cleanup(loop, shutdown_future, songs, delete_files, remove_dirs)
    log.debug('Released lock.')
