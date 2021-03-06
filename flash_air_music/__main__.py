"""Convert FLAC music and sync it to a FlashAir WiFI SD card.

Command line options overridden by config file values.

Usage:
    {program} [options] run
    {program} -h | --help
    {program} -V | --version

Options:
    -c FILE --config=FILE       Path to INI config file.
    -f FILE --ffmpeg-bin=FILE   File path to ffmpeg binary.
                                [default: {ffmpeg_default}]
    -h --help                   Show this screen.
    -i ADDR --ip-addr=ADDR      FlashAir hostname/IP address.
    -l FILE --log=FILE          Log to file. Will be rotated daily.
    -q --quiet                  Don't print anything to stdout/stderr.
    -s DIR --music-source=DIR   Source directory containing FLAC/MP3s.
                                [default: ~/fam_music_source]
    -t NUM --threads=NUM        File conversion worker count [default: 0].
                                0 is one worker per CPU.
    -v --verbose                Debug logging.
    -V --version                Show version and exit.
    -w DIR --working-dir=DIR    Working directory for converted music, etc.
                                [default: ~/fam_working_dir]
"""

import asyncio
import logging
import signal
import sys

from flash_air_music.configuration import initialize_config, SIGNALS_INT_TO_NAME, update_config
from flash_air_music.convert.triggers import EVERY_SECONDS_PERIODIC, periodically_convert, watch_directory
from flash_air_music.exceptions import BaseError
from flash_air_music.lib import SHUTDOWN
from flash_air_music.upload.triggers import watch_for_flashair


def main():
    """Main function."""
    log = logging.getLogger(__name__)
    loop = asyncio.get_event_loop()

    log.info('Scheduling signal handlers.')
    loop.add_signal_handler(signal.SIGHUP, update_config, __doc__, signal.SIGHUP)
    loop.add_signal_handler(signal.SIGINT, loop.create_task, shutdown(loop, signal.SIGINT, True))
    loop.add_signal_handler(signal.SIGTERM, loop.create_task, shutdown(loop, signal.SIGTERM, True))

    log.info('Scheduling periodic tasks.')
    loop.call_later(EVERY_SECONDS_PERIODIC, loop.create_task, periodically_convert())
    loop.create_task(watch_directory())
    loop.create_task(watch_for_flashair())

    log.info('Running main loop.')
    loop.run_forever()
    loop.close()
    log.info('Main loop has exited.')


@asyncio.coroutine
def shutdown(loop, signum, stop_loop=False):
    """Cleanup and shut down the program.

    :param loop: AsyncIO event loop object.
    :param int signum: Signal caught.
    :param bool stop_loop: Stop the event loop after tasks complete or 5 seconds pass.
    """
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Shutting down.', signum, '/'.join(SIGNALS_INT_TO_NAME[signum]))
    SHUTDOWN.set_result(signum)
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
