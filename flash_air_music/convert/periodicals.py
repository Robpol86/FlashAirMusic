"""Main callers of convert functions/coroutines. Run indefinitely."""

import asyncio
import logging

from flash_air_music.convert.run import run

EVERY_SECONDS_PERIODIC = 60 * 60


@asyncio.coroutine
def periodically_convert(loop, semaphore, shutdown_future):
    """Call run() every EVERY_SECONDS_PERIODIC unless semaphore is locked.

    :param loop: AsyncIO event loop object.
    :param asyncio.Semaphore semaphore: Semaphore() instance.
    :param asyncio.Future shutdown_future: Main process shutdown signal.
    """
    log = logging.getLogger(__name__)
    while True:
        if semaphore.locked():
            log.debug('Semaphore is locked, skipping this iteration.')
        else:
            yield from run(loop, semaphore, shutdown_future)
        log.debug('periodically_convert() sleeping %d seconds.', EVERY_SECONDS_PERIODIC)
        for _ in range(EVERY_SECONDS_PERIODIC):
            yield from asyncio.sleep(1, loop=loop)
            if shutdown_future.done():
                log.debug('periodically_convert() saw shutdown signal.')
                return
        log.debug('periodically_convert() waking up.')
