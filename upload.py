#!/usr/bin/env python
"""Simple script which uploads an MP3 file to a FlashAir card.

Doesn't actually work. Using this file to put all my notes in.

In [136]: response = requests.get('http://10.192.168.149/upload.cgi?WRITEPROTECT=ON&UPDIR=/MUSIC&FTI
ME={}'.format(file_time())); print response.status_code, response.text
200 SUCCESS

In [137]: handle.seek(0); response = requests.post(url, files=dict(file=('sample4.mp3', handle))); p
rint response.status_code, response.text
200 <html xmlns="http://www.w3.org/1999/xhtml"><head><META http-equiv="Content-Type" CONTENT="text/h
tml; charset=utf-8"/><h1>Success</h1><br>
<form action=/upload.cgi method=post enctype=multipart/form-data>
<input name=file type=file size=50><br>
<input type=submit value=submit ></form>
</body></html>
"""

import datetime

import requests


def datetime_to_ftime(dt=None):
    """Convert a Python datetime object to DOS/Win32 FILEDATE/FILETIME format.

    From: https://flashair-developers.com/en/documents/tutorials/advanced/2/

    :param datetime.datetime dt: Datetime object. Default is now.

    :return: Current FILETIME formatted in a string as a 32bit hex number.
    :rtype: str
    """
    dt = dt or datetime.datetime.now()
    year = (dt.year - 1980) << 9
    month = dt.month << 5
    day = dt.day
    hour = dt.hour << 11
    minute = dt.minute << 5
    second = dt.second // 2
    return '0x{:x}{:x}'.format(year + month + day, hour + minute + second)


def main():
    """Main function."""
    # Set time.
    # response = requests.get('http://10.192.168.149/upload.cgi?FTIME={}'.format(file_time()))
    # assert response.text == 'SUCCESS'

    # Set upload root directory.
    # requests.get('http://10.192.168.149/upload.cgi?UPDIR=/MUSIC')

    # Prevent the host from also writing to the SD card, which would corrupt data.
    # response = requests.get('http://10.192.168.149/upload.cgi?WRITEPROTECT=ON')
    # assert response.text == 'SUCCESS'

    # Delete everything in /MUSIC
    # response = requests.get('http://10.192.168.149/command.cgi?op=100&DIR=/MUSIC')
    # lines = response.text.splitlines()
    # assert lines[0] == 'WLANSD_FILELIST'
    # if len(lines) > 1:
    #    import pdb; pdb.set_trace()
    #    raise NotImplementedError

    # Upload file.
    now = datetime_to_ftime()
    url = 'http://10.192.168.149/upload.cgi?WRITEPROTECT=ON&FTIME={}&UPDIR=/MUSIC'.format(now)
    with open('sample.mp3', 'rb') as handle:
        response = requests.post(url, files=dict(file=('sample2.mp3', handle)))
    assert response


if __name__ == '__main__':
    main()
