"""Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.

Command line options override config file values.

TODO:
* Handle SIGHUP or whatever for re-reading config.

Usage:
    FlashAirMusic [options] run
    FlashAirMusic -h | --help
    FlashAirMusic -V | --version

Options:
    -c --config         Path YAML config file.
    -h --help           Show this screen.
    -l --log            Log to file. Will be rotated daily.
    -m --mac-addr       FlashAir MAC Address (DHCP sniffing).
    -q --quiet          Don't print anything to stdout/stderr.
    -s --music-source   Source directory containing FLAC/MP3s.
    -v --verbose        Debug logging.
    -V --version        Show version and exit.
    -w --working-dir    Working directory for converted music and other files.
"""

import logging
import os
import signal
import sys
import time

import pkg_resources
from docopt import docopt

from flash_air_music import exceptions, lib


def get_arguments(argv=None):
    """Get command line arguments.

    :param list argv: Command line argument list to process.

    :return: Parsed options.
    :rtype: dict
    """
    require = getattr(pkg_resources, 'require')  # Stupid linting error.
    project = [p for p in require('FlashAirMusic') if p.project_name == 'FlashAirMusic'][0]
    version = project.version
    return docopt(__doc__, argv=argv or sys.argv[1:], version=version)


def main():
    """Main function."""
    log = logging.getLogger(__name__)
    while True:
        log.info('Doing nothing.')
        time.sleep(5)


def shutdown(*_):
    """Cleanup and shut down the program.

    :param _: Ignored.
    """
    logging.info('Shutting down.')
    getattr(os, '_exit')(0)


def entry_point():
    """Entry-point from setuptools."""
    signal.signal(signal.SIGINT, shutdown)  # Properly handle Control+C
    config = get_arguments()
    lib.setup_logging(config)
    try:
        main()
    except exceptions.BaseError:
        logging.critical('Failure.')
        sys.exit(1)
