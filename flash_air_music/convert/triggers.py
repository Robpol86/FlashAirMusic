"""Main callers of convert functions/coroutines. Run indefinitely."""

import asyncio
import hashlib
import logging
import os

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.convert.discover import walk_source
from flash_air_music.convert.run import run
from flash_air_music.lib import SHUTDOWN

EVERY_SECONDS_PERIODIC = 60 * 60
EVERY_SECONDS_WATCH = 5 * 60


@asyncio.coroutine
def periodically_convert():
    """Call run() every EVERY_SECONDS_PERIODIC unless semaphore is locked."""
    log = logging.getLogger(__name__)
    while True:
        yield from run()
        log.debug('periodically_convert() sleeping %d seconds.', EVERY_SECONDS_PERIODIC)
        for _ in range(EVERY_SECONDS_PERIODIC):
            yield from asyncio.sleep(1)
            if SHUTDOWN.done():
                log.debug('periodically_convert() saw shutdown signal.')
                return
        log.debug('periodically_convert() waking up.')


@asyncio.coroutine
def watch_directory():
    """Watch directory by recursing into it every EVERY_SECONDS_WATCH.

    Compare size and mtimes between periods. Is responsible for converting on startup.
    """
    log = logging.getLogger(__name__)
    previous_hash = None
    array = bytearray()
    ramp_up = list(range(EVERY_SECONDS_WATCH, 15, -35))
    while True:
        sleep_for = ramp_up.pop() if ramp_up else EVERY_SECONDS_WATCH
        source_dir = GLOBAL_MUTABLE_CONFIG['--music-source']  # Keep in loop for when update_config() is called.
        for i in sorted((p, s.st_size, s.st_mtime) for p, s in ((p, os.stat(p)) for p in walk_source(source_dir))):
            array.extend(str(i).encode('utf-8'))
        current_hash = hashlib.md5(array).hexdigest()
        array.clear()
        if current_hash != previous_hash:
            log.debug('watch_directory() file system changed, calling run().')
            yield from run()
            previous_hash = current_hash
        else:
            log.debug('watch_directory() no change in file system, not calling run().')
        log.debug('watch_directory() sleeping %d seconds.', sleep_for)
        for _ in range(sleep_for):
            yield from asyncio.sleep(1)
            if SHUTDOWN.done():
                log.debug('watch_directory() saw shutdown signal.')
                return
        log.debug('watch_directory() waking up.')
