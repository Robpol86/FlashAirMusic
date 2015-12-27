"""Test flash_air_music.configuration functions/classes."""

import pytest

from flash_air_music import configuration, exceptions
from flash_air_music.__main__ import __doc__ as doc


@pytest.mark.parametrize('bad', ['', 'dne', 'perm', 'binary', 'text'])
def test_read_config_file(tmpdir, caplog, bad):
    """Test _read_config_file().

    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str bad: Scenario to test for.
    """
    path = tmpdir.join('config.yaml')
    if bad != 'dne':
        path.ensure()
    if bad == 'perm':
        path.chmod(0o0222)
    if bad == 'binary':
        path.write('\x00\x00\x00\x00')
    if bad == 'text':
        path.write('text')
    if not bad:
        path.write('log: {}\nquiet: true\nverbose: false\nignore_me: null'.format(str(tmpdir.join('sample.log'))))

    if not bad:
        config = getattr(configuration, '_read_config_file')(str(path))
        assert config == {'--log': str(tmpdir.join('sample.log')), '--quiet': True, '--verbose': False}
        return

    with pytest.raises(exceptions.ConfigError):
        getattr(configuration, '_read_config_file')(str(path))
    messages = [r.message for r in caplog.records]

    if bad in ('dne', 'perm'):
        assert messages[-1].startswith('Unable to read config file')
    else:
        assert messages[-1].startswith('Unable to parse')


@pytest.mark.parametrize('path', ['', 'empty.yaml', 'normal.yaml', 'error.yaml'])
def test_update_config_doc(monkeypatch, tmpdir, path):
    """Test update_config() by calling it with doc defined.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param str path: What to set argv --config to.
    """
    config = dict()
    monkeypatch.setattr('flash_air_music.configuration.GLOBAL_MUTABLE_CONFIG', config)

    # Setup argv and config file.
    argv = ['run'] + (['--config', str(tmpdir.join(path))] if path else [])
    if path == 'empty.yaml':
        tmpdir.join(path).write('{}')
    elif path == 'normal.yaml':
        tmpdir.join(path).write('log: sample.log')
    elif path == 'error.yaml':
        tmpdir.join(path).write('\x00\x00\x00\x00'.encode(), mode='wb')
    else:
        argv.append('--verbose')

    # Call.
    if path == 'error.yaml':
        with pytest.raises(exceptions.ConfigError):
            configuration.update_config(argv=argv, doc=doc)
        return
    configuration.update_config(argv=argv, doc=doc)

    # Verify
    if path == 'empty.yaml':
        assert config['--config'] == str(tmpdir.join(path))
        assert config['--log'] is None
        assert config['--verbose'] is False
    elif path == 'normal.yaml':
        assert config['--config'] == str(tmpdir.join(path))
        assert config['--log'] == 'sample.log'
        assert config['--verbose'] is False
    else:
        assert config['--config'] is None
        assert config['--log'] is None
        assert config['--verbose'] is True
