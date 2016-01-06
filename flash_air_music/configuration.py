"""Handles reading configuration from command line or file and storing it in a global mutable dictionary."""

import logging
import os
import re
import signal
import sys

import pkg_resources
from docopt import docopt
from yaml import safe_load
from yaml.reader import ReaderError

from flash_air_music.exceptions import ConfigError
from flash_air_music.setup_logging import setup_logging

CONVERTED_MUSIC_SUBDIR = 'converted_music'
DEFAULT_WORKING_DIR = os.path.join(os.environ['HOME'], 'FlashAirMusicWorkingDir')
SIGNALS_INT_TO_NAME = {v: {a for a, b in vars(signal).items() if a.startswith('SIG') and b == v}
                       for k, v in vars(signal).items() if k.startswith('SIG')}
GLOBAL_MUTABLE_CONFIG = dict()
REGEX_MAC_ADDR = re.compile(r'^(?:[a-fA-F0-9]{2}[ :-]?){5}[a-fA-F0-9]{2}$')


def _get_arguments(doc, argv=None):
    """Get command line arguments.

    :param str doc: Docstring to pass to docopt.
    :param list argv: Command line argument list to process. For testing.

    :return: Parsed options.
    :rtype: dict
    """
    require = getattr(pkg_resources, 'require')  # Stupid linting error.
    project = [p for p in require('FlashAirMusic') if p.project_name == 'FlashAirMusic'][0]
    version = project.version
    return docopt(doc, argv=argv or sys.argv[1:], version=version)


def _read_config_file(path):
    """Read configuration file. Mimics docopt key names.

    :raise flash_air_music.exceptions.ConfigError: On any error when attempting to read config file.

    :param path: File path to YAML file.

    :return: Docopt-compatible configuration data.
    :rtype: dict
    """
    log = logging.getLogger(__name__)
    try:
        with open(path) as handle:
            data = dict(safe_load(handle))
    except (FileNotFoundError, PermissionError) as exc:
        log.error('Unable to read config file %s: %s', path, exc.strerror)
        raise ConfigError
    except ReaderError as exc:
        log.error('Unable to parse %s, not valid YAML: %s', path, exc.reason)
        raise ConfigError
    except (TypeError, ValueError) as exc:
        log.error('Unable to parse %s, not a dictionary: %s', path, exc.args[0])
        raise ConfigError

    # Parse config.
    config = dict()
    for key in ('--log', '--mac-addr', '--music-source', '--working-dir'):
        if key[2:] in data:
            value = data[key[2:]]
            config[key] = str(value) if value is not None else None
    for key in ('--quiet', '--verbose'):
        if key[2:] in data:
            config[key] = bool(data[key[2:]])

    return config


def _validate_config(config, file_config=None):
    """Validate config data.

    :raise flash_air_music.exceptions.ConfigError: On invalid data.

    :param dict config: Configuration dict to validate.
    :param dict file_config: Second configuration dict, usually from a config file.
    """
    if file_config:
        config = config.copy()
        config.update(file_config)
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
    if not config['--music-source']:
        logging.getLogger(__name__).error('Music source directory not specified.')
        raise ConfigError
    if not os.path.isdir(config['--music-source']):
        logging.getLogger(__name__).error('Music source directory does not exist: %s', config['--music-source'])
        raise ConfigError
    if not os.access(config['--music-source'], os.R_OK | os.X_OK):
        logging.getLogger(__name__).error('No access to music source directory: %s', config['--music-source'])
        raise ConfigError
    if not os.path.isdir(config['--working-dir']):
        logging.getLogger(__name__).error('Working directory does not exist: %s', config['--working-dir'])
        raise ConfigError
    if not os.access(config['--working-dir'], os.R_OK | os.W_OK | os.X_OK):
        logging.getLogger(__name__).error('No access to working directory: %s', config['--working-dir'])
        raise ConfigError
    if os.path.realpath(os.path.join(config['--working-dir'],
                                     CONVERTED_MUSIC_SUBDIR)) == os.path.realpath(config['--music-source']):
        logging.getLogger(__name__).error('Music source dir cannot match working directory converted music subdir.')
        raise ConfigError
    if config['--mac-addr'] and not REGEX_MAC_ADDR.match(config['--mac-addr']):
        logging.getLogger(__name__).error('Invalid MAC address: %s', config['--mac-addr'])
        raise ConfigError


def initialize_config(doc, argv=None):
    """Called during initial startup. Read config data from command line and optionally a config file.

    :param str doc: Docstring to pass to docopt.
    :param argv: Command line argument list to process. For testing.
    """
    GLOBAL_MUTABLE_CONFIG.update(_get_arguments(doc, argv))
    if not GLOBAL_MUTABLE_CONFIG['--working-dir']:
        GLOBAL_MUTABLE_CONFIG['--working-dir'] = DEFAULT_WORKING_DIR
    if GLOBAL_MUTABLE_CONFIG['--config']:
        file_config = _read_config_file(GLOBAL_MUTABLE_CONFIG['--config'])
        if file_config:
            GLOBAL_MUTABLE_CONFIG.update(file_config)
    _validate_config(GLOBAL_MUTABLE_CONFIG)
    setup_logging(GLOBAL_MUTABLE_CONFIG)
    log = logging.getLogger(__name__)
    log.debug('Read config file. Updated GLOBAL_MUTABLE_CONFIG.')


def update_config(signum, _):
    """Read config data from config file on SIGHUP (1).

    :param int signum: Signal number provided by signal.signal().
    :param _: Ignored frame.
    """
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Reloading configuration.', signum, '/'.join(SIGNALS_INT_TO_NAME[signum]))
    if not GLOBAL_MUTABLE_CONFIG['--config']:
        log.warning('No previously defined configuration file. Nothing to read.')
        return

    # Read config. Validate before merging into global config.
    try:
        file_config = _read_config_file(GLOBAL_MUTABLE_CONFIG['--config'])
        if file_config:
            _validate_config(GLOBAL_MUTABLE_CONFIG, file_config)
        else:
            log.warning('Config file %s empty.', GLOBAL_MUTABLE_CONFIG['--config'])
            return
    except ConfigError:
        return
    GLOBAL_MUTABLE_CONFIG.update(file_config)
    setup_logging(GLOBAL_MUTABLE_CONFIG)

    log.info('Done reloading configuration.')
