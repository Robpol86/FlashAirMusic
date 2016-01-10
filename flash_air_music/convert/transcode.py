"""Convert files from one format to mp3, keeping metadata."""

import asyncio
import logging
import os
import signal
import time

from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG
from flash_air_music.convert.id3_flac_tags import write_stored_metadata

SLEEP_FOR = 1  # Seconds.
TIMEOUT = 5 * 60  # Seconds.


class Protocol(asyncio.SubprocessProtocol):
    """Handles process output."""

    def __init__(self, loop):
        """Constructor."""
        self.exit_future = asyncio.Future(loop=loop)
        self.stdout = bytearray()
        self.stderr = bytearray()

    def pipe_data_received(self, fd, data):
        """Receive program's output.

        :param int fd: File descriptor sending data.
        :param bytearray data: Data sent.
        """
        if fd == 2:
            self.stderr.extend(data)
        else:
            self.stdout.extend(data)

    def process_exited(self):
        """Called when process exits."""
        self.exit_future.set_result(True)


@asyncio.coroutine
def convert_file(loop, song):
    """Convert one file to mp3. Store metadata in ID3 comment tag.

    :param loop: AsyncIO event loop object.
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

    # Start process.
    log.info('Converting %s', os.path.basename(song.source))
    transport, protocol = yield from loop.subprocess_exec(lambda: Protocol(loop), *command, stdin=None)
    pid = transport.get_pid()

    # Wait for process to finish.
    log.debug('Process %d started with command %s with timeout %d.', pid, str(command), TIMEOUT)
    while not protocol.exit_future.done():
        log.debug('Process %d still running...', pid)
        if time.time() - start_time > TIMEOUT and timeout_signals:
            send_signal = timeout_signals.pop()
            log.warning('Timeout exceeded, sending signal %d to pid %d.', send_signal, pid)
            transport.send_signal(send_signal)
        yield from asyncio.sleep(SLEEP_FOR, loop=loop)
    yield from protocol.exit_future

    # Get results.
    transport.close()
    exit_status = transport.get_returncode()
    stdout = bytes(protocol.stdout)
    stderr = bytes(protocol.stderr)
    log.debug('Process %d exited %d', pid, exit_status)
    log.debug('Process %d stdout: %s', pid, stdout.decode('utf-8'))
    log.debug('Process %d stderr: %s', pid, stderr.decode('utf-8'))

    if not exit_status:
        log.debug('Storing metadata in %s', os.path.basename(song.target))
        write_stored_metadata(song)

    return song, command, exit_status
