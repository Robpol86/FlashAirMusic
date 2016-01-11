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
    log.info('Converting %s', song.name)
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

    # Cleanup or finalize.
    if exit_status:
        log.error('Failed to convert %s! ffmpeg exited %d.', song.name, exit_status)
        log.error('Error output of %s: %s', str(command), stderr.decode('utf-8'))
        if os.path.isfile(song.target):
            log.error('Removing %s', song.target)
            os.remove(song.target)
    else:
        log.debug('Storing metadata in %s', os.path.basename(song.target))
        write_stored_metadata(song)

    return song, command, exit_status


@asyncio.coroutine
def run(semaphore, loop, song):
    """Wait for semaphore before running convert_file().

    :param asyncio.Semaphore semaphore: Semaphore() instance.
    :param loop: AsyncIO event loop object.
    :param flash_air_music.convert.discover.Song song: Song instance.

    :return: convert_file() return value.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    log.debug('%s: waiting for semaphore...', song.name)
    try:
        with (yield from semaphore):
            log.debug('%s: got semaphore lock.', song.name)
            return (yield from convert_file(loop, song))
    finally:
        log.debug('%s: released lock.', song.name)


@asyncio.coroutine
def convert_songs(loop, songs):
    """Convert all songs concurrently.

    :param loop: AsyncIO event loop object.
    :param iter songs: List of Song instances.
    """
    log = logging.getLogger(__name__)
    workers = int(GLOBAL_MUTABLE_CONFIG['--threads']) or os.cpu_count()
    conversion_semaphore = asyncio.Semaphore(workers)

    # Execute all.
    log.info('Beginning to convert %d file(s) up to %d at a time.', len(songs), workers)
    nested_results = yield from asyncio.wait([run(conversion_semaphore, loop, s) for s in songs])
    results = [t for s in nested_results for t in s]
    succeeded = [t for t in (r.result() for r in results if not r.exception()) if t[-1] == 0]
    log.info('Done converting %d file(s) (%d failed).', len(results), len(results) - len(succeeded))

    # Look for exceptions.
    for future in (r for r in results if r.exception()):
        # noinspection PyBroadException
        try:
            future.result()
        except Exception:  # pylint: disable=broad-except
            log.exception('BUG! Exception raised in coroutine.')
