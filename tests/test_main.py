"""Test flash_air_music.__main__ functions/classes."""

import os
import signal
import subprocess
import time
from distutils.spawn import find_executable

import pytest


@pytest.mark.parametrize('error', [False, True])
def test_subprocess(tmpdir, error):
    """Test running program through subprocess. Also tests signal handling.

    :param tmpdir: pytest fixture.
    :param bool error: Test startup error handling.
    """
    tmpdir.join('config.yaml').write('bad' if error else 'verbose: True')
    script = find_executable('FlashAirMusic')
    command = [script, 'run', '--config', str(tmpdir.join('config.yaml'))]
    assert os.path.isfile(script)

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
