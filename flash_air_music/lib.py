"""Holds common objects used throughout the project."""

import asyncio
import os

SEMAPHORE = asyncio.Semaphore()  # Main semaphore shared by convert and upload coroutines/functions.
SHUTDOWN = asyncio.Future()  # Signals service shutdown if future has result.


class BaseSong(object):
    """Base class to be subclassed by local and remote Song classes."""

    def __init__(self, source, source_dir, target_dir):
        """Constructor.

        :param str source: Absolute source file path.
        :param str source_dir: Root absolute source directory path.
        :param str target_dir: Root absolute target directory path.
        """
        self.live_metadata = dict()
        self.source = source
        self.stored_metadata = dict()
        self.target = self._generate_target_path(source_dir, target_dir)
        self.refresh_live_metadata()
        self._refresh_stored_metadata()

    def __repr__(self):
        """repr() handler."""
        return '<{} name={} needs_action={}>'.format(self.__class__.__name__, self.name, self.needs_action)

    def _generate_target_path(self, source_dir, target_dir):
        """Generate self.target value.

        :param str source_dir: Root absolute source directory path.
        :param str target_dir: Root absolute target directory path.

        :return: Absolute target file path.
        :rtype: str
        """
        raise NotImplementedError  # pragma: no cover

    def _refresh_stored_metadata(self):
        """Read metadata from long term storage location."""
        raise NotImplementedError  # pragma: no cover

    @property
    def name(self):
        """Return basename of source file."""
        return os.path.basename(self.source)

    @property
    def needs_action(self):
        """Skip file if nothing has changed."""
        return self.live_metadata != self.stored_metadata

    def refresh_live_metadata(self):
        """Read current metadata of local file(s) right now."""
        source_stat = os.stat(self.source)
        self.live_metadata['source_mtime'] = int(source_stat.st_mtime)
        self.live_metadata['source_size'] = int(source_stat.st_size)
