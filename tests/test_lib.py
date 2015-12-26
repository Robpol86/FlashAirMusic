"""Test flash_air_music.lib functions/classes."""

import logging
import time

import pytest

from flash_air_music.lib import setup_logging


@pytest.mark.parametrize('log', ['sample.log', ''])
@pytest.mark.parametrize('quiet', [True, False])
@pytest.mark.parametrize('verbose', [True, False])
def test_setup_logging(capsys, tmpdir, log, quiet, verbose):
    """Test setup_logging() function.

    :param capsys: pytest fixture.
    :param tmpdir: pytest fixture.
    :param bool log: Test --log (to file) option.
    :param bool quiet: Test --quiet (console only) option.
    :param bool verbose: Test --verbose (debug logging) option.
    """
    config = {'--log': str(tmpdir.join(log)) if log else log, '--quiet': quiet, '--verbose': verbose}
    name = 'test_logger_{}'.format('_'.join(k[2:] for k, v in sorted(config.items()) if v))
    setup_logging(config, name)

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
        assert not disk

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
