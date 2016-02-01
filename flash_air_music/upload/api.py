"""Make API calls to the FlashAir card over HTTP.

Make sure /SD_WLAN/CONFIG exists on the card and is configured to connect to your home WiFi.
"""

import logging
import urllib.parse

import requests

from flash_air_music import exceptions


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
    log = logging.getLogger(__name__)
    url = 'http://{}/command.cgi?op=100&DIR={}'.format(ip_addr, urllib.parse.quote(directory))

    # Hit API.
    log.debug('Querying url %s', url)
    response = requests.get(url)
    log.debug('Response code: %d', response.status_code)
    log.debug('Response text: %s', response.text)
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
    log = logging.getLogger(__name__)
    url = 'http://{}/command.cgi?op=221'.format(ip_addr)

    # Hit API.
    log.debug('Querying url %s', url)
    response = requests.get(url)
    log.debug('Response code: %d', response.status_code)
    log.debug('Response text: %s', response.text)
    if not response.ok:
        raise exceptions.FlashAirHTTPError(response.status_code, response)

    # Parse response.
    try:
        return int(response.text)
    except (TypeError, ValueError):
        raise exceptions.FlashAirBadResponse(response.text, response)
