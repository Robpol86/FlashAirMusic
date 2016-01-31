"""Interface with the FlashAir card over WiFi. Performs API calls to it.

Make sure /SD_WLAN/CONFIG exists on the card and is configured to connect to your home WiFi.
"""

import datetime
import logging
import re
import urllib.parse

import requests

from flash_air_music import exceptions

REMOTE_ROOT_DIRECTORY = '/MUSIC'


def ftime_to_epoch(fdate, ftime, tzinfo):
    """Convert FILEDATE and FILETIME integers to the number of seconds since the Unix epoch (time.time()).

    From: https://github.com/JakeJP/FlashAirJS/blob/master/js/flashAirClient.js

    :param int fdate: FDATE integer.
    :param int ftime: FTIME integer.
    :param datetime.timezone tzinfo: Timezone the card is set to.

    :return: time.time() equivalent.
    :rtype: int
    """
    year = 1980 + ((fdate >> 9) & 0x7F)
    month = (fdate >> 5) & 0xF
    day = fdate & 0x1F
    hour = (ftime >> 11) & 0x1F
    minute = (ftime >> 5) & 0x3F
    second = (ftime << 1) & 0x3F
    return int(datetime.datetime(year, month, day, hour, minute, second, tzinfo=tzinfo).timestamp())


def get_card_time_zone(ip_addr):
    """Get the time zone currently configured on the card.

    :param str ip_addr: IP address of FlashAir to connect to.

    :return: Timezone instance.
    :rtype: datetime.timezone
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
        fifteen_min_offset = int(response.text)
    except (TypeError, ValueError):
        raise exceptions.FlashAirBadResponse(response.text, response)

    return datetime.timezone(datetime.timedelta(hours=fifteen_min_offset / 4.0))


def get_files(ip_addr, tzinfo, directory=REMOTE_ROOT_DIRECTORY):
    """Recursively get a list of MP3s currently on the SD card in a directory.

    API is not recursive, so this function will call itself on every directory it encounters.

    Attribute decoding from:
    https://flashair-developers.com/en/documents/api/commandcgi/#100
    https://github.com/JakeJP/FlashAirJS/blob/master/js/flashAirClient.js

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to get file list from.
    :param datetime.timezone tzinfo: Timezone the card is set to.

    :return: Files (list of 3-item tuples [absolute file path, file size, mtime]) and list of empty dirs.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    directory = directory.rstrip('/')  # Remove trailing slash.
    url = 'http://{}/command.cgi?op=100&DIR={}'.format(ip_addr, urllib.parse.quote(directory))

    # Hit API.
    log.debug('Querying url %s', url)
    response = requests.get(url)
    log.debug('Response code: %d', response.status_code)
    log.debug('Response text: %s', response.text)
    if response.status_code == 404:
        raise exceptions.FlashAirDirNotFoundError(directory, response)
    if not response.ok:
        if len('{}?{}'.format(urllib.parse.urlsplit(url).path, urllib.parse.urlsplit(url).query)) > 280:
            log.warning('URL too long, ignoring: %s', url)
            return list(), list()
        raise exceptions.FlashAirHTTPError(response.status_code, response)
    if not response.text.startswith('WLANSD_FILELIST'):
        raise exceptions.FlashAirBadResponse(response.text, response)
    if response.text.count('\n') <= 1:
        return list(), [directory]  # No files in directory.

    # Discover files and empty directories.
    files, empty_dirs = list(), list()
    regex = re.compile(r'^.{%d},(.+?),(\d+),(\d+),(\d+),(\d+)$' % len(directory), re.MULTILINE)
    for name, size, attr, fdate, ftime in (i.groups() for i in regex.finditer(response.text.replace('\r', ''))):
        if int(attr) & 16:  # Handle directory.
            try:
                subdir = get_files(ip_addr, tzinfo, '{}/{}'.format(directory, name))  # Recurse into dir.
            except exceptions.FlashAirError:
                log.warning('Unable to handle special characters in directory name: %s', name)
                continue
            files.extend(subdir[0])
            empty_dirs.extend(subdir[1])
        elif name.lower().endswith('.mp3'):
            files.append(('{}/{}'.format(directory, name), int(size), ftime_to_epoch(int(fdate), int(ftime), tzinfo)))

    return files, empty_dirs
