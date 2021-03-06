"""Interface with the FlashAir card over WiFi. Parse API responses."""

import datetime
import logging
import os
import re
import time

from flash_air_music import exceptions
from flash_air_music.lib import SHUTDOWN
from flash_air_music.upload import api

LUA_HELPER_SCRIPT = os.path.join(os.path.dirname(__file__), '_fam_move_touch.lua')
REMOTE_ROOT_DIRECTORY = '/MUSIC'  # Must not be more than 1 level and have no spaces.
DO_NOT_DELETE = (REMOTE_ROOT_DIRECTORY, '')
UPLOAD_STAGE_NAME = '_fam_staged.bin'


def epoch_to_ftime(epoch, tzinfo):
    """Current time in DOS/Win32 FILEDATE/FILETIME format.

    From: https://flashair-developers.com/en/documents/tutorials/advanced/2/

    :param int epoch: Seconds since Unix epoch (right now if 0).
    :param datetime.timezone tzinfo: Timezone the card is set to.

    :return: Current FILETIME formatted in a string as a 32bit hex number.
    :rtype: str
    """
    date = datetime.datetime.fromtimestamp(epoch or time.time(), tzinfo)
    year = (date.year - 1980) << 9
    month = date.month << 5
    day = date.day
    hour = date.hour << 11
    minute = date.minute << 5
    second = date.second // 2  # Loses precision of half a second.
    return '0x{:x}{:x}'.format(year + month + day, hour + minute + second)


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
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.

    :return: Timezone instance.
    :rtype: datetime.timezone
    """
    fifteen_min_offset = api.command_get_time_zone(ip_addr)
    return datetime.timezone(datetime.timedelta(hours=fifteen_min_offset / 4.0))


def get_files(ip_addr, tzinfo, directory):
    """Recursively get a list of MP3s currently on the SD card in a directory.

    API is not recursive, so this function will call itself on every directory it encounters.

    Attribute decoding from:
    https://flashair-developers.com/en/documents/api/commandcgi/#100
    https://github.com/JakeJP/FlashAirJS/blob/master/js/flashAirClient.js

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirDirNotFoundError: When the queried directory does not exist on the card.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.
    :raise FlashAirURLTooLong: When the queried directory path is too long.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param datetime.timezone tzinfo: Timezone the card is set to.
    :param str directory: Remote directory to get file list from.

    :return: Files dict ({file path: (file size, mtime)}) and list of empty dirs.
    :rtype: tuple
    """
    log = logging.getLogger(__name__)
    directory = directory.rstrip('/')  # Remove trailing slash.

    # Handle shutdown.
    if SHUTDOWN.done():
        log.info('Service shutdown initiated, not getting files.')
        return dict(), list()

    # Query API.
    response_text = api.command_get_file_list(ip_addr, directory)
    if response_text.count('\n') <= 1:
        return dict(), [directory]  # No files in directory.

    # Parse response.
    files, empty_dirs = dict(), list()
    regex = re.compile(r'^.{%d},(.+?),(\d+),(\d+),(\d+),(\d+)$' % len(directory), re.MULTILINE)
    for name, size, attr, fdate, ftime in (i.groups() for i in regex.finditer(response_text.replace('\r', ''))):
        if int(attr) & 16:  # Handle directory.
            try:
                subdir = get_files(ip_addr, tzinfo, '{}/{}'.format(directory, name))  # Recurse into.
            except exceptions.FlashAirURLTooLong:
                log.warning('Directory path too long, ignoring: %s', name)
                continue
            except exceptions.FlashAirError:
                log.warning('Unable to handle special characters in directory name: %s', name)
                continue
            files.update(subdir[0])
            empty_dirs.extend(subdir[1])
        elif name.lower().endswith('.mp3'):
            files['{}/{}'.format(directory, name)] = (int(size), ftime_to_epoch(int(fdate), int(ftime), tzinfo))

    return files, empty_dirs


def delete_files_dirs(ip_addr, paths):
    """Delete files and directories on the FlashAir card.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param iter paths: List of file/dir paths to remove.
    """
    log = logging.getLogger(__name__)
    sorted_paths = sorted((p for p in paths if p.rstrip('/') not in DO_NOT_DELETE), reverse=True)
    for path in sorted_paths:
        if SHUTDOWN.done():
            logging.getLogger(__name__).info('Service shutdown initiated, stop deleting items.')
            break
        log.info('Deleting: %s', path)
        api.upload_delete(ip_addr, path)


def initialize_upload(ip_addr, tzinfo):
    """Prepare the FlashAir card for uploading files.

    Set the system clock on the card, set the upload directory, and enable write project on the host it's attached to.

    Also upload the helper Lua script to the REMOTE_ROOT_DIRECTORY.

    :raise FlashAirBadResponse: When API returns unexpected/malformed data.
    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.
    :raise FlashAirURLTooLong: When the queried directory path is too long.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param datetime.timezone tzinfo: Timezone the card is set to.
    """
    log = logging.getLogger(__name__)

    # Prepare card via upload.cgi.
    api.upload_ftime_updir_writeprotect(ip_addr, REMOTE_ROOT_DIRECTORY, epoch_to_ftime(0, tzinfo))

    # Upload helper script if not there.
    try:
        text = api.command_get_file_list(ip_addr, REMOTE_ROOT_DIRECTORY)
    except exceptions.FlashAirDirNotFoundError:
        pass
    else:
        if os.path.basename(LUA_HELPER_SCRIPT) in text:
            return  # Script already there.
    with open(LUA_HELPER_SCRIPT, mode='rb') as handle:
        api.upload_upload_file(ip_addr, os.path.basename(handle.name), handle)

    # Verify script uploaded successfully.
    text = api.command_get_file_list(ip_addr, REMOTE_ROOT_DIRECTORY)
    if '{},{}'.format(os.path.basename(LUA_HELPER_SCRIPT), os.stat(LUA_HELPER_SCRIPT).st_size) not in text:
        log.error('Lua script upload failed!')
        raise exceptions.FlashAirBadResponse(text, None)


def upload_files(ip_addr, files_attrs):
    """Upload files to the card one at a time.

    Each item in the `files_attrs` list is a tuple of:
        1. Absolute source file path on this machine.
        2. Absolute destination file path on the FlashAir card.
        3. mtime of the file in seconds since epoch.

    :raise FlashAirHTTPError: When API returns non-200 HTTP status code.
    :raise FlashAirNetworkError: When there is trouble reaching the API.

    :param str ip_addr: IP address of FlashAir to connect to.
    :param iter files_attrs: List of tuples about files and how to upload them.
    """
    log = logging.getLogger(__name__)
    script_path = '{}/{}'.format(REMOTE_ROOT_DIRECTORY, os.path.basename(LUA_HELPER_SCRIPT))
    stage_path = '{}/{}'.format(REMOTE_ROOT_DIRECTORY, UPLOAD_STAGE_NAME)

    for source, destination, mtime in files_attrs:
        if SHUTDOWN.done():
            logging.getLogger(__name__).info('Service shutdown initiated, stop uploading songs.')
            break
        log.info('Uploading file: %s', source)
        log.debug('Uploading to %s', stage_path)
        with open(source, mode='rb') as handle:
            api.upload_upload_file(ip_addr, UPLOAD_STAGE_NAME, handle)
        log.debug('Moving to %s and setting mtime %s', destination, mtime)
        script_argv = '{} {} {}'.format(stage_path, mtime, destination)
        api.lua_script_execute(ip_addr, script_path, script_argv)
