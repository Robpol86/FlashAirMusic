"""Handles reading configuration from command line or file and storing it in a global mutable dictionary."""

import logging
import signal
import sys

import pkg_resources
from docopt import docopt
from yaml import safe_load
from yaml.reader import ReaderError

from flash_air_music.exceptions import ConfigError
from flash_air_music.setup_logging import setup_logging

GLOBAL_MUTABLE_CONFIG = dict()


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


def update_config(signum=-1, argv=None, doc=None):
    """Read config data from command line and/or config file.

    Called two different ways. Either in __main__.entry_point() which handles ConfigError or from signal.signal() which
    expects this function to handle ConfigError.

    :raise flash_air_music.exceptions.ConfigError: Config file read/parse error. Raised only if `doc` arg set.

    :param int signum: When called from signal.signal(), this is the signal number.
    :param list argv: Command line argument list to process. For testing.
    :param str doc: Docstring to pass to docopt.
    """
    # If called from __main__.py on launch.
    if doc:
        GLOBAL_MUTABLE_CONFIG.update(_get_arguments(doc, argv))
        setup_logging(GLOBAL_MUTABLE_CONFIG)
        if GLOBAL_MUTABLE_CONFIG['--config']:
            file_config = _read_config_file(GLOBAL_MUTABLE_CONFIG['--config'])
            if file_config:
                GLOBAL_MUTABLE_CONFIG.update(file_config)
                setup_logging(GLOBAL_MUTABLE_CONFIG)
        log = logging.getLogger(__name__)
        log.debug('Read config file. Updated GLOBAL_MUTABLE_CONFIG.')
        return

    # Handle signaling.
    int_to_name = {getattr(signal, k): list() for k in dir(signal) if k.startswith('SIG')}
    for name in (k for k in dir(signal) if k.startswith('SIG')):
        int_to_name[getattr(signal, name)].append(name)
    log = logging.getLogger(__name__)
    log.info('Caught signal %d (%s). Reloading configuration.', signum, ', '.join(int_to_name[signum]))
    if not GLOBAL_MUTABLE_CONFIG['--config']:
        log.warning('No previously defined configuration file. Nothing to read.')
        return

    # Read config.
    try:
        file_config = _read_config_file(GLOBAL_MUTABLE_CONFIG['--config'])
    except ConfigError:
        return
    GLOBAL_MUTABLE_CONFIG.update(file_config)
    setup_logging(GLOBAL_MUTABLE_CONFIG)
    log.info('Done reloading configuration.')
