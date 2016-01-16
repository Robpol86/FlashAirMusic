"""Test flash_air_music.configuration functions/classes."""

import pytest

from flash_air_music import configuration, exceptions
from flash_air_music.__main__ import __doc__ as doc


@pytest.mark.parametrize('bad', ['', 'dne', 'perm', 'binary', 'text'])
def test_read_config_file(monkeypatch, tmpdir, caplog, bad):
    """Test _read_config_file() via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str bad: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv and config file.
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
        path.write("""\
            ffmpeg-bin: {1}
            ignore_me: null
            music-source: {0}
            verbose: false
            working-dir: {0}
        """.format(str(tmpdir), str(ffmpeg)))
    argv = ['run', '--config', str(path)]

    if not bad:
        configuration.initialize_config(doc=doc, argv=argv)
        expected = {
            '--config': str(path),
            '--ffmpeg-bin': str(tmpdir.join('ffmpeg')),
            '--help': False,
            '--log': None,
            '--mac-addr': None,
            '--music-source': str(tmpdir),
            '--quiet': False,
            '--threads': '0',
            '--verbose': False,
            '--version': False,
            '--working-dir': str(tmpdir),
            'run': True,
        }
        assert config == expected
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]

    if bad in ('dne', 'perm'):
        assert messages[-1].startswith('Unable to read config file')
    else:
        assert messages[-1].startswith('Unable to parse')


@pytest.mark.parametrize('mode', ['not_used', 'used', 'no_parent', 'dir_perm', 'file_perm'])
def test_validate_config_log(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --log validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run', '--music-source', str(tmpdir)]
    if mode != 'not_used':
        argv.extend(['--log', str(tmpdir.join('parent', 'logfile.log'))])

    if mode != 'no_parent':
        tmpdir.join('parent').ensure_dir()
    if mode == 'dir_perm':
        tmpdir.join('parent').chmod(0o444)
    elif mode == 'file_perm':
        tmpdir.join('parent', 'logfile.log').ensure().chmod(0o444)

    if mode in ('not_used', 'used'):
        configuration.initialize_config(doc=doc, argv=argv)
        if mode == 'used':
            assert config['--log'] == str(tmpdir.join('parent', 'logfile.log'))
        else:
            assert config['--log'] is None
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    assert messages[-1].startswith('Log file')
    if mode == 'no_parent':
        assert messages[-1].endswith('not a directory.')
    elif mode == 'dir_perm':
        assert messages[-1].endswith('not writable.')
    else:
        assert messages[-1].endswith('not read/writable.')


@pytest.mark.parametrize('mode', ['good', 'not_used', 'dne', 'perm'])
def test_validate_config_music_source(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --music-source validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run']
    if mode != 'not_used':
        argv.extend(['--music-source', str(tmpdir.join('music'))])

    if mode != 'dne':
        tmpdir.join('music').ensure_dir()
    if mode == 'perm':
        tmpdir.join('music').chmod(0o444)

    if mode == 'good':
        configuration.initialize_config(doc=doc, argv=argv)
        assert config['--music-source'] == str(tmpdir.join('music'))
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    if mode == 'not_used':
        assert messages[-1] == 'Music source directory not specified.'
    elif mode == 'dne':
        assert messages[-1].startswith('Music source directory does not exist')
    else:
        assert messages[-1].startswith('No access to music source directory')


@pytest.mark.parametrize('mode', ['specified', 'default', 'dne', 'perm', 'collision'])
def test_validate_config_working_dir(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --working-dir validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run']
    if mode == 'collision':
        argv.extend(['--music-source', str(tmpdir.join(configuration.CONVERTED_MUSIC_SUBDIR).ensure_dir())])
    else:
        argv.extend(['--music-source', str(tmpdir)])
        if mode != 'default':
            argv.extend(['--working-dir', str(tmpdir.join('not_default'))])

    if mode != 'dne':
        tmpdir.join('not_default').ensure_dir()
    if mode == 'perm':
        tmpdir.join('not_default').chmod(0o444)

    if mode in ('specified', 'default'):
        configuration.initialize_config(doc=doc, argv=argv)
        assert config['--working-dir'] == str(tmpdir.join('' if mode == 'default' else 'not_default'))
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    if mode == 'dne':
        assert messages[-1].startswith('Working directory does not exist')
    elif mode == 'perm':
        assert messages[-1].startswith('No access to working directory')
    else:
        assert messages[-1] == 'Music source dir cannot match working directory converted music subdir.'


@pytest.mark.parametrize('mode', ['missing', 'contiguous', 'hyphens', 'colons', 'spaces', 'bad'])
def test_validate_config_mac_addr(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --mac-addr validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run', '--music-source', str(tmpdir)]
    if mode == 'contiguous':
        argv.extend(['--mac-addr', 'aaBBccDDeeFF'])
    elif mode == 'hyphens':
        argv.extend(['--mac-addr', '00-aa-22-BB-33-cc'])
    elif mode == 'colons':
        argv.extend(['--mac-addr', '98:Ff:76:Ee:54:Dd'])
    elif mode == 'spaces':
        argv.extend(['--mac-addr', 'a1 b2 c3 d4 e5 f6'])
    elif mode == 'bad':
        argv.extend(['--mac-addr', 'Invalid'])

    if mode != 'bad':
        configuration.initialize_config(doc=doc, argv=argv)
        if mode == 'missing':
            assert config['--mac-addr'] is None
        else:
            assert config['--mac-addr'] == argv[-1]
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    assert messages[-1] == 'Invalid MAC address: Invalid'


@pytest.mark.parametrize('mode', ['default', '0', '1', '10', '5.5', 'a'])
def test_validate_config_threads(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --threads validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run', '--music-source', str(tmpdir)]
    if mode != 'default':
        argv.extend(['--threads', mode])

    if mode not in ('a', '5.5'):
        configuration.initialize_config(doc=doc, argv=argv)
        assert config['--threads'] == '0' if mode == 'default' else mode
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    assert messages[-1] == 'Thread count must be a number: {}'.format(mode)


@pytest.mark.parametrize('mode', ['specified', 'default', 'default missing', 'dne', 'perm'])
def test_validate_config_ffmpeg_bin(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --ffmpeg-bin validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg')
    if mode != 'dne':
        ffmpeg.ensure()
        if mode != 'perm':
            ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg) if mode != 'default missing' else None)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run', '--music-source', str(tmpdir)]
    if mode == 'specified':
        argv.extend(['--ffmpeg-bin', str(ffmpeg)])

    if mode in ('specified', 'default'):
        configuration.initialize_config(doc=doc, argv=argv)
        assert config['--ffmpeg-bin'] == str(ffmpeg)
        return

    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc=doc, argv=argv)
    messages = [r.message for r in caplog.records]
    if mode == 'dne':
        assert messages[-1].startswith('ffmpeg binary does not exist')
    elif mode == 'perm':
        assert messages[-1].startswith('No access to ffmpeg')
    else:
        assert messages[-1] == 'Unable to find ffmpeg in PATH.'


@pytest.mark.parametrize('mode', ['good', 'no_config', 'corrupted', 'bad_config', 'empty_config'])
def test_update_config(monkeypatch, tmpdir, caplog, mode):
    """Test update_config() and SIGHUP handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    config = dict()
    ffmpeg = tmpdir.join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)
    argv = ['run', '--music-source', str(tmpdir)]
    if mode != 'no_config':
        argv.extend(['--config', str(tmpdir.join('config.yaml'))])
        tmpdir.join('config.yaml').write('{}')
    tmpdir.join(configuration.CONVERTED_MUSIC_SUBDIR).ensure_dir()
    configuration.initialize_config(doc=doc, argv=argv)

    # Setup config file.
    if mode == 'good':
        tmpdir.join('config.yaml').write('log: sample.log')
    elif mode == 'corrupted':
        tmpdir.join('config.yaml').write('\x00\x00\x00\x00'.encode(), mode='wb')
    elif mode == 'bad_config':
        tmpdir.join('config.yaml').write('mac-addr: Invalid')

    # Call.
    before = config.copy()
    configuration.update_config(1, object())  # signal.signal() provides signum and frame object.

    # Verify
    messages = [r.message for r in caplog.records]
    if mode == 'good':
        assert config['--log'] == 'sample.log'
        assert messages[-1] == 'Done reloading configuration.'
    elif mode == 'corrupted':
        assert config == before
        assert messages[-1].startswith('Unable to parse')
    elif mode == 'no_config':
        assert config == before
        assert messages[-1] == 'No previously defined configuration file. Nothing to read.'
    elif mode == 'bad_config':
        assert config == before
        assert messages[-1] == 'Invalid MAC address: Invalid'
    else:
        assert config == before
        assert messages[-1] == 'Config file {} empty.'.format(str(tmpdir.join('config.yaml')))
    assert [m for m in messages if 'Caught signal' in m]
