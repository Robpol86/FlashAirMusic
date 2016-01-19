"""Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.

Command line options overridden by config file values.

Usage:
    FlashAirMusic [options] run
    FlashAirMusic -h | --help
    FlashAirMusic -V | --version

Options:
    -c FILE --config=FILE       Path YAML config file.
    -f FILE --ffmpeg-bin=FILE   File path to ffmpeg binary.
    -h --help                   Show this screen.
    -l FILE --log=FILE          Log to file. Will be rotated daily.
    -m ADDR --mac-addr=ADDR     FlashAir MAC Address (DHCP sniffing).
    -q --quiet                  Don't print anything to stdout/stderr.
    -s DIR --music-source=DIR   Source directory containing FLAC/MP3s.
    -t NUM --threads=NUM        File conversion worker count [default: 0].
                                0 is one worker per CPU.
    -v --verbose                Debug logging.
    -V --version                Show version and exit.
    -w DIR --working-dir=DIR    Working directory for converted music, etc.
"""

import asyncio
import logging
import signal
import sys
import time

from flash_air_music.configuration import initialize_config, SIGNALS_INT_TO_NAME, update_config
from flash_air_music.exceptions import BaseError


def main():
    """Main function."""
    log = logging.getLogger(__name__)
    while True:
        log.info('Doing nothing (info).')
        log.debug('Doing nothing (debug).')
        time.sleep(0.5)


def shutdown_old(*_):
    """Cleanup and shut down the program.

    :param _: Ignored.
    """
    log = logging.getLogger(__name__)
    log.info('Shutting down.')
    sys.exit(0)


@asyncio.coroutine
def shutdown(signum, shutdown_future):
    """Cleanup and shut down the program.

    :param int signum: Signal caught.
    :param asyncio.Future shutdown_future: Signals process shutdown to periodic coroutines.
    """
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Shutting down.', signum, '/'.join(SIGNALS_INT_TO_NAME[signum]))
    shutdown_future.set_result(signum)


def entry_point():
    """Entry-point from setuptools."""
    signal.signal(signal.SIGINT, shutdown_old)
    signal.signal(signal.SIGTERM, shutdown_old)
    try:
        initialize_config(doc=__doc__)
        signal.signal(signal.SIGHUP, update_config)
        main()
    except BaseError:
        logging.critical('Failure.')
        sys.exit(1)
