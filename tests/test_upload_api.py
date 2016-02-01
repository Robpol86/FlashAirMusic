"""Test functions in module."""

import urllib.parse

import httpretty
import pytest

from flash_air_music import exceptions
from flash_air_music.upload import api
from tests import HERE


@pytest.mark.httpretty
@pytest.mark.parametrize('mode', ['404', '400', 'long dir', 'bad response', ''])
def test_command_get_file_list(mode):
    """Test command_get_file_list().

    :param str mode: Scenario to test for.
    """
    status, body, directory = 200, '', '/MUSIC'
    url = 'http://flashair/command.cgi?op=100&DIR={}'.format(directory)

    # Setup responses and expectations.
    if mode == '404':
        status, exception, expected = 404, exceptions.FlashAirDirNotFoundError, directory
    elif mode == '400':
        status, exception, expected = 400, exceptions.FlashAirHTTPError, 400
    elif mode == 'long dir':
        directory = ('/MUSIC/Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder'
                     ' pork belly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken and'
                     'ouille, tongue rump tri-tip turducken spare ribs ball tip. Tai pe')
        url = 'http://flashair/command.cgi?op=100&DIR={}'.format(urllib.parse.quote(directory))
        status, exception, expected = 400, exceptions.FlashAirURLTooLong, url
    elif mode == 'bad response':
        body, exception, expected = 'unexpected', exceptions.FlashAirBadResponse, 'unexpected'
    else:
        body, exception, expected = 'WLANSD_FILELIST\r\n', None, 'WLANSD_FILELIST\r\n'
    httpretty.register_uri(httpretty.GET, url, body=body, status=status)

    # Handle non-exception.
    if not mode:
        actual = api.command_get_file_list('flashair', directory)
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        api.command_get_file_list('flashair', directory)
    assert exc.value.args[0] == expected


@pytest.mark.httpretty
@pytest.mark.parametrize('mode', ['400', 'bad response', '-32'])
def test_command_get_time_zone(mode):
    """Test command_get_time_zone().

    :param str mode: Scenario to test for.
    """
    # Setup responses and expectations.
    if mode == '400':
        status, body, exception, expected = 400, '', exceptions.FlashAirHTTPError, 400
    elif mode == 'bad response':
        status, body, exception, expected = 200, 'unexpected', exceptions.FlashAirBadResponse, 'unexpected'
    else:
        status, body, exception, expected = 200, mode, None, -32
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi', body=body, status=status)

    # Handle non-exception.
    if mode == '-32':
        actual = api.command_get_time_zone('flashair')
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        api.command_get_time_zone('flashair')
    assert exc.value.args[0] == expected


@pytest.mark.httpretty
@pytest.mark.parametrize('bad', [True, False])
def test_lua_script_execute(bad):
    """Test lua_script_execute().

    :param bool bad: Test exception.
    """
    httpretty.register_uri(httpretty.GET, 'http://flashair/MUSIC/script.lua', body=':)', status=400 if bad else 200)

    if not bad:
        actual = api.lua_script_execute('flashair', '/MUSIC/script.lua', 'a 1 c d')
        assert actual == ':)'
        return

    with pytest.raises(exceptions.FlashAirHTTPError):
        api.lua_script_execute('flashair', '/MUSIC/script.lua', 'a 1 c d')


@pytest.mark.httpretty
@pytest.mark.parametrize('bad', [True, False])
def test_upload_delete(bad):
    """Test upload_delete().

    :param bool bad: Test exception.
    """
    httpretty.register_uri(httpretty.GET, 'http://flashair/upload.cgi', body='', status=400 if bad else 200)

    if not bad:
        return api.upload_delete('flashair', '/MUSIC/file.mp3')

    with pytest.raises(exceptions.FlashAirHTTPError):
        api.upload_delete('flashair', '/MUSIC/file.mp3')


@pytest.mark.httpretty
@pytest.mark.parametrize('bad', [True, False])
def test_upload_ftime_updir_writeprotect(bad):
    """Test upload_ftime_updir_writeprotect().

    :param bool bad: Test exception.
    """
    httpretty.register_uri(httpretty.GET, 'http://flashair/upload.cgi', body='', status=400 if bad else 200)

    if not bad:
        return api.upload_ftime_updir_writeprotect('flashair', '/MUSIC', '0x483f9341')

    with pytest.raises(exceptions.FlashAirHTTPError):
        api.upload_ftime_updir_writeprotect('flashair', '/MUSIC', '0x483f9341')


@pytest.mark.httpretty
@pytest.mark.parametrize('bad', [True, False])
def test_upload_upload_file(bad):
    """Test upload_upload_file().

    :param bool bad: Test exception.
    """
    httpretty.register_uri(httpretty.POST, 'http://flashair/upload.cgi', body='', status=400 if bad else 200)

    if not bad:
        return api.upload_upload_file('flashair', 'file.mp3', HERE.join('1khz_sine.mp3').open(mode='rb'))

    with pytest.raises(exceptions.FlashAirHTTPError):
        api.upload_upload_file('flashair', 'file.mp3', HERE.join('1khz_sine.mp3').open(mode='rb'))
