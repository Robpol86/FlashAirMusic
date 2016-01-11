"""Walk directories looking for source/target music files.

Target mp3 files hold source metadata in their ID3 comment tags. Each mp3 file is like a little database of itself.
"""

import os

from flash_air_music.convert.id3_flac_tags import read_stored_metadata

VALID_SOURCE_EXTENSIONS = ('.flac', '.mp3')


class Song(object):
    """Holds information about one song. Handles source/destination file paths.

    :ivar str source: Source file path (usually FLAC file).
    :ivar str target: Target file path (mp3 file).
    :ivar dict previous_metadata: Previously recorded metadata of source and target files stored in target file ID3 tag.
    :ivar dict current_metadata: Current metadata of soruce and target files.
    """

    def __init__(self, source, source_dir, target_dir):
        """Constructor."""
        self.source = source

        # Determine target path.
        target_path_old_extension = os.path.join(target_dir, os.path.relpath(source, source_dir))
        self.target = os.path.splitext(target_path_old_extension)[0] + '.mp3'

        # Read previous metadata from target file.
        self.previous_metadata = read_stored_metadata(self.target)
        self.current_metadata = dict()
        self.refresh_current_metadata()

    def __repr__(self):
        """repr() handler."""
        return '<{}.{} name={} needs_conversion={}>'.format(
            self.__class__.__module__,
            self.__class__.__name__,
            self.name, self.needs_conversion,
        )

    @property
    def name(self):
        """Return basename of source file."""
        return os.path.basename(self.source)

    @property
    def needs_conversion(self):
        """Skip file if nothing has changed."""
        return self.previous_metadata != self.current_metadata

    def refresh_current_metadata(self):
        """Read current file metadata of source and target file."""
        source_stat = os.stat(self.source)
        self.current_metadata['source_mtime'] = int(source_stat.st_mtime)
        self.current_metadata['source_size'] = int(source_stat.st_size)
        try:
            target_stat = os.stat(self.target)
            self.current_metadata['target_mtime'] = int(target_stat.st_mtime)
            self.current_metadata['target_size'] = int(target_stat.st_size)
        except FileNotFoundError:
            self.current_metadata['target_mtime'] = 0
            self.current_metadata['target_size'] = 0


def get_songs(source_dir, target_dir):
    """Walk source and target directories looking for files to convert.

    :param str source_dir: Source directory.
    :param str target_dir: Target directory.

    :return: Song instances that need conversion and list of all mp3 targets targets that need or don't need conversion.
    """
    source_dir = os.path.realpath(source_dir)
    target_dir = os.path.realpath(target_dir)
    valid_targets = list()
    songs = list()

    for path in (os.path.join(root, f) for root, _, files in os.walk(source_dir) for f in files):
        if os.path.splitext(path)[1].lower() not in VALID_SOURCE_EXTENSIONS:
            continue
        song = Song(path, source_dir, target_dir)
        valid_targets.append(song.target)
        if song.needs_conversion:
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
