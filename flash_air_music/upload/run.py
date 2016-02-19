"""Main functions/coroutines that fire directory walking, song uploads, file/dir deletion, and retry logic."""

import asyncio
import logging
import time

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError, FlashAirURLTooLong
from flash_air_music.upload.discover import files_dirs_to_delete, get_songs
from flash_air_music.upload.interface import delete_files_dirs, get_card_time_zone, initialize_upload, upload_files

GIVE_UP_AFTER = 300  # Retry for 5 minutes when network errors occur (packet loss, etc).


def scan(ip_addr, shutdown_future):
    """Walk source and remote directories for new songs and files/dirs to delete. Get card timezone too.

    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param asyncio.Future shutdown_future: Shutdown signal.

    :return: 3 item tuple: Song instances (list), files/dirs to delete (set), timezone info.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    source_dir = GLOBAL_MUTABLE_CONFIG['--working-dir']
    log.debug('Scanning for local and remote songs in %s', source_dir)

    # First get timezone.
    try:
        tzinfo = get_card_time_zone(ip_addr)
    except FlashAirNetworkError:
        raise  # To be handled in caller.
    except FlashAirError:
        log.exception('Unexpected exception.')
        return list(), set(), None

    # Get songs to upload and items to delete.
    songs, valid_targets, files, empty_dirs = get_songs(source_dir, ip_addr, tzinfo, shutdown_future)
    delete_paths = files_dirs_to_delete(valid_targets, files, empty_dirs)

    return songs, delete_paths, tzinfo


def upload_cleanup(ip_addr, songs, delete_paths, tzinfo, shutdown_future):
    """Remove remote files/directories and upload new/changed songs. Upload smallest files first.

    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param iter songs: List of songs to upload.
    :param iter delete_paths: Set of files and/or directories to remote on the FlashAir card.
    :param datetime.timezone tzinfo: Timezone the card is set to.
    :param asyncio.Future shutdown_future: Shutdown signal.
    """
    log = logging.getLogger(__name__)
    files_attrs = [j[:3] for j in sorted((s.attrs for s in songs), key=lambda i: i[-1])]

    # Lock card to prevent host from making changes and copy helper Lua script.
    try:
        log.info('Preparing FlashAir card for changes.')
        initialize_upload(ip_addr, tzinfo)
        if delete_paths:
            log.info('Deleting %d file(s)/dir(s) on the FlashAir card.', len(delete_paths))
            delete_files_dirs(ip_addr, delete_paths, shutdown_future)
        if songs:
            log.info('Uploading %d song(s).', len(songs))
            upload_files(ip_addr, files_attrs, shutdown_future)
    except FlashAirURLTooLong:
        log.exception('Lua script path is too long for some reason???')
    except FlashAirNetworkError:
        raise  # To be handled in caller.
    except FlashAirError:
        log.exception('Unexpected exception.')


@asyncio.coroutine
def run(semaphore, ip_addr, shutdown_future):
    """Wait for semaphore and then try to run scan() and upload_cleanup() within GIVE_UP_AFTER. Retry on network error.

    :param asyncio.Semaphore semaphore: Semaphore() instance.
    :param str ip_addr: IP address of FlashAir to connect to.
    :param asyncio.Future shutdown_future: Shutdown signal.

    :return: If sync was successful.
    :rtype: bool
    """
    log = logging.getLogger(__name__)
    log.debug('Waiting for semaphore...')
    sleep_for = 2
    success = False
    changed = False
    with (yield from semaphore):
        log.debug('Got semaphore lock.')
        start_time = time.time()
        while time.time() - start_time < GIVE_UP_AFTER:
            if shutdown_future.done():
                log.info('Service shutdown initiated, stop trying to update FlashAir card.')
                break
            try:
                songs, delete_paths, tzinfo = scan(ip_addr, shutdown_future)
                if songs or delete_paths:
                    upload_cleanup(ip_addr, songs, delete_paths, tzinfo, shutdown_future)
                    changed = True
            except FlashAirNetworkError:
                log.warning('Lost connection to FlashAir card. Retrying in %s seconds...', sleep_for)
                yield from asyncio.sleep(sleep_for)
                sleep_for += 1
            else:
                success = True
                break
        else:
            log.error('Retried too many times, giving up.')
    log.debug('Released lock.')
    if changed:
        log.info('Done updating FlashAir card.')
    elif not success:
        log.error('Failed to fully update FlashAir card. Maybe next time.')
    else:
        log.info('No changes detected on FlashAir card.')
    return success
