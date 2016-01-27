"""Handles reading configuration from command line or file and storing it in a global mutable dictionary."""

import logging
import os
import re
import signal
from distutils.spawn import find_executable

import pkg_resources
from docoptcfg import docoptcfg, DocoptcfgFileError

from flash_air_music.exceptions import ConfigError
from flash_air_music.setup_logging import setup_logging

CONVERTED_MUSIC_SUBDIR = 'converted_music'
DEFAULT_FFMPEG_BINARY = find_executable('ffmpeg')
DEFAULT_WORKING_DIR = os.path.join(os.environ['HOME'], 'FlashAirMusicWorkingDir')
SIGNALS_INT_TO_NAME = {v: {a for a, b in vars(signal).items() if a.startswith('SIG') and b == v}
                       for k, v in vars(signal).items() if k.startswith('SIG')}
GLOBAL_MUTABLE_CONFIG = dict()
REGEX_MAC_ADDR = re.compile(r'^(?:[a-fA-F0-9]{2}[ :-]?){5}[a-fA-F0-9]{2}$')


def _get_arguments(doc):
    """Get command line arguments.

    :param str doc: Docstring to pass to docopt.

    :return: Parsed options.
    :rtype: dict
    """
    require = getattr(pkg_resources, 'require')  # Stupid linting error.
    project = [p for p in require('FlashAirMusic') if p.project_name == 'FlashAirMusic'][0]
    version = project.version
    return docoptcfg(doc, config_option='--config', env_prefix='FAM_', version=version)


def _validate_config(config):  # pylint:disable=too-many-branches
    """Validate config data.

    :raise flash_air_music.exceptions.ConfigError: On invalid data.

    :param dict config: Configuration dict to validate.
    """
    # --log
    if config['--log']:
        parent = os.path.dirname(config['--log']) or os.getcwd()
        if not os.path.isdir(parent):
            logging.getLogger(__name__).error('Log file parent directory %s not a directory.', parent)
            raise ConfigError
        if not os.access(parent, os.W_OK | os.X_OK):
            logging.getLogger(__name__).error('Log file parent directory %s not writable.', parent)
            raise ConfigError
        if os.path.exists(config['--log']) and not os.access(config['--log'], os.R_OK | os.W_OK):
            logging.getLogger(__name__).error('Log file %s not read/writable.', config['--log'])
            raise ConfigError

    # --music-source
    if not config['--music-source']:
        logging.getLogger(__name__).error('Music source directory not specified.')
        raise ConfigError
    if not os.path.isdir(config['--music-source']):
        logging.getLogger(__name__).error('Music source directory does not exist: %s', config['--music-source'])
        raise ConfigError
    if not os.access(config['--music-source'], os.R_OK | os.X_OK):
        logging.getLogger(__name__).error('No access to music source directory: %s', config['--music-source'])
        raise ConfigError

    # --working-dir
    if not os.path.isdir(config['--working-dir']):
        logging.getLogger(__name__).error('Working directory does not exist: %s', config['--working-dir'])
        raise ConfigError
    if not os.access(config['--working-dir'], os.R_OK | os.W_OK | os.X_OK):
        logging.getLogger(__name__).error('No access to working directory: %s', config['--working-dir'])
        raise ConfigError
    if os.path.realpath(os.path.join(config['--working-dir'],
                                     CONVERTED_MUSIC_SUBDIR)).startswith(os.path.realpath(config['--music-source'])):
        logging.getLogger(__name__).error('Working directory converted music subdir cannot be in music source dir.')
        raise ConfigError

    # --mac-addr
    if config['--mac-addr'] and not REGEX_MAC_ADDR.match(config['--mac-addr']):
        logging.getLogger(__name__).error('Invalid MAC address: %s', config['--mac-addr'])
        raise ConfigError

    # --ffmpeg-bin
    if not config['--ffmpeg-bin']:
        logging.getLogger(__name__).error('Unable to find ffmpeg in PATH.')
        raise ConfigError
    if not os.path.isfile(config['--ffmpeg-bin']):
        logging.getLogger(__name__).error('ffmpeg binary does not exist: %s', config['--ffmpeg-bin'])
        raise ConfigError
    if not os.access(config['--ffmpeg-bin'], os.R_OK | os.X_OK):
        logging.getLogger(__name__).error('No access to ffmpeg: %s', config['--ffmpeg-bin'])
        raise ConfigError

    # --threads
    try:
        int(config['--threads'])
    except (TypeError, ValueError):
        logging.getLogger(__name__).error('Thread count must be a number: %s', config['--threads'])
        raise ConfigError


def initialize_config(doc):
    """Called during initial startup. Read config data from command line and optionally a config file.

    :raise flash_air_music.exceptions.ConfigError: On invalid data.

    :param str doc: Docstring to pass to docoptcfg.
    """
    try:
        GLOBAL_MUTABLE_CONFIG.update(_get_arguments(doc))
    except DocoptcfgFileError as exc:
        logging.getLogger(__name__).error('Config file specified but invalid: %s', exc.message)
        raise ConfigError

    # Set defaults.
    if not GLOBAL_MUTABLE_CONFIG['--ffmpeg-bin']:
        GLOBAL_MUTABLE_CONFIG['--ffmpeg-bin'] = DEFAULT_FFMPEG_BINARY
    if not GLOBAL_MUTABLE_CONFIG['--working-dir']:
        GLOBAL_MUTABLE_CONFIG['--working-dir'] = DEFAULT_WORKING_DIR

    # Validate.
    _validate_config(GLOBAL_MUTABLE_CONFIG)

    # Create destination directory.
    try:
        os.mkdir(os.path.realpath(os.path.join(GLOBAL_MUTABLE_CONFIG['--working-dir'], CONVERTED_MUSIC_SUBDIR)))
    except FileExistsError:
        pass

    # Setup logging.
    setup_logging(GLOBAL_MUTABLE_CONFIG)
    log = logging.getLogger(__name__)
    log.debug('Updated GLOBAL_MUTABLE_CONFIG.')


def update_config(doc, signum):
    """Read config data from config file on SIGHUP (1).

    :param str doc: Docstring to pass to docoptcfg.
    :param int signum: Signal number provided by signal.signal().
    """
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Reloading configuration.', signum, '/'.join(SIGNALS_INT_TO_NAME[signum]))
    if not GLOBAL_MUTABLE_CONFIG['--config']:
        log.warning('No previously defined configuration file. Nothing to read.')
        return

    # Read config.
    try:
        config = _get_arguments(doc)
    except DocoptcfgFileError as exc:
        logging.getLogger(__name__).error('Config file specified but invalid: %s', exc.message)
        return

    # Set defaults.
    if not config['--ffmpeg-bin']:
        config['--ffmpeg-bin'] = DEFAULT_FFMPEG_BINARY
    if not config['--working-dir']:
        config['--working-dir'] = DEFAULT_WORKING_DIR

    # Validate.
    try:
        _validate_config(config)
    except ConfigError:
        return

    # Update.
    GLOBAL_MUTABLE_CONFIG.update(config)

    # Create destination directory.
    try:
        os.mkdir(os.path.realpath(os.path.join(GLOBAL_MUTABLE_CONFIG['--working-dir'], CONVERTED_MUSIC_SUBDIR)))
    except FileExistsError:
        pass

    # Re-setup logging.
    setup_logging(GLOBAL_MUTABLE_CONFIG)
    log.info('Done reloading configuration.')
