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

FFMPEG_DEFAULT_BINARY = find_executable('ffmpeg')
FFMPEG_NOT_FOUND_LABEL = '<not found>'
GLOBAL_MUTABLE_CONFIG = dict()
REGEX_IP_ADDR = re.compile(r'^[a-zA-Z0-9_.-]+$')
SIGNALS_INT_TO_NAME = {v: {a for a, b in vars(signal).items() if a.startswith('SIG') and b == v}
                       for k, v in vars(signal).items() if k.startswith('SIG')}


def _get_arguments(doc):
    """Get command line arguments.

    :param str doc: Docstring to pass to docopt.

    :return: Parsed options.
    :rtype: dict
    """
    docstring = doc.format(program='FlashAirMusic', ffmpeg_default=FFMPEG_DEFAULT_BINARY or FFMPEG_NOT_FOUND_LABEL)
    require = getattr(pkg_resources, 'require')  # Stupid linting error.
    project = [p for p in require('FlashAirMusic') if p.project_name == 'FlashAirMusic'][0]
    version = project.version
    return docoptcfg(docstring, config_option='--config', env_prefix='FAM_', version=version)


def _real_paths(config):
    """Resolve relative paths in config to absolute/real paths.

    :param dict config: Configuration dict to validate.
    """
    for key in ('--config', '--ffmpeg-bin', '--log', '--music-source', '--working-dir'):
        if not config[key]:
            continue
        config[key] = os.path.realpath(os.path.expanduser(config[key]))


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
    if config['--working-dir'].startswith(config['--music-source']):
        logging.getLogger(__name__).error('Working directory cannot be in music source dir.')
        raise ConfigError
    if config['--music-source'].startswith(config['--working-dir']):
        logging.getLogger(__name__).error('Music source dir cannot be in working directory.')
        raise ConfigError

    # --ip-addr
    if config['--ip-addr'] and not REGEX_IP_ADDR.match(config['--ip-addr']):
        logging.getLogger(__name__).error('Invalid hostname/IP address: %s', config['--ip-addr'])
        raise ConfigError

    # --ffmpeg-bin
    if config['--ffmpeg-bin'].endswith(FFMPEG_NOT_FOUND_LABEL):
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

    # Resolve relative paths.
    _real_paths(GLOBAL_MUTABLE_CONFIG)

    # Validate.
    _validate_config(GLOBAL_MUTABLE_CONFIG)

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

    # Resolve relative paths.
    _real_paths(config)

    # Validate.
    try:
        _validate_config(config)
    except ConfigError:
        return

    # Update.
    GLOBAL_MUTABLE_CONFIG.update(config)

    # Re-setup logging.
    setup_logging(GLOBAL_MUTABLE_CONFIG)
    log.info('Done reloading configuration.')
