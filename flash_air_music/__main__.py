"""Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.

Command line options overridden by config file values.

Usage:
    FlashAirMusic [options] run
    FlashAirMusic -h | --help
    FlashAirMusic -V | --version

Options:
    -c FILE --config=FILE       Path YAML config file.
    -h --help                   Show this screen.
    -l FILE --log=FILE          Log to file. Will be rotated daily.
    -m ADDR --mac-addr=ADDR     FlashAir MAC Address (DHCP sniffing).
    -q --quiet                  Don't print anything to stdout/stderr.
    -s DIR --music-source=DIR   Source directory containing FLAC/MP3s.
    -v --verbose                Debug logging.
    -V --version                Show version and exit.
    -w DIR --working-dir=DIR    Working directory for converted music, etc.
"""

import logging
import os
import signal
import sys
import time

from flash_air_music import configuration, exceptions


def main():
    """Main function."""
    log = logging.getLogger(__name__)
    while True:
        log.info('Doing nothing (info).')
        log.debug('Doing nothing (debug).')
        time.sleep(0.5)


def shutdown(*_):
    """Cleanup and shut down the program.

    :param _: Ignored.
    """
    log = logging.getLogger(__name__)
    log.info('Shutting down.')
    getattr(os, '_exit')(0)


def entry_point():
    """Entry-point from setuptools."""
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        configuration.update_config(doc=__doc__)
        signal.signal(signal.SIGHUP, configuration.update_config)
        main()
    except exceptions.BaseError:
        logging.critical('Failure.')
        sys.exit(1)
