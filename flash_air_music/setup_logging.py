"""Code that handles logging for the project."""

import logging
import logging.handlers
import sys


class _InfoFilter(logging.Filter):
    """Filter out non-info and non-debug logging statements.

    From: https://stackoverflow.com/questions/16061641/python-logging-split/16066513#16066513
    """

    def filter(self, record):
        """Filter method.

        :param record: Log record object.

        :return: Keep or ignore this record.
        :rtype: bool
        """
        return record.levelno <= logging.INFO


def _cleanup_logging(root_logger, quiet, log_file):
    """Cleanup previous logging configuration. Remove unneeded handlers.

    :param root_logger: Root logger to reconfigure.
    :param bool quiet: Disable console logging.
    :param str log_file: Disable file logging.

    :return: Current file, stdout, and stderr logging handlers.
    :rtype: tuple
    """
    # Cleanup previous config.
    for handler in list(root_logger.handlers):
        if handler.__class__ == logging.handlers.WatchedFileHandler and not log_file:
            root_logger.removeHandler(handler)
        elif handler.__class__ == logging.handlers.WatchedFileHandler and handler.baseFilename != log_file:
            root_logger.removeHandler(handler)
        elif handler.__class__ == logging.StreamHandler and quiet:
            root_logger.removeHandler(handler)
        elif handler.__class__ == logging.StreamHandler and handler.stream not in (sys.stdout, sys.stderr):
            root_logger.removeHandler(handler)

    # Cleanup duplicate handlers.
    handlers_file = [h for h in root_logger.handlers if h.__class__ == logging.handlers.WatchedFileHandler]
    handlers_out = [h for h in root_logger.handlers if h.__class__ == logging.StreamHandler and h.stream == sys.stdout]
    handlers_err = [h for h in root_logger.handlers if h.__class__ == logging.StreamHandler and h.stream == sys.stderr]
    for handler in handlers_file[1:] + handlers_out[1:] + handlers_err[1:]:
        root_logger.removeHandler(handler)

    # Get remaining handlers.
    handlers_file = [h for h in root_logger.handlers if h.__class__ == logging.handlers.WatchedFileHandler]
    handlers_out = [h for h in root_logger.handlers if h.__class__ == logging.StreamHandler and h.stream == sys.stdout]
    handlers_err = [h for h in root_logger.handlers if h.__class__ == logging.StreamHandler and h.stream == sys.stderr]

    return handlers_file, handlers_out, handlers_err


def setup_logging(config, name=None):
    """Configure or reconfigure console logging. Info and below go to stdout, others go to stderr.

    :param dict config: Configuration dict to read from.
    :param str name: Which logger name to set handlers to. Used for testing.
    """
    log_file = config['--log'] or ''
    root_logger = logging.getLogger(name)
    root_logger.setLevel(logging.DEBUG if config['--verbose'] else logging.INFO)
    formatter_minimal = logging.Formatter('%(message)s')
    formatter_verbose = logging.Formatter('%(asctime)s %(process)-5d %(levelname)-8s %(name)-40s %(message)s')

    # Cleanup previous config if any.
    handlers_file, handlers_out = _cleanup_logging(root_logger, config['--quiet'], log_file)[:2]

    # Handle no logging.
    if config['--quiet'] and not log_file:
        root_logger.disabled = True
        return
    root_logger.disabled = False

    # Handle file logging.
    if log_file and not handlers_file:
        handler = logging.handlers.WatchedFileHandler(log_file)
        handler.setFormatter(formatter_verbose)
        root_logger.addHandler(handler)

    # Handle console logging.
    if not config['--quiet'] and not handlers_out:
        if config['--verbose']:
            formatter = formatter_verbose
        else:
            formatter = formatter_minimal
            logging.getLogger('requests').setLevel(logging.WARNING)
        handler_stdout = logging.StreamHandler(sys.stdout)
        handler_stdout.setFormatter(formatter)
        handler_stdout.setLevel(logging.DEBUG)
        handler_stdout.addFilter(_InfoFilter())
        root_logger.addHandler(handler_stdout)
        handler_stderr = logging.StreamHandler(sys.stderr)
        handler_stderr.setFormatter(formatter)
        handler_stderr.setLevel(logging.WARNING)
        root_logger.addHandler(handler_stderr)

    log = logging.getLogger(__name__)
    log.info('Configured logging.')
