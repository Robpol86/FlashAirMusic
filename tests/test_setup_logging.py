"""Test flash_air_music.setup_logging functions/classes."""

import logging
import logging.handlers
import time
from io import StringIO

import pytest

from flash_air_music import setup_logging


@pytest.mark.parametrize('mode', ['', 'rem file', 'bad file', 'dup file', 'rem con', 'bad con', 'dup out', 'dup err'])
def test_cleanup_logging(monkeypatch, request, tmpdir, mode):
    """Test _cleanup_logging().

    :param monkeypatch: pytest fixture.
    :param request: pytest fixture.
    :param tmpdir: pytest fixture.
    :param str mode: Test scenario.
    """
    stdout, stderr = StringIO(), StringIO()
    monkeypatch.setattr('flash_air_music.setup_logging.sys', type('', (), {'stdout': stdout, 'stderr': stderr}))

    log, name, quiet = str(tmpdir.join('sample.log')), request.function.__name__, False
    logger = logging.getLogger(name)
    if mode == 'rem file':
        logger.addHandler(logging.handlers.WatchedFileHandler(log))
        log = ''
    elif mode == 'bad file':
        logger.addHandler(logging.handlers.WatchedFileHandler(str(tmpdir.join('bad.log'))))
    elif mode == 'dup file':
        logger.addHandler(logging.handlers.WatchedFileHandler(log))
        logger.addHandler(logging.handlers.WatchedFileHandler(log))
    elif mode == 'rem con':
        logger.addHandler(logging.StreamHandler(stdout))
        quiet = True
    elif mode == 'bad con':
        logger.addHandler(logging.StreamHandler(StringIO()))
    elif mode == 'dup out':
        logger.addHandler(logging.StreamHandler(stdout))
        logger.addHandler(logging.StreamHandler(stdout))
    elif mode == 'dup err':
        logger.addHandler(logging.StreamHandler(stderr))
        logger.addHandler(logging.StreamHandler(stderr))

    handlers_file, handlers_out, handlers_err = getattr(setup_logging, '_cleanup_logging')(logger, quiet, log)

    if mode == 'dup file':
        assert [h.baseFilename for h in handlers_file] == [str(tmpdir.join('sample.log'))]
    else:
        assert not handlers_file

    if mode == 'dup out':
        assert [h.stream for h in handlers_out] == [stdout]
    else:
        assert not handlers_out

    if mode == 'dup err':
        assert [h.stream for h in handlers_err] == [stderr]
    else:
        assert not handlers_err


@pytest.mark.parametrize('log', ['sample.log', ''])
@pytest.mark.parametrize('quiet', [True, False])
@pytest.mark.parametrize('verbose', [True, False])
def test_setup_logging_new(capsys, request, tmpdir, log, quiet, verbose):
    """Test setup_logging() function with no previous config.

    :param capsys: pytest fixture.
    :param request: pytest fixture.
    :param tmpdir: pytest fixture.
    :param str log: Test --log (to file) option.
    :param bool quiet: Test --quiet (console only) option.
    :param bool verbose: Test --verbose (debug logging) option.
    """
    config = {'--log': str(tmpdir.join(log)) if log else log, '--quiet': quiet, '--verbose': verbose}
    name = '{}_{}'.format(request.function.__name__, '_'.join(k[2:] for k, v in sorted(config.items()) if v))
    setup_logging.setup_logging(config, name)

    # Emit.
    logger = logging.getLogger(name)
    for attr in ('debug', 'info', 'warning', 'error', 'critical'):
        getattr(logger, attr)('Test {}.'.format(attr))
        time.sleep(0.01)

    # Collect.
    stdout, stderr = capsys.readouterr()
    disk = tmpdir.join(log).read() if log else None

    # Check log file.
    if log:
        assert 'Test critical.' in disk
        assert 'Test error.' in disk
        assert 'Test warning.' in disk
        assert 'Test info.' in disk
        if verbose:
            assert 'Test debug.' in disk
        else:
            assert 'Test debug.' not in disk
    else:
        assert not tmpdir.listdir()

    # Check quiet console.
    if quiet:
        assert not stdout
        assert not stderr
        return

    # Check normal/verbose console.
    if verbose:
        assert name in stdout
        assert name in stderr
        assert 'Test debug.' in stdout
    else:
        assert name not in stdout
        assert name not in stderr
        assert 'Test debug.' not in stdout
    assert 'Test debug.' not in stderr

    assert 'Test info.' in stdout
    assert 'Test warning.' not in stdout
    assert 'Test error.' not in stdout
    assert 'Test critical.' not in stdout

    assert 'Test info.' not in stderr
    assert 'Test warning.' in stderr
    assert 'Test error.' in stderr
    assert 'Test critical.' in stderr


@pytest.mark.parametrize('log', range(3))
def test_setup_logging_on_off_on(capsys, request, tmpdir, log):
    """Test enabling, disabling, and re-enabling logging.

    :param capsys: pytest fixture.
    :param request: pytest fixture.
    :param tmpdir: pytest fixture.
    :param int log: Test iteration (0 1 2: on off on).
    """
    # Setup config.
    config = {'--log': str(tmpdir.join('sample.log')), '--quiet': False, '--verbose': False}
    if log == 1:
        config['--log'] = ''
        config['--quiet'] = True

    # Check for loggers before logging.
    name = request.function.__name__
    logger = logging.getLogger(name)
    if log == 1:
        assert logger.handlers
    else:
        assert not logger.handlers

    # Log.
    setup_logging.setup_logging(config, name)
    logger.info('Test info.')

    # Collect.
    stdout, stderr = capsys.readouterr()
    disk = tmpdir.join('sample.log').read() if log != 1 else None

    # Check.
    assert not stderr
    if log == 1:
        assert not stdout
        assert not tmpdir.listdir()
    else:
        assert 'Test info.' in stdout
        assert 'Test info.' in disk


def test_logrotate(request, tmpdir):
    """Test logrotate support.

    :param request: pytest fixture.
    :param tmpdir: pytest fixture.
    """
    # Setup.
    config = {'--log': str(tmpdir.join('sample.log')), '--quiet': True, '--verbose': False}
    name = request.function.__name__
    logger = logging.getLogger(name)

    # Log.
    setup_logging.setup_logging(config, name)
    logger.info('Test one.')
    tmpdir.join('sample.log').move(tmpdir.join('sample.log.old'))
    logger.info('Test two.')

    # Collect.
    sample_one = tmpdir.join('sample.log.old').read()
    sample_two = tmpdir.join('sample.log').read()

    # Check.
    assert 'Test one.' in sample_one
    assert 'Test two.' not in sample_one
    assert 'Test one.' not in sample_two
    assert 'Test two.' in sample_two
