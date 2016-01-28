"""Test flash_air_music.configuration functions/classes."""

import pytest

from flash_air_music import configuration, exceptions
from flash_air_music.__main__ import __doc__ as doc


@pytest.mark.parametrize('bad', [False, True])
def test_config_file(monkeypatch, tmpdir, caplog, bad):
    """Test for DocoptcfgFileError in initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture
    :param bool bad: Error?
    """
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup config file.
    path = tmpdir.join('config.ini')
    monkeypatch.setenv('FAM_CONFIG', str(path))
    if bad:
        path.write('Bad File')
    else:
        path.write('[FlashAirMusic]\nverbose = true')

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Run.
    if not bad:
        configuration.initialize_config(doc)
        assert config['--verbose'] is True
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
    messages = [r.message for r in caplog.records]
    assert messages[-1] == 'Config file specified but invalid: Unable to parse config file.'


@pytest.mark.parametrize('mode', ['not_used', 'used', 'no_parent', 'dir_perm', 'file_perm'])
def test_validate_config_log(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --log validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])
    if mode != 'not_used':
        argv.extend(['--log', str(tmpdir.join('parent', 'logfile.log'))])

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Populate tmpdir.
    if mode != 'no_parent':
        tmpdir.ensure_dir('parent')
    if mode == 'dir_perm':
        tmpdir.join('parent').chmod(0o444)
    elif mode == 'file_perm':
        tmpdir.ensure('parent', 'logfile.log').chmod(0o444)

    # Run.
    if mode in ('not_used', 'used'):
        configuration.initialize_config(doc)
        if mode == 'used':
            assert config['--log'] == str(tmpdir.join('parent', 'logfile.log'))
        else:
            assert config['--log'] is None
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
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
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv.
    argv.extend(['run'])
    if mode != 'not_used':
        argv.extend(['--music-source', str(tmpdir.join('music'))])

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Populate tmpdir.
    if mode != 'dne':
        tmpdir.ensure_dir('music')
    if mode == 'perm':
        tmpdir.join('music').chmod(0o444)

    # Run.
    if mode == 'good':
        configuration.initialize_config(doc)
        assert config['--music-source'] == str(tmpdir.join('music'))
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
    messages = [r.message for r in caplog.records]
    if mode == 'not_used':
        assert messages[-1] == 'Music source directory not specified.'
    elif mode == 'dne':
        assert messages[-1].startswith('Music source directory does not exist')
    else:
        assert messages[-1].startswith('No access to music source directory')


