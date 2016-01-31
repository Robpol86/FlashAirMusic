"""Test functions in module."""

import datetime
import urllib.parse

import httpretty
import pytest

from flash_air_music import exceptions
from flash_air_music.upload.interface import get_card_time_zone, get_files

TZINFO = datetime.timezone(datetime.timedelta(hours=-8))  # Tests are written with Pacific Time in mind.


@pytest.mark.httpretty
@pytest.mark.parametrize('mode', ['400', 'bad response', '-32'])
def test_get_card_time_zone(mode):
    """Test error handling and empty root directory.

    :param str mode: Scenario to test for.
    """
    # Setup responses and expectations.
    if mode == '400':
        status, body, exception, expected = 400, '', exceptions.FlashAirHTTPError, 400
    elif mode == 'bad response':
        status, body, exception, expected = 200, 'unexpected', exceptions.FlashAirBadResponse, 'unexpected'
    else:
        status, body, exception, expected = 200, mode, None, TZINFO
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi?op=221&DIR=/MUSIC', body=body, status=status)

    # Handle non-exception.
    if mode == '-32':
        actual = get_card_time_zone('flashair')
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        get_card_time_zone('flashair')
    assert exc.value.args[0] == expected


@pytest.mark.httpretty
@pytest.mark.parametrize('mode', ['404', '400', 'bad response', 'empty'])
def test_get_files_errors_empty_root(mode):
    """Test error handling and empty root directory.

    :param str mode: Scenario to test for.
    """
    # Setup responses and expectations.
    if mode == '404':
        status, body, exception, expected = 404, '', exceptions.FlashAirDirNotFoundError, '/MUSIC'
    elif mode == '400':
        status, body, exception, expected = 400, '', exceptions.FlashAirHTTPError, 400
    elif mode == 'bad response':
        status, body, exception, expected = 200, 'unexpected', exceptions.FlashAirBadResponse, 'unexpected'
    else:
        status, body, exception, expected = 200, 'WLANSD_FILELIST\r\n', None, (list(), ['/MUSIC'])
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi?op=100&DIR=/MUSIC', body=body, status=status)

    # Handle non-exception.
    if mode == 'empty':
        actual = get_files('flashair', TZINFO)
        assert actual == expected
        return

    # Handle exceptions.
    with pytest.raises(exception) as exc:
        get_files('flashair', TZINFO)
    assert exc.value.args[0] == expected


@pytest.mark.httpretty
@pytest.mark.parametrize('mode', ['ignore', 'one', 'two', 'three partial'])
def test_get_files_simple(mode):
    """Test simple file structure with no directories.

    :param str mode: Scenario to test for.
    """
    # Setup responses and expectations.
    if mode == 'ignore':
        body = 'WLANSD_FILELIST\r\n/MUSIC,ignore.dat,7734072,32,18062,43980\r\n'
        expected = list(), list()
    elif mode == 'one':
        body = 'WLANSD_FILELIST\r\n/MUSIC,song.mp3,7733944,32,18494,28729\r\n'
        expected = [('/MUSIC/song.mp3', 7733944, 1454191310)], list()
    else:
        if mode == 'two':
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC,song.mp3,7733944,32,18494,28729\r\n'
                    '/MUSIC,09 - Half-Penny, Two-Penny.mp3,11704554,32,17800,622\r\n')
        else:
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC,song.mp3,7733944,32,18494,28729\r\n'
                    '/MUSIC,09 - Half-Penny, Two-Penny.mp3,11704554,32,17800,622\r\n'
                    '/MUSIC,Rick James - 1981 - Street Songs - 05 - Super Freak.flac,22578069,32,16771,33703\r\n')
        expected = (
            [('/MUSIC/song.mp3', 7733944, 1454191310), ('/MUSIC/09 - Half-Penny, Two-Penny.mp3', 11704554, 1418026768)],
            list()
        )
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi?op=100&DIR=/MUSIC', body=body)

    # Run.
    actual = get_files('flashair', TZINFO)
    assert actual == expected


@pytest.mark.httpretty
def test_get_files_recursive():
    """Test with directories."""
    def request_callback(_, url, headers):
        """Mock HTTP responses.

        :param _: unused.
        :param str url: URL queried.
        :param dict headers: HTTP headers.
        """
        body = ''
        if url.endswith('DIR=/MUSIC'):
            # Root directory.
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC,04 Slip.mp3,11869064,32,15082,38565\r\n'
                    '/MUSIC,empty,0,16,18494,39799\r\n'
                    '/MUSIC,ignore,0,16,18494,39804\r\n'
                    '/MUSIC,more music,0,16,18494,39829\r\n')
        elif url.endswith('DIR=/MUSIC/empty'):
            body = 'WLANSD_FILELIST\r\n'
        elif url.endswith('DIR=/MUSIC/ignore'):
            body = 'WLANSD_FILELIST\r\n/MUSIC/ignore,ignore.txt,0,32,18494,39826\r\n'
        elif url.endswith('DIR=/MUSIC/more%20music'):
            body = "WLANSD_FILELIST\r\n/MUSIC/more music,02 - Rockin' the Paradise.mp3,7077241,32,17800,620\r\n"
        return 200, headers, body
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi', body=request_callback)

    # Run.
    actual = get_files('flashair', TZINFO)
    expected = (
        [
            ('/MUSIC/04 Slip.mp3', 11869064, 1247280790),
            ('/MUSIC/more music/02 - Rockin\' the Paradise.mp3', 7077241, 1418026764),
        ],
        ['/MUSIC/empty']
    )
    assert actual == expected


