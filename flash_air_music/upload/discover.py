"""Walk local and remote directories looking for music files."""

import logging
import os
import unicodedata

from flash_air_music.base_song import BaseSong
from flash_air_music.exceptions import FlashAirDirNotFoundError, FlashAirError, FlashAirNetworkError, FlashAirURLTooLong
from flash_air_music.upload.interface import DO_NOT_DELETE, epoch_to_ftime, get_files, REMOTE_ROOT_DIRECTORY

MAX_LENGTH = 255
TRANS_TABLE = str.maketrans(r'&<>:"\|?*', "+() '  . ")
WHITE_LIST = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!#$%'()+,-;=@]^_`{}~./"


class Song(BaseSong):
    """Holds information about one song, locally and on the FlashAir card. Handles source/destination file paths.

    :ivar dict live_metadata: Current metadata of source file.
    :ivar str source: Source file path (local MP3 file).
    :ivar dict stored_metadata: Metadata of remote file on FlashAir card.
    :ivar str target: Target file path (absolute remote path to mp3 file).
    """

    def __init__(self, source, source_dir, target_dir, remote_metadata, tzinfo):
        """Constructor.

        :param str source: Absolute source file path.
        :param str source_dir: Root absolute source directory path.
        :param str target_dir: Root absolute target directory path.
        :param dict remote_metadata: File paths and file metadata from the FlashAir API [from get_remote_songs()].
        :param datetime.timezone tzinfo: Timezone the card is set to.
        """
        self.remote_metadata = remote_metadata
        self.tzinfo = tzinfo
        super().__init__(source, source_dir, target_dir)

    def _generate_target_path(self, source_dir, target_dir):
        """Determine target path and translate invalid characters to valid ones. All paths are absolute.

        :param str source_dir: Local source directory.
        :param str target_dir: Remote target directory.

        :return: FlashAir safe path.
        :rtype: str
        """
        target = os.path.join(target_dir, os.path.relpath(self.source, source_dir))

        # Translate special characters.
        target = unicodedata.normalize('NFKD', target).encode('ASCII', 'ignore').decode('ASCII')

        # Translate invalid ASCII characters.
        target = target.translate(TRANS_TABLE)

        # Last resort.
        target = ''.join(i for i in target if i in WHITE_LIST)

        # Shorten long paths.
        if len(target) > MAX_LENGTH:
            for truncate in range(MAX_LENGTH - 10, 1, -10):
                target = '/'.join(p[:truncate] for p in os.path.splitext(target)[0].split('/')) + '.mp3'
                if len(target) <= MAX_LENGTH:
                    break

        return target

    def _refresh_stored_metadata(self):
        """Read metadata from FlashAir remote_metadata dict."""
        if self.target not in self.remote_metadata:
            return
        remote_metadata = self.remote_metadata[self.target]
        self.stored_metadata['source_size'] = int(remote_metadata[0])
        self.stored_metadata['source_mtime'] = int(remote_metadata[1]) & ~1

    @property
    def attrs(self):
        """Return attributes of this song expected by upload.upload_files(). Include extra item for sorting."""
        mtime = epoch_to_ftime(self.live_metadata['source_mtime'], self.tzinfo)
        return self.source, self.target, mtime, self.live_metadata['source_size']

    def refresh_live_metadata(self):
        """Need to make number even due to half a second precision loss with FILETIME conversion."""
        super().refresh_live_metadata()
        self.live_metadata['source_mtime'] &= ~1  # http://stackoverflow.com/a/22154943/1198943


def walk_source(source_dir):
    """Walk source directory and yield valid file paths.

    :param str source_dir: Source directory.

    :return: Yield file paths.
    :rtype: str
    """
    for path in (os.path.join(root, f) for root, _, files in os.walk(source_dir) for f in files):
        if os.path.splitext(path)[1].lower() == '.mp3':
            yield path


def get_songs(source_dir, ip_addr, tzinfo, shutdown_future):
    """Walk local source and remote target directories looking for files to transfer.

    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str source_dir: Source directory.
    :param str ip_addr: IP address of FlashAir to connect to.
    :param datetime.timezone tzinfo: Timezone the card is set to.
    :param asyncio.Future shutdown_future: Shutdown signal.

    :return: Song instances, valid remote target files, all remote target files, and empty remote directories.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    target_dir = REMOTE_ROOT_DIRECTORY
    valid_targets = list()
    songs = list()

    # First get remote files.
    try:
        files, empty_dirs = get_files(ip_addr, tzinfo, REMOTE_ROOT_DIRECTORY, shutdown_future)
    except FlashAirNetworkError:
        raise  # To be handled (retired) in caller.
    except FlashAirDirNotFoundError:
        log.debug('Directory %s does not exist on FlashAir card.', REMOTE_ROOT_DIRECTORY)
        files, empty_dirs = dict(), list()
    except FlashAirURLTooLong:
        log.exception('Got FlashAirURLTooLong, is %s too long?', REMOTE_ROOT_DIRECTORY)
        return songs, valid_targets, dict(), list()
    except FlashAirError:
        log.exception('Unexpected exception.')
        return songs, valid_targets, dict(), list()
    if shutdown_future.done():
        return songs, valid_targets, dict(), list()

    # Get local files.
    for path in walk_source(source_dir):
        song = Song(path, source_dir, target_dir, files, tzinfo)
        valid_targets.append(song.target)
        if song.needs_action:
            songs.append(song)

    # Prune empty_dirs.
    empty_dirs = [p for p in empty_dirs if p.rstrip('/') not in DO_NOT_DELETE]

    return songs, valid_targets, files, empty_dirs


def files_dirs_to_delete(valid_targets, files, empty_dirs):
    """Compare local and remote directory trees looking for files to delete. Combine with empty dirs from get_songs().

    :param iter valid_targets: List of valid target files from get_songs().
    :param iter files: List/dict keys of all files on the FlashAir card.
    :param iter empty_dirs: List of empty directories on the FlashAir card to remove.

    :return: Set of abandoned files to delete and empty directories to remove. One API call deletes either.
    :rtype: set
    """
    delete_files_dirs = set(empty_dirs)
    for path in files:
        if path in valid_targets:
            continue
        if path.lower().endswith('.mp3'):
            delete_files_dirs.add(path)
    return delete_files_dirs
