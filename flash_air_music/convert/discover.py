"""Walk directories looking for source/target music files.

Target mp3 files hold source metadata in their ID3 comment tags. Each mp3 file is like a little database of itself.
"""

import os

from flash_air_music.common.base_song import BaseSong
from flash_air_music.convert.id3_flac_tags import read_stored_metadata

VALID_SOURCE_EXTENSIONS = ('.flac', '.mp3')


class Song(BaseSong):
    """Holds information about one song. Handles source/destination file paths.

    :ivar dict live_metadata: Current metadata of source and target files.
    :ivar str source: Source file path (usually FLAC file).
    :ivar dict stored_metadata: Previously recorded metadata of source and target files stored in target file ID3 tag.
    :ivar str target: Target file path (mp3 file).
    """

    def _generate_target_path(self, source_dir, target_dir):
        """Generate self.target value.

        :param str source_dir: Root absolute source directory path.
        :param str target_dir: Root absolute target directory path.

        :return: Absolute target file path.
        :rtype: str
        """
        target_path_old_extension = os.path.join(target_dir, os.path.relpath(self.source, source_dir))
        return os.path.splitext(target_path_old_extension)[0] + '.mp3'

    def _refresh_stored_metadata(self):
        """Read metadata from long term storage location."""
        self.stored_metadata.update(read_stored_metadata(self.target))

    @property
    def changed(self):
        """Return True if the file changed since we last checked."""
        source_stat = os.stat(self.source)
        mtime = int(source_stat.st_mtime)
        size = int(source_stat.st_size)
        return self.live_metadata['source_mtime'] != mtime or self.live_metadata['source_size'] != size

    def refresh_live_metadata(self):
        """Read current file metadata of source and target file."""
        super().refresh_live_metadata()
        try:
            target_stat = os.stat(self.target)
            self.live_metadata['target_mtime'] = int(target_stat.st_mtime)
            self.live_metadata['target_size'] = int(target_stat.st_size)
        except FileNotFoundError:
            self.live_metadata['target_mtime'] = 0
            self.live_metadata['target_size'] = 0


def walk_source(source_dir):
    """Walk source directory and yield valid file paths.

    :param str source_dir: Source directory.

    :return: Yield file paths.
    :rtype: str
    """
    for path in (os.path.join(root, f) for root, _, files in os.walk(source_dir) for f in files):
        if os.path.splitext(path)[1].lower() in VALID_SOURCE_EXTENSIONS:
            yield path


def get_songs(source_dir, target_dir):
    """Walk source and target directories looking for files to convert.

    :param str source_dir: Source directory.
    :param str target_dir: Target directory.

    :return: Song instances that need conversion and list of all mp3 target files that need or don't need conversion.
    :rtype: tuple
    """
    source_dir = os.path.realpath(source_dir)
    target_dir = os.path.realpath(target_dir)
    valid_targets = list()
    songs = list()

    for path in walk_source(source_dir):
        song = Song(path, source_dir, target_dir)
        valid_targets.append(song.target)
        if song.needs_action:
            songs.append(song)

    return songs, valid_targets


def files_dirs_to_delete(target_dir, valid_targets):
    """Walk source and target directories looking for files to delete and empty directories to remove.

    :param str target_dir: Target directory.
    :param iter valid_targets: List of valid target files from get_songs().

    :return: Abandoned files to delete and empty directories to remove.
    :rtype: tuple
    """
    target_dir = os.path.realpath(target_dir)
    delete_files = set()
    remove_dirs = set()

    # Discover abandoned target files.
    for path in (os.path.join(root, f) for root, _, files in os.walk(target_dir) for f in files):
        if path in valid_targets:
            continue
        if path.lower().endswith('.mp3'):
            delete_files.add(path)

    # Discover empty directories.
    for root, files in ((r, {os.path.join(r, f) for f in fs}) for r, _, fs in os.walk(target_dir)):
        if root == target_dir:
            continue
        if not files:
            remove_dirs.add(root)
        elif not files - delete_files:
            remove_dirs.add(root)

    return delete_files, remove_dirs