@pytest.mark.httpretty
def test_get_files_long_file_names(caplog):
    """Test with long file/dir names.

    Apparently the FlashAir API doesn't handle long file names very well, probably running into the URL length limit.

    :param caplog: pytest extension fixture.
    """
    def request_callback(_, url, headers):
        """Mock HTTP responses.

        :param _: unused.
        :param str url: URL queried.
        :param dict headers: HTTP headers.
        """
        body, status = '', 200
        if url.endswith('DIR=/MUSIC'):
            # Root directory.
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC,Bacon ipsum dolor amet corned beef fatback bresaola meatloaf, landjaeger ham hock t-bone gr'
                    'ound round short ribs cupim ham doner swine pig..MP3,11869064,32,15082,38565\r\n'
                    '/MUSIC,TENDER~1.DON,0,16,18494,42155\r\n'
                    '/MUSIC,GROUND~1.DRU,0,16,18494,42158\r\n'
                    '/MUSIC,Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder '
                    'pork belly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andou'
                    'ille, tongue rump tri-tip turducken spare ribs ball tip. Tail pe,0,16,18494,42396\r\n'
                    '/MUSIC,Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder '
                    'pork belly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andou'
                    'ille, tongue rump tri-tip turducken spare ribs ball tip. Tai,0,48,18494,42499\r\n')
        elif url.endswith('DIR=/MUSIC/TENDER~1.DON'):
            body = 'WLANSD_FILELIST\r\n/MUSIC/TENDER~1.DON,song1.MP3,11869064,32,15082,38565\r\n'
        elif url.endswith('DIR=/MUSIC/GROUND~1.DRU'):
            body = 'WLANSD_FILELIST\r\n/MUSIC/GROUND~1.DRU,song1.MP3,11869064,32,15082,38565\r\n'
        elif url.endswith('Tai'):
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC/Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder '
                    'pork belly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andou'
                    'ille, tongue rump tri-tip turducken spare ribs ball tip. Tai,Bacon ipsum dolor amet corned beef fa'
                    'tback bresaola meatloaf, landjaeger ham hock t-bone ground round short ribs cupim ham doner swine '
                    'pig..MP3,11869064,32,15082,38565\r\n')
        else:
            status = 400
        return status, headers, body
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi', body=request_callback)

    # Run.
    actual = get_files('flashair', TZINFO)
    expected = (
        [
            ('/MUSIC/Bacon ipsum dolor amet corned beef fatback bresaola meatloaf, landjaeger ham hock t-bone ground ro'
             'und short ribs cupim ham doner swine pig..MP3', 11869064, 1247280790),
            ('/MUSIC/TENDER~1.DON/song1.MP3', 11869064, 1247280790),
            ('/MUSIC/GROUND~1.DRU/song1.MP3', 11869064, 1247280790),
            ('/MUSIC/Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder pork be'
             'lly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andouille, tongue r'
             'ump tri-tip turducken spare ribs ball tip. Tai/Bacon ipsum dolor amet corned beef fatback bresaola meatlo'
             'af, landjaeger ham hock t-bone ground round short ribs cupim ham doner swine pig..MP3',
             11869064, 1247280790),
        ],
        list()
    )
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert actual == expected
    assert '\n'.join(messages).count('URL too long, ignoring: ') == 1


