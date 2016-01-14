"""Main coroutines that fire directory walking, song conversion, file deletion, and directory removal."""

import asyncio
import logging
import os

from flash_air_music.configuration import CONVERTED_MUSIC_SUBDIR, GLOBAL_MUTABLE_CONFIG
from flash_air_music.convert.discover import files_dirs_to_delete, get_songs

CHANGE_WAIT = 0.5  # Seconds.


@asyncio.coroutine
def scan_wait(loop):
    """Walk source directory for new songs and wait until they're done being written to if needed.

    :param loop: AsyncIO event loop object.

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
        yield from asyncio.sleep(CHANGE_WAIT, loop=loop)
        changed = [s for s in songs if s.changed]
        if not changed:
            break
        for song in changed:
            log.debug('Size/mtime changed for %s', song.source)
            song.refresh_current_metadata()
        log.info('%d song%s still being written to, waiting %f second%s...',
                 len(changed), '' if len(changed) == 1 else 's',
                 CHANGE_WAIT, '' if CHANGE_WAIT == 1 else 's')

    return songs, delete_files, remove_dirs
