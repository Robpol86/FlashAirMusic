"""Common classes/functions used throughout the program."""

import logging
import logging.handlers
import sys


class InfoFilter(logging.Filter):
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


def setup_logging(config, name=None):
    """Setup console logging. Info and below go to stdout, others go to stderr.

    :param dict config: docopt output from __main__.get_arguments().
    :param str name: Which logger name to set handlers to. Used for testing.
    """
    root_logger = logging.getLogger(name)
    root_logger.setLevel(logging.DEBUG if config['--verbose'] else logging.INFO)
    formatter_verbose = logging.Formatter('%(asctime)s %(levelname)-8s %(name)-40s %(message)s')

    # Handle file logging.
    if config['--log']:
        handler = logging.handlers.TimedRotatingFileHandler(config['--log'], 'd', 1, 60)
        handler.setFormatter(formatter_verbose)
        root_logger.addHandler(handler)

    # Handle console logging.
    if not config['--quiet']:
        formatter = formatter_verbose if config['--verbose'] else logging.Formatter('\xf0\x9f\x92\xac  %(message)s')
        handler_stdout = logging.StreamHandler(sys.stdout)
        handler_stdout.setFormatter(formatter)
        handler_stdout.setLevel(logging.DEBUG)
        handler_stdout.addFilter(InfoFilter())
        root_logger.addHandler(handler_stdout)
        handler_stderr = logging.StreamHandler(sys.stderr)
        handler_stderr.setFormatter(formatter)
        handler_stderr.setLevel(logging.WARNING)
        root_logger.addHandler(handler_stderr)

    # Handle no logging.
    if config['--quiet'] and not config['--log']:
        root_logger.disabled = True

    log = logging.getLogger(__name__)
    log.info('Initializing...')
