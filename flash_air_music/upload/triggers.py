"""Main callers of upload functions/coroutines. Run indefinitely."""

import asyncio
import logging
from socket import error, socket

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.lib import SHUTDOWN
from flash_air_music.upload.run import run

EVERY_SECONDS_CHECK = 5
SUCCESS_SLEEP = 5 * 60


@asyncio.coroutine
def watch_for_flashair():
    """Try to connect to FlashAir card every EVERY_SECONDS_CHECK. Runs coroutine if card responds."""
    log = logging.getLogger(__name__)

    while True:
        sleep_for = EVERY_SECONDS_CHECK

        # Check if card is reachable.
        if GLOBAL_MUTABLE_CONFIG['--ip-addr']:
            try:
                with socket() as sock:
                    sock.connect((GLOBAL_MUTABLE_CONFIG['--ip-addr'], 80))
            except error:
                success = False
            else:
                log.debug('%s is reachable. calling run().', GLOBAL_MUTABLE_CONFIG['--ip-addr'])
                success = yield from run(GLOBAL_MUTABLE_CONFIG['--ip-addr'])
        else:
            log.debug('No IP address specified. Skipping watch_for_flashair().')
            success = True

        # Sleep longer if successful.
        if success:
            sleep_for = SUCCESS_SLEEP

        # Sleep.
        for _ in range(sleep_for):
            if SHUTDOWN.done():
                log.debug('watch_for_flashair() saw shutdown signal.')
                return
            yield from asyncio.sleep(1)
