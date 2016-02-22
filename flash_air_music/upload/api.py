"""Make API calls to the FlashAir card over HTTP.

Make sure /SD_WLAN/CONFIG exists on the card and is configured to connect to your home WiFi.
"""

import asyncio
import logging
import urllib.parse

import aiohttp
import requests

from flash_air_music import exceptions
from flash_air_music.configuration import GLOBAL_MUTABLE_CONFIG


@asyncio.coroutine
def aiohttp_interface(client, url, stream=None, file_name=None):
    """Use aiohttp to issue HTTP requests to a server.

    :raise TODO

    :param aiohttp.ClientSession client: aiohttp Client session instance.
    :param str url: URL to query.
    :param file stream: Data to POST/upload. If None then this will do a GET request.
    :param str file_name: Remote file name (not path) to upload as.

    :return: TODO
    """
    log = logging.getLogger(__name__)

    if stream is None:
        log.debug('Querying url %s', url)
        response = yield from client.get(url)
        text = yield from response.read_and_close()
        status = response.status
        yield from response.release()
        return status, text


@asyncio.coroutine
def aiohttp_get_post(url, stream=None, file_name=None):
    """TODO

    :param url:
    :param stream:
    :param file_name:
    :return:
    """
    log = logging.getLogger(__name__)

    try:
        with aiohttp.Timeout(5), aiohttp.ClientSession() as client:
            status, text = yield from aiohttp_interface(client, url, stream, file_name)
    except Exception:
        raise


def http_get_post(url, stream=None, file_name=None):
    """Perform a GET or POST request.

    :raise FlashAirNetworkError: When unable to reach API or connection timeout.

    :param str url: URL to query.
    :param file stream: Data to POST/upload. If None then this will do a GET request.
    :param str file_name: Remote file name (not path) to upload as.

    :return: Status code (int) and response text (str).
    :rtype: tuple
    """
    log = logging.getLogger(__name__)

    try:
        if stream is None:
            log.debug('Querying url %s', url)
            response = requests.get(url, timeout=5)
        else:
            log.debug('POSTing to %s with file name %s', url, file_name)
            response = requests.post(url, files={'file': (file_name, stream)}, timeout=5)
    except requests.Timeout:
        if GLOBAL_MUTABLE_CONFIG['--verbose']:
            log.exception('Handled exception:')
        raise exceptions.FlashAirNetworkError('Timed out reaching {}'.format(urllib.parse.urlsplit(url).netloc))
    except requests.ConnectionError:
        if GLOBAL_MUTABLE_CONFIG['--verbose']:
            log.exception('Handled exception:')
        raise exceptions.FlashAirNetworkError('Unable to connect to {}'.format(urllib.parse.urlsplit(url).netloc))

    log.debug('Response code: %d', response.status_code)
    log.debug('Response text: %s', response.text)
    return response.status_code, response.text


def command_get_file_list(ip_addr, directory):
    """command.cgi?op=100: Get list of files in a directory. Not recursive.

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirDirNotFoundError: When the queried directory does not exist on the card.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.
    :raise FlashAirURLTooLong: When the queried directory path is too long.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to get file list from.

    :return: Unprocessed text response.
    :rtype: str
    """
    url = 'http://{}/command.cgi?op=100&DIR={}'.format(ip_addr, urllib.parse.quote(directory))

    # Hit API.
    status_code, text = http_get_post(url)
    if status_code == 404:
        raise exceptions.FlashAirDirNotFoundError(directory, status_code, text)
    if status_code != 200:
        split = urllib.parse.urlsplit(url)
        if len('{}?{}'.format(split.path, split.query)) > 280:
            raise exceptions.FlashAirURLTooLong(url, status_code, text)
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)
    if not text.startswith('WLANSD_FILELIST'):
        raise exceptions.FlashAirBadResponse(text, status_code, text)

    return text


def command_get_time_zone(ip_addr):
    """command.cgi?op=221: get card's time zone.

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.

    :return: 15-minute offset count from UTC.
    :rtype: int
    """
    url = 'http://{}/command.cgi?op=221'.format(ip_addr)

    # Hit API.
    status_code, text = http_get_post(url)
    if status_code != 200:
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)

    # Parse response.
    try:
        return int(text)
    except (TypeError, ValueError):
        raise exceptions.FlashAirBadResponse(text, status_code, text)


def lua_script_execute(ip_addr, script_path, argv):
    """Execute Lua script over HTTP.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str script_path: Remote path to Lua script.
    :param str argv: URL-compatible arguments to pass to script.

    :return: Unprocessed text response.
    :rtype: str
    """
    url = 'http://{}/{}?{}'.format(ip_addr, script_path.strip('/'), urllib.parse.quote(argv))
    status_code, text = http_get_post(url)
    if status_code != 200:
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)
    return text


def upload_delete(ip_addr, path):
    """upload.cgi?DEL={}: delete a file or directory.

    Not recursive. Delete responsibly to avoid orphaning children.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str path: Remote path to delete.
    """
    url = 'http://{}/upload.cgi?DEL={}'.format(ip_addr, path)
    status_code, text = http_get_post(url)
    if status_code != 200:
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)


def upload_ftime_updir_writeprotect(ip_addr, directory, ftime):
    """upload.cgi?FTIME={}&UPDIR={}&WRITEPROTECT=ON: prepare for upload.

    * Sets system clock on the card to current time.
    * Defines directory where files will be uploaded to.
    * Enabled write protect for the attached host.

    Setting write protect prevents host devices from writing to the card while files are being written to it over the
    HTTP API. Card will need to be cycled to undo the host lock.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to upload files to.
    :param str ftime: Current FILETIME as a 32bit hex number.
    """
    url = 'http://{}/upload.cgi?FTIME={}&UPDIR={}&WRITEPROTECT=ON'.format(ip_addr, ftime, directory)
    status_code, text = http_get_post(url)
    if status_code != 200:
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)


def upload_upload_file(ip_addr, file_name, handle):
    """upload.cgi: Upload a file to the card over WiFi.

    File mtime is set to the current time. No way around it.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param file_name: File name to write to on the card in UPDIR.
    :param handle: Opened file handle (binary mode) to stream from.
    """
    url = 'http://{}/upload.cgi'.format(ip_addr)
    status_code, text = http_get_post(url, handle, file_name)
    if status_code != 200:
        raise exceptions.FlashAirHTTPError(status_code, status_code, text)
