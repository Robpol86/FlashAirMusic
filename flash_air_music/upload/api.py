"""Make API calls to the FlashAir card over HTTP.

Make sure /SD_WLAN/CONFIG exists on the card and is configured to connect to your home WiFi.
"""

import logging
import urllib.parse

import requests

from flash_air_music import exceptions


def requests_get_post(url, stream=None, file_name=None):
    """Perform a GET or POST request.

    :param str url: URL to query.
    :param file stream: Data to POST/upload. If None then this will do a GET request.
    :param str file_name: Remote file name (not path) to upload as.

    :return: Response object.
    :rtype: requests.models.Response
    """
    log = logging.getLogger(__name__)

    if stream is None:
        log.debug('Querying url %s', url)
        response = requests.get(url, timeout=5)
    else:
        log.debug('POSTing to %s', url)
        response = requests.post(url, files={'file': (file_name, stream)}, timeout=5)

    log.debug('Response code: %d', response.status_code)
    log.debug('Response text: %s', response.text)
    return response


def command_get_file_list(ip_addr, directory):
    """command.cgi?op=100: Get list of files in a directory. Not recursive.

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirDirNotFoundError: When the queried directory does not exist on the card.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirURLTooLong: When the queried directory path is too long.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to get file list from.

    :return: Unprocessed text response.
    :rtype: str
    """
    url = 'http://{}/command.cgi?op=100&DIR={}'.format(ip_addr, urllib.parse.quote(directory))

    # Hit API.
    response = requests_get_post(url)
    if response.status_code == 404:
        raise exceptions.FlashAirDirNotFoundError(directory, response)
    if not response.ok:
        split = urllib.parse.urlsplit(url)
        if len('{}?{}'.format(split.path, split.query)) > 280:
            raise exceptions.FlashAirURLTooLong(url, response)
        raise exceptions.FlashAirHTTPError(response.status_code, response)
    if not response.text.startswith('WLANSD_FILELIST'):
        raise exceptions.FlashAirBadResponse(response.text, response)

    return response.text


def command_get_time_zone(ip_addr):
    """command.cgi?op=221: get card's time zone.

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.

    :return: 15-minute offset count from UTC.
    :rtype: int
    """
    url = 'http://{}/command.cgi?op=221'.format(ip_addr)

    # Hit API.
    response = requests_get_post(url)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)

    # Parse response.
    try:
        return int(response.text)
    except (TypeError, ValueError):
        raise exceptions.FlashAirBadResponse(response.text, response)


def lua_script_execute(ip_addr, script_path, argv):
    """Execute Lua script over HTTP.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str script_path: Remote path to Lua script.
    :param str argv: URL-compatible arguments to pass to script.

    :return: Unprocessed text response.
    :rtype: str
    """
    url = 'http://{}/{}?{}'.format(ip_addr, script_path.strip('/'), urllib.parse.quote(argv))
    response = requests_get_post(url)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)
    return response.text


def upload_delete(ip_addr, path):
    """upload.cgi?DEL={}: delete a file or directory.

    Not recursive. Delete responsibly to avoid orphaning children.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str path: Remote path to delete.
    """
    url = 'http://{}/upload.cgi?DEL={}'.format(ip_addr, path)
    response = requests_get_post(url)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)


def upload_ftime_updir_writeprotect(ip_addr, directory, ftime):
    """upload.cgi?FTIME={}&UPDIR={}&WRITEPROTECT=ON: prepare for upload.

    * Sets system clock on the card to current time.
    * Defines directory where files will be uploaded to.
    * Enabled write protect for the attached host.

    Setting write protect prevents host devices from writing to the card while files are being written to it over the
    HTTP API. Card will need to be cycled to undo the host lock.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to upload files to.
    :param str ftime: Current FILETIME as a 32bit hex number.
    """
    url = 'http://{}/upload.cgi?FTIME={}&UPDIR={}&WRITEPROTECT=ON'.format(ip_addr, ftime, directory)
    response = requests_get_post(url)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)


def upload_upload_file(ip_addr, file_name, handle):
    """upload.cgi: Upload a file to the card over WiFi.

    File mtime is set to the current time. No way around it.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param file_name: File name to write to on the card in UPDIR.
    :param handle: Opened file handle (binary mode) to stream from.
    """
    url = 'http://{}/upload.cgi'.format(ip_addr)
    response = requests_get_post(url, handle, file_name)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)
