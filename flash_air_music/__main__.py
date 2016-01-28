"""Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.

Command line options overridden by config file values.

Usage:
    FlashAirMusic [options] run
    FlashAirMusic -h | --help
    FlashAirMusic -V | --version

Options:
    -c FILE --config=FILE       Path to INI config file.
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

from flash_air_music.configuration import initialize_config, SIGNALS_INT_TO_NAME, update_config
from flash_air_music.convert.periodicals import EVERY_SECONDS_PERIODIC, periodically_convert, watch_directory
from flash_air_music.exceptions import BaseError


def main():
    """Main function."""
    log = logging.getLogger(__name__)
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore()
    shutdown_future = asyncio.Future()

    log.info('Scheduling signal handlers.')
    loop.add_signal_handler(signal.SIGHUP, update_config, __doc__, signal.SIGHUP)
    loop.add_signal_handler(signal.SIGINT, loop.create_task, shutdown(loop, signal.SIGINT, shutdown_future, True))
    loop.add_signal_handler(signal.SIGTERM, loop.create_task, shutdown(loop, signal.SIGTERM, shutdown_future, True))

    log.info('Scheduling periodic tasks.')
    loop.call_later(EVERY_SECONDS_PERIODIC, loop.create_task, periodically_convert(loop, semaphore, shutdown_future))
    loop.create_task(watch_directory(loop, semaphore, shutdown_future))

    log.info('Running main loop.')
    loop.run_forever()
    loop.close()
    log.info('Main loop has exited.')


@asyncio.coroutine
def shutdown(loop, signum, shutdown_future, stop_loop=False):
    """Cleanup and shut down the program.

    :param loop: AsyncIO event loop object.
    :param int signum: Signal caught.
    :param asyncio.Future shutdown_future: Signals process shutdown to periodic coroutines.
    :param bool stop_loop: Stop the event loop after tasks complete or 5 seconds pass.
    """
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Shutting down.', signum, '/'.join(SIGNALS_INT_TO_NAME[signum]))
    shutdown_future.set_result(signum)
    if stop_loop:
        loop.create_task(stop(loop))


@asyncio.coroutine
def stop(loop):
    """Wait up to 5 seconds for tasks to cleanup before stopping event loop.

    :param loop: AsyncIO event loop object.
    """
    log = logging.getLogger(__name__)
    log.info('Waiting up to 5 seconds for tasks to cleanup.')

    this_task = asyncio.Task.current_task()
    for _ in range(50):
        yield from asyncio.sleep(0.1)
        running_tasks = [t for t in asyncio.Task.all_tasks() if not t.done() and t != this_task]
        if not running_tasks:
            break
    log.info('Stopping loop.')
    loop.stop()


def entry_point():
    """Entry-point from setuptools."""
    try:
        initialize_config(__doc__)
        main()
    except BaseError:
        logging.critical('Failure.')
        sys.exit(1)