@pytest.mark.httpretty
def test_get_files_special_characters(caplog):
    """Test with special characters. FlashAir API does not support all legal FAT32 file name characters.

    At least legal for FAT32 and not Windows. OS X lets me set these.

    :param caplog: pytest extension fixture.
    """
    good_mapping = {
        '~': 's', '`': 'l', '!': '5', '@': 'e', '#': 'j', '$': 't', '%': 'k', '^': 'm', '(': '9', ')': 'a',
        '_': '1', '-': '2', '+': 'n', '=': 'p', '{': 'c', ']': 'b', '}': 'd', ';': '4', "'": '7', ',': '3',
    }
    weird_mapping = {
        '~1': 'f',  # *
        '~~~~~~39': 'h',  # \
        '~~~~~~41': 'r',  # |
        '~~~~~~46': '8',  # "
        '~~~~~~50': 'o',  # <
        '~~~~~~52': 'q',  # >
        '~~~~~~54': 'g',  # /
        '~~~~~~56': '6',  # ?
    }

    def request_callback(_, url, headers):
        """Mock HTTP responses.

        :param _: unused.
        :param str url: URL queried.
        :param dict headers: HTTP headers.
        """
        body, status, url = '', 200, urllib.parse.unquote(url)
        if url.endswith('DIR=/MUSIC'):
            # Root directory.
            body = ("WLANSD_FILELIST\r\n"
                    "/MUSIC,~,0,16,18494,44088\r\n"
                    "/MUSIC,`,0,16,18494,44090\r\n"
                    "/MUSIC,!,0,16,18494,44092\r\n"
                    "/MUSIC,@,0,16,18494,44093\r\n"
                    "/MUSIC,#,0,16,18494,44096\r\n"
                    "/MUSIC,$,0,16,18494,44098\r\n"
                    "/MUSIC,%,0,16,18494,44099\r\n"
                    "/MUSIC,^,0,16,18494,44100\r\n"
                    "/MUSIC,&,0,16,18494,44101\r\n"
                    "/MUSIC,~1,0,16,18494,44102\r\n"
                    "/MUSIC,(,0,16,18494,44103\r\n"
                    "/MUSIC,),0,16,18494,44105\r\n"
                    "/MUSIC,_,0,16,18494,44106\r\n"
                    "/MUSIC,-,0,16,18494,44107\r\n"
                    "/MUSIC,+,0,16,18494,44109\r\n"
                    "/MUSIC,=,0,16,18494,44110\r\n"
                    "/MUSIC,{,0,16,18494,44117\r\n"
                    "/MUSIC,],0,16,18494,44121\r\n"
                    "/MUSIC,},0,16,18494,44123\r\n"
                    "/MUSIC,~~~~~~39,0,16,18494,44124\r\n"
                    "/MUSIC,~~~~~~41,0,16,18494,44125\r\n"
                    "/MUSIC,;,0,16,18494,44129\r\n"
                    "/MUSIC,',0,16,18494,44134\r\n"
                    "/MUSIC,~~~~~~46,0,16,18494,44138\r\n"
                    "/MUSIC,,,0,16,18494,44141\r\n"
                    "/MUSIC,~~~~~~50,0,16,18494,44147\r\n"
                    "/MUSIC,~~~~~~52,0,16,18494,44148\r\n"
                    "/MUSIC,~~~~~~54,0,16,18494,44152\r\n"
                    "/MUSIC,~~~~~~56,0,16,18494,44153\r\n"
                    "/MUSIC,ñ,0,16,18494,44157\r\n"
                    "/MUSIC,Ã©,0,16,18494,44164\r\n")
        elif url[-1] in good_mapping:
            key = url[-1]
            body = 'WLANSD_FILELIST\r\n/MUSIC/{},{}.mp3,11869064,32,15082,38565\r\n'.format(key, good_mapping[key])
        elif any(url.endswith(k) for k in weird_mapping):
            key = [k for k in weird_mapping if url.endswith(k)][0]
            body = 'WLANSD_FILELIST\r\n/MUSIC/{},{}.mp3,11869064,32,15082,38565\r\n'.format(key, weird_mapping[key])
        else:
            status = 400
        return status, headers, body
    httpretty.register_uri(httpretty.GET, 'http://flashair/command.cgi', body=request_callback)

    # Run.
    actual = get_files('flashair', TZINFO)
    expected = (
        [
            ('/MUSIC/~/s.mp3', 11869064, 1247280790),
            ('/MUSIC/`/l.mp3', 11869064, 1247280790),
            ('/MUSIC/!/5.mp3', 11869064, 1247280790),
            ('/MUSIC/@/e.mp3', 11869064, 1247280790),
            ('/MUSIC/#/j.mp3', 11869064, 1247280790),
            ('/MUSIC/$/t.mp3', 11869064, 1247280790),
            ('/MUSIC/%/k.mp3', 11869064, 1247280790),
            ('/MUSIC/^/m.mp3', 11869064, 1247280790),
            ('/MUSIC/~1/f.mp3', 11869064, 1247280790),
            ('/MUSIC/(/9.mp3', 11869064, 1247280790),
            ('/MUSIC/)/a.mp3', 11869064, 1247280790),
            ('/MUSIC/_/1.mp3', 11869064, 1247280790),
            ('/MUSIC/-/2.mp3', 11869064, 1247280790),
            ('/MUSIC/+/n.mp3', 11869064, 1247280790),
            ('/MUSIC/=/p.mp3', 11869064, 1247280790),
            ('/MUSIC/{/c.mp3', 11869064, 1247280790),
            ('/MUSIC/]/b.mp3', 11869064, 1247280790),
            ('/MUSIC/}/d.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~39/h.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~41/r.mp3', 11869064, 1247280790),
            ('/MUSIC/;/4.mp3', 11869064, 1247280790),
            ("/MUSIC/'/7.mp3", 11869064, 1247280790),
            ('/MUSIC/~~~~~~46/8.mp3', 11869064, 1247280790),
            ('/MUSIC/,/3.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~50/o.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~52/q.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~54/g.mp3', 11869064, 1247280790),
            ('/MUSIC/~~~~~~56/6.mp3', 11869064, 1247280790)
        ],
        list()
    )
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert actual == expected
    assert '\n'.join(messages).count('Unable to handle special characters in directory name: ') == 3
