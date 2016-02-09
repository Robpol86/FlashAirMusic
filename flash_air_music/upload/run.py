"""Main functions/coroutines that fire directory walking, song uploads, file/dir deletion, and retry logic."""

import logging

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError
from flash_air_music.upload.discover import files_dirs_to_delete, get_songs
from flash_air_music.upload.interface import get_card_time_zone


def scan(ip_addr, shutdown_future):
    """Walk source and remote directories for new songs and files/dirs to delete. Get card timezone too.

    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param asyncio.Future shutdown_future: Shutdown signal.

    :return: 3 item tuple: Song instances (list), files/dirs to delete (set), timezone info.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    log.debug('Scanning for local and remote songs...')
    source_dir = GLOBAL_MUTABLE_CONFIG['--music-source']

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
