"""Test functions in module."""

import urllib.parse

import httpretty
import pytest

from flash_air_music import exceptions
from flash_air_music.upload.api import command_get_file_list, command_get_time_zone


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
        actual = command_get_file_list('flashair', directory)
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        command_get_file_list('flashair', directory)
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
        actual = command_get_time_zone('flashair')
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        command_get_time_zone('flashair')
    assert exc.value.args[0] == expected
