"""Convert files from one format to mp3, keeping metadata."""

import asyncio
import logging
import os
import signal
import time
from subprocess import DEVNULL, Popen

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.convert.id3_flac_tags import write_stored_metadata

SLEEP_FOR = 1  # Seconds.
TIMEOUT = 5 * 60  # Seconds.


@asyncio.coroutine
def convert_file(song):
    """Convert one file to mp3. Store metadata in ID3 comment tag.

    :param flash_air_music.convert.discover.Song song: Song instance.

    :return: Same Song instance, command, and exit status of command.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    start_time = time.time()
    timeout_signals = [signal.SIGKILL, signal.SIGTERM, signal.SIGINT]  # reverse order.
    command = [
        GLOBAL_MUTABLE_CONFIG['--ffmpeg-bin'],
        '-i', song.source,
        '-codec:a', 'libmp3lame',
        '-id3v2_version', '3',
        '-map_metadata', '0',
        '-qscale:a', '0',
        '-y', '-sn', '-vn',
        song.target,
    ]

    log.info('Converting %s', os.path.basename(song.source))
    with Popen(command, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL) as process:
        log.debug('Process %d started with command %s with timeout %d.', process.pid, str(command), TIMEOUT)
        while process.poll() is None:
            log.debug('Process %d still running...', process.pid)
            if time.time() - start_time > TIMEOUT and timeout_signals:
                send_signal = timeout_signals.pop()
                log.warning('Timeout exceeded, sending signal %d to pid %d.', send_signal, process.pid)
                process.send_signal(send_signal)
            yield from asyncio.sleep(SLEEP_FOR)
        exit_status = process.poll()
        log.debug('Process %d exited %d', process.pid, exit_status)

    if not exit_status:
        log.debug('Storing metadata in %s', os.path.basename(song.target))
        write_stored_metadata(song)

    return song, command, exit_status
