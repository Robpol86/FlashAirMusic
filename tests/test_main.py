"""Test flash_air_music.__main__ functions/classes."""

import os
import signal
import subprocess
import time
from distutils.spawn import find_executable

import pytest


@pytest.mark.parametrize('error', [False, True])
def test_subprocess(monkeypatch, tmpdir, error):
    """Test running program through subprocess. Also tests signal handling.

    :param monkeypatch: pytest fixture.
    :param tmpdir: pytest fixture.
    :param bool error: Test startup error handling.
    """
    source, work = tmpdir.join('source').ensure_dir(), tmpdir.join('work').ensure_dir()

    if error:
        tmpdir.join('config.yaml').write('bad')
    else:
        tmpdir.join('config.yaml').write(
            'verbose: True\nmusic-source: {}\nworking-dir: {}'.format(str(source), str(work))
        )
    script = find_executable('FlashAirMusic')
    command = [script, 'run', '--config', str(tmpdir.join('config.yaml'))]
    assert os.path.isfile(script)

    ffmpeg = tmpdir.join('bin').ensure_dir().join('ffmpeg').ensure()
    ffmpeg.chmod(0o0755)
    monkeypatch.setenv('PATH', '{}:{}'.format(os.environ['PATH'], ffmpeg.dirname))

    if error:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=1)
        stdout = exc.value.output.decode('utf-8')
        assert 'Unable to parse {}'.format(tmpdir.join('config.yaml')) in stdout
        assert 'Failure.' in stdout
        return

    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
        time.sleep(0.7)
        tmpdir.join('config.yaml').write('verbose: False')
        process.send_signal(signal.SIGHUP)
        time.sleep(0.7)
        process.send_signal(signal.SIGTERM)
        stdout = process.communicate(timeout=1)[0].decode('utf-8')
        retcode = process.poll()

    assert 'Caught signal' in stdout
    assert 'SIGHUP' in stdout

    before, after = stdout.split('SIGHUP', 1)
    assert 'Doing nothing (info).' in before
    assert 'Doing nothing (debug).' in before
    assert 'Doing nothing (info).' in after
    assert 'Doing nothing (debug).' not in after
    assert 'Shutting down.' in after

    assert not retcode