@pytest.mark.parametrize('mode', ['specified', 'default', 'dne', 'perm', 'collision', 'collision within'])
def test_validate_config_working_dir(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --working-dir validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv.
    argv.extend(['run'])
    if mode == 'collision':
        argv.extend(['--music-source', str(tmpdir.ensure_dir(configuration.CONVERTED_MUSIC_SUBDIR))])
    elif mode == 'collision within':
        argv.extend(['--music-source', str(tmpdir)])
    else:
        argv.extend(['--music-source', str(tmpdir.ensure_dir('source'))])
        if mode != 'default':
            argv.extend(['--working-dir', str(tmpdir.join('not_default'))])

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Populate tmpdir.
    if mode != 'dne':
        tmpdir.ensure_dir('not_default')
    if mode == 'perm':
        tmpdir.join('not_default').chmod(0o444)

    # Run.
    if mode in ('specified', 'default'):
        configuration.initialize_config(doc)
        assert config['--working-dir'] == str(tmpdir.join('' if mode == 'default' else 'not_default'))
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
    messages = [r.message for r in caplog.records]
    if mode == 'dne':
        assert messages[-1].startswith('Working directory does not exist')
    elif mode == 'perm':
        assert messages[-1].startswith('No access to working directory')
    else:
        assert messages[-1] == 'Working directory converted music subdir cannot be in music source dir.'


@pytest.mark.parametrize('mode', ['missing', 'contiguous', 'hyphens', 'colons', 'spaces', 'bad'])
def test_validate_config_mac_addr(monkeypatch, tmpdir, caplog, mode):
    """Test _validate_config() --mac-addr validation via initialize_config().

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])
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

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Run.
    if mode != 'bad':
        configuration.initialize_config(doc)
        if mode == 'missing':
            assert config['--mac-addr'] is None
        else:
            assert config['--mac-addr'] == argv[-1]
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
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
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])
    if mode != 'default':
        argv.extend(['--threads', mode])

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Run.
    if mode not in ('a', '5.5'):
        configuration.initialize_config(doc)
        assert config['--threads'] == '0' if mode == 'default' else mode
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
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
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Set fake ffmpeg.
    ffmpeg = tmpdir.join('ffmpeg')
    if mode != 'dne':
        ffmpeg.ensure()
        if mode != 'perm':
            ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg) if mode != 'default missing' else None)

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])
    if mode == 'specified':
        argv.extend(['--ffmpeg-bin', str(ffmpeg)])

    # Run.
    if mode in ('specified', 'default'):
        configuration.initialize_config(doc)
        assert config['--ffmpeg-bin'] == str(ffmpeg)
        return

    # Run.
    with pytest.raises(exceptions.ConfigError):
        configuration.initialize_config(doc)

    # Verify.
    messages = [r.message for r in caplog.records]
    if mode == 'dne':
        assert messages[-1].startswith('ffmpeg binary does not exist')
    elif mode == 'perm':
        assert messages[-1].startswith('No access to ffmpeg')
    else:
        assert messages[-1] == 'Unable to find ffmpeg in PATH.'


@pytest.mark.parametrize('mode', ['good', 'no_config', 'corrupted', 'bad_config'])
def test_update_config(monkeypatch, tmpdir, caplog, mode):
    """Test update_config() and SIGHUP handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param caplog: pytest extension fixture.
    :param str mode: Scenario to test for.
    """
    argv, config = ['program'], dict()
    monkeypatch.setattr('sys.argv', argv)
    monkeypatch.setattr(configuration, 'DEFAULT_WORKING_DIR', str(tmpdir))
    monkeypatch.setattr(configuration, 'GLOBAL_MUTABLE_CONFIG', config)
    monkeypatch.setattr(configuration, 'setup_logging', lambda _: None)

    # Set fake ffmpeg.
    ffmpeg = tmpdir.ensure('ffmpeg')
    ffmpeg.chmod(0o0755)
    monkeypatch.setattr(configuration, 'DEFAULT_FFMPEG_BINARY', str(ffmpeg))

    # Setup argv.
    argv.extend(['run', '--music-source', str(tmpdir.ensure_dir('source'))])
    if mode != 'no_config':
        argv.extend(['--config', str(tmpdir.join('config.ini'))])
        tmpdir.join('config.ini').write('[FlashAirMusic]\n')

    # Initialize.
    tmpdir.ensure_dir(configuration.CONVERTED_MUSIC_SUBDIR)
    configuration.initialize_config(doc)

    # Setup config file.
    sample = tmpdir.join('sample.log')
    if mode == 'good':
        tmpdir.join('config.ini').write('[FlashAirMusic]\nlog = {}\nffmpeg-bin = {}'.format(sample, ffmpeg))
    elif mode == 'corrupted':
        tmpdir.join('config.ini').write('\x00\x00\x00\x00'.encode(), mode='wb')
    elif mode == 'bad_config':
        tmpdir.join('config.ini').write('[FlashAirMusic]\nworking-dir = {}'.format(ffmpeg))

    # Call.
    before = config.copy()
    configuration.update_config(doc, 1)

    # Verify
    messages = [r.message for r in caplog.records]
    if mode == 'good':
        assert config['--log'] == str(sample)
        assert messages[-1] == 'Done reloading configuration.'
    elif mode == 'corrupted':
        assert config == before
        assert 'Unable to parse' in messages[-1]
    elif mode == 'no_config':
        assert config == before
        assert messages[-1] == 'No previously defined configuration file. Nothing to read.'
    else:
        assert config == before
        assert messages[-1].startswith('Working directory does not exist')
    assert [m for m in messages if 'Caught signal' in m]
