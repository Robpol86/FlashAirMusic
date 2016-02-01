"""Interface with the FlashAir card over WiFi. Parse API responses."""

import datetime
import logging
import re

from flash_air_music import exceptions
from flash_air_music.upload import api

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

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.

    :param str ip_addr: IP address of FlashAir to connect to.

    :return: Timezone instance.
    :rtype: datetime.timezone
    """
    fifteen_min_offset = api.command_get_time_zone(ip_addr)
    return datetime.timezone(datetime.timedelta(hours=fifteen_min_offset / 4.0))


def get_files(ip_addr, tzinfo, directory=REMOTE_ROOT_DIRECTORY):
    """Recursively get a list of MP3s currently on the SD card in a directory.

    API is not recursive, so this function will call itself on every directory it encounters.

    Attribute decoding from:
    https://flashair-developers.com/en/documents/api/commandcgi/#100
    https://github.com/JakeJP/FlashAirJS/blob/master/js/flashAirClient.js

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirDirNotFoundError: When the queried directory does not exist on the card.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirURLTooLong: When the queried directory path is too long.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param str directory: Remote directory to get file list from.
    :param datetime.timezone tzinfo: Timezone the card is set to.

    :return: Files (list of 3-item tuples [absolute file path, file size, mtime]) and list of empty dirs.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    directory = directory.rstrip('/')  # Remove trailing slash.

    # Query API.
    response_text = api.command_get_file_list(ip_addr, directory)
    if response_text.count('\n') <= 1:
        return list(), [directory]  # No files in directory.

    # Parse response.
    files, empty_dirs = list(), list()
    regex = re.compile(r'^.{%d},(.+?),(\d+),(\d+),(\d+),(\d+)$' % len(directory), re.MULTILINE)
    for name, size, attr, fdate, ftime in (i.groups() for i in regex.finditer(response_text.replace('\r', ''))):
        if int(attr) & 16:  # Handle directory.
            try:
                subdir = get_files(ip_addr, tzinfo, '{}/{}'.format(directory, name))  # Recurse into dir.
            except exceptions.FlashAirURLTooLong:
                log.warning('Directory path too long, ignoring: %s', name)
                continue
            except exceptions.FlashAirError:
                log.warning('Unable to handle special characters in directory name: %s', name)
                continue
            files.extend(subdir[0])
            empty_dirs.extend(subdir[1])
        elif name.lower().endswith('.mp3'):
            files.append(('{}/{}'.format(directory, name), int(size), ftime_to_epoch(int(fdate), int(ftime), tzinfo)))

    return files, empty_dirs
