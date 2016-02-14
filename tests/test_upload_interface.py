"""Test functions in module."""

import asyncio
import os

import pytest

from flash_air_music import exceptions
from flash_air_music.upload import api, interface
from tests import HERE, TZINFO


def test_datetime_to_ftime_ftime_to_epoch():
    """Test both time functions.

    Comparing against the same number or +1 because conversion to 16-bit time number involves dividing seconds by 2 and
    rounding down.
    """
    start_time = 1455394075
    end_time = start_time + 604800  # 1 week later.
    for epoch in range(start_time, end_time):
        ftime = interface.epoch_to_ftime(epoch, TZINFO)
        epoch2 = interface.ftime_to_epoch(int(ftime[2:6], 16), int(ftime[6:], 16), TZINFO)
        assert epoch == epoch2 or epoch == epoch2 + 1


def test_get_card_time_zone(monkeypatch):
    """Test get_card_time_zone().

    :param monkeypatch: pytest fixture.
    """
    monkeypatch.setattr(api, 'command_get_time_zone', lambda _: -32)
    actual = interface.get_card_time_zone('flashair')
    assert actual == TZINFO


def test_get_files_empty_root(monkeypatch):
    """Test get_files() with empty root directory.

    :param monkeypatch: pytest fixture.
    """
    monkeypatch.setattr(api, 'command_get_file_list', lambda *_: 'WLANSD_FILELIST\r\n')
    actual = interface.get_files('flashair', TZINFO, '/MUSIC', asyncio.Future())
    expected = dict(), ['/MUSIC']
    assert actual == expected


@pytest.mark.parametrize('mode', ['ignore', 'shutdown', 'one', 'two', 'three partial'])
def test_get_files_simple(monkeypatch, mode):
    """Test get_files() and ftime_to_epoch() with simple file structure and no directories.

    :param monkeypatch: pytest fixture.
    :param str mode: Scenario to test for.
    """
    shutdown_future = asyncio.Future()

    # Setup responses and expectations.
    if mode == 'ignore':
        body = 'WLANSD_FILELIST\r\n/MUSIC,ignore.dat,7734072,32,18062,43980\r\n'
        expected = dict(), list()
    elif mode == 'shutdown':
        shutdown_future.set_result(True)
        expected = dict(), list()
    elif mode == 'one':
        body = 'WLANSD_FILELIST\r\n/MUSIC,song.mp3,7733944,32,18494,28729\r\n'
        expected = {'/MUSIC/song.mp3': (7733944, 1454191310)}, list()
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
            {'/MUSIC/song.mp3': (7733944, 1454191310), '/MUSIC/09 - Half-Penny, Two-Penny.mp3': (11704554, 1418026768)},
            list()
        )
    monkeypatch.setattr(api, 'command_get_file_list', lambda *_: body)

    # Run.
    actual = interface.get_files('flashair', TZINFO, '/MUSIC', shutdown_future)
    assert actual == expected


def test_get_files_recursive(monkeypatch):
    """Test get_files() recursing into directories.

    :param monkeypatch: pytest fixture.
    """
    def request_callback(_, directory):
        """Mock responses.

        :param _: unused.
        :param str directory: Directory queried.
        """
        body = None
        if directory == '/MUSIC':
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC,04 Slip.mp3,11869064,32,15082,38565\r\n'
                    '/MUSIC,empty,0,16,18494,39799\r\n'
                    '/MUSIC,ignore,0,16,18494,39804\r\n'
                    '/MUSIC,more music,0,16,18494,39829\r\n')
        elif directory == '/MUSIC/empty':
            body = 'WLANSD_FILELIST\r\n'
        elif directory == '/MUSIC/ignore':
            body = 'WLANSD_FILELIST\r\n/MUSIC/ignore,ignore.txt,0,32,18494,39826\r\n'
        elif directory == '/MUSIC/more music':
            body = "WLANSD_FILELIST\r\n/MUSIC/more music,02 - Rockin' the Paradise.mp3,7077241,32,17800,620\r\n"
        return body
    monkeypatch.setattr(api, 'command_get_file_list', request_callback)

    # Run.
    actual = interface.get_files('flashair', TZINFO, '/MUSIC', asyncio.Future())
    expected = (
        {
            '/MUSIC/04 Slip.mp3': (11869064, 1247280790),
            "/MUSIC/more music/02 - Rockin' the Paradise.mp3": (7077241, 1418026764),
        },
        ['/MUSIC/empty']
    )
    assert actual == expected


def test_get_files_long_file_names(monkeypatch, caplog):
    """Test get_files() with long file/dir names.

    Apparently the FlashAir API doesn't handle long file names very well, probably running into the URL length limit.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    def request_callback(_, directory):
        """Mock HTTP responses.

        :param _: unused.
        :param str directory: Directory queried.
        """
        if directory == '/MUSIC':
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
        elif directory == '/MUSIC/TENDER~1.DON':
            body = 'WLANSD_FILELIST\r\n/MUSIC/TENDER~1.DON,song1.MP3,11869064,32,15082,38565\r\n'
        elif directory == '/MUSIC/GROUND~1.DRU':
            body = 'WLANSD_FILELIST\r\n/MUSIC/GROUND~1.DRU,song1.MP3,11869064,32,15082,38565\r\n'
        elif directory.endswith('Tai'):
            body = ('WLANSD_FILELIST\r\n'
                    '/MUSIC/Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder '
                    'pork belly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andou'
                    'ille, tongue rump tri-tip turducken spare ribs ball tip. Tai,Bacon ipsum dolor amet corned beef fa'
                    'tback bresaola meatloaf, landjaeger ham hock t-bone ground round short ribs cupim ham doner swine '
                    'pig..MP3,11869064,32,15082,38565\r\n')
        else:
            raise exceptions.FlashAirURLTooLong('', None)
        return body
    monkeypatch.setattr(api, 'command_get_file_list', request_callback)

    # Run.
    actual = interface.get_files('flashair', TZINFO, '/MUSIC', asyncio.Future())
    expected = (
        {
            ('/MUSIC/Bacon ipsum dolor amet corned beef fatback bresaola meatloaf, landjaeger ham hock t-bone ground ro'
             'und short ribs cupim ham doner swine pig..MP3'): (11869064, 1247280790),
            '/MUSIC/TENDER~1.DON/song1.MP3': (11869064, 1247280790),
            '/MUSIC/GROUND~1.DRU/song1.MP3': (11869064, 1247280790),
            ('/MUSIC/Ribeye leberkas beef ribs doner capicola shankle swine short ribs fatback alcatra shoulder pork be'
             'lly meatball picanha. Pork belly pancetta t-bone tail. Filet mignon pork chop chicken andouille, tongue r'
             'ump tri-tip turducken spare ribs ball tip. Tai/Bacon ipsum dolor amet corned beef fatback bresaola meatlo'
             'af, landjaeger ham hock t-bone ground round short ribs cupim ham doner swine pig..MP3'):
            (11869064, 1247280790),
        },
        list()
    )
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert actual == expected
    assert '\n'.join(messages).count('Directory path too long, ignoring: ') == 1


def test_get_files_special_characters(monkeypatch, caplog):
    """Test get_files() with special characters. FlashAir API does not support all legal FAT32 file name characters.

    At least legal for FAT32 and not Windows. OS X lets me set these.

    :param monkeypatch: pytest fixture.
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

    def request_callback(_, directory):
        """Mock HTTP responses.

        :param _: unused.
        :param str directory: Directory queried.
        """
        if directory == '/MUSIC':
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
        elif directory[-1] in good_mapping:
            key = directory[-1]
            body = 'WLANSD_FILELIST\r\n/MUSIC/{},{}.mp3,11869064,32,15082,38565\r\n'.format(key, good_mapping[key])
        elif any(directory.endswith(k) for k in weird_mapping):
            key = [k for k in weird_mapping if directory.endswith(k)][0]
            body = 'WLANSD_FILELIST\r\n/MUSIC/{},{}.mp3,11869064,32,15082,38565\r\n'.format(key, weird_mapping[key])
        else:
            raise exceptions.FlashAirHTTPError(400, None)
        return body
    monkeypatch.setattr(api, 'command_get_file_list', request_callback)

    # Run.
    actual = interface.get_files('flashair', TZINFO, '/MUSIC', asyncio.Future())
    expected = (
        {
            '/MUSIC/~/s.mp3': (11869064, 1247280790),
            '/MUSIC/`/l.mp3': (11869064, 1247280790),
            '/MUSIC/!/5.mp3': (11869064, 1247280790),
            '/MUSIC/@/e.mp3': (11869064, 1247280790),
            '/MUSIC/#/j.mp3': (11869064, 1247280790),
            '/MUSIC/$/t.mp3': (11869064, 1247280790),
            '/MUSIC/%/k.mp3': (11869064, 1247280790),
            '/MUSIC/^/m.mp3': (11869064, 1247280790),
            '/MUSIC/~1/f.mp3': (11869064, 1247280790),
            '/MUSIC/(/9.mp3': (11869064, 1247280790),
            '/MUSIC/)/a.mp3': (11869064, 1247280790),
            '/MUSIC/_/1.mp3': (11869064, 1247280790),
            '/MUSIC/-/2.mp3': (11869064, 1247280790),
            '/MUSIC/+/n.mp3': (11869064, 1247280790),
            '/MUSIC/=/p.mp3': (11869064, 1247280790),
            '/MUSIC/{/c.mp3': (11869064, 1247280790),
            '/MUSIC/]/b.mp3': (11869064, 1247280790),
            '/MUSIC/}/d.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~39/h.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~41/r.mp3': (11869064, 1247280790),
            '/MUSIC/;/4.mp3': (11869064, 1247280790),
            "/MUSIC/'/7.mp3": (11869064, 1247280790),
            '/MUSIC/~~~~~~46/8.mp3': (11869064, 1247280790),
            '/MUSIC/,/3.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~50/o.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~52/q.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~54/g.mp3': (11869064, 1247280790),
            '/MUSIC/~~~~~~56/6.mp3': (11869064, 1247280790),
        },
        list()
    )
    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]

    # Verify.
    assert actual == expected
    assert '\n'.join(messages).count('Unable to handle special characters in directory name: ') == 3


@pytest.mark.parametrize('shutdown', [False, True])
def test_delete_files_dirs(monkeypatch, shutdown):
    """Test delete_files_dirs().

    :param monkeypatch: pytest fixture.
    :param bool shutdown: Test shutdown handling.
    """
    order = list()
    monkeypatch.setattr(api, 'upload_delete', lambda _, p: order.append(p))
    shutdown_future = asyncio.Future()

    if shutdown:
        shutdown_future.set_result(True)
        expected = list()
    else:
        expected = [
            '/MUSIC/subdir/b.mp3',
            '/MUSIC/subdir/a.mp3',
            '/MUSIC/subdir',
            '/MUSIC/song.mp3',
        ]

    paths = [
        '/',
        '/MUSIC',
        '/MUSIC/',
        '/MUSIC/song.mp3',
        '/MUSIC/subdir',
        '/MUSIC/subdir/a.mp3',
        '/MUSIC/subdir/b.mp3',
    ]

    interface.delete_files_dirs('flashair', paths, shutdown_future)
    assert order == expected


@pytest.mark.parametrize('mode', ['no dir', 'no file', 'error', ''])
def test_initialize_upload(monkeypatch, mode):
    """Test initialize_upload().

    :param monkeypatch: pytest fixture.
    :param mode: Scenario to test for.
    """
    monkeypatch.setattr(api, 'upload_ftime_updir_writeprotect', lambda *_: None)
    uploaded = list()
    script_size = os.stat(interface.LUA_HELPER_SCRIPT).st_size

    def command_get_file_list(*_):
        """Mock."""
        if not uploaded and mode == 'no dir':
            raise exceptions.FlashAirDirNotFoundError
        if (not uploaded and mode != '') or (uploaded and mode == 'error'):
            return 'WLANSD_FILELIST\r\n'
        return 'WLANSD_FILELIST\r\n/MUSIC,_fam_move_touch.lua,{},32,18495,28453\r\n'.format(script_size)
    monkeypatch.setattr(api, 'command_get_file_list', command_get_file_list)

    def upload_upload_file(*args):
        """Mock."""
        uploaded.append(True)
        assert args[1] == '_fam_move_touch.lua'
    monkeypatch.setattr(api, 'upload_upload_file', upload_upload_file)

    if mode != 'error':
        interface.initialize_upload('flashair', TZINFO)
        return

    with pytest.raises(exceptions.FlashAirBadResponse):
        interface.initialize_upload('flashair', TZINFO)


@pytest.mark.parametrize('shutdown', [False, True])
def test_upload_files(monkeypatch, shutdown):
    """Test upload_files().

    :param monkeypatch: pytest fixture.
    :param bool shutdown: Test shutdown handling.
    """
    upload, execute = list(), list()
    monkeypatch.setattr(api, 'upload_upload_file', lambda *args: upload.append(args[-1].name))
    monkeypatch.setattr(api, 'lua_script_execute', lambda *args: execute.append(args[-1]))
    shutdown_future = asyncio.Future()

    if shutdown:
        shutdown_future.set_result(True)
        expected = list()
    else:
        expected = [(str(HERE.join('1khz_sine.mp3')), '/MUSIC/_fam_staged.bin 1454388430 /MUSIC/song.mp3')]

    files_attrs = [(str(HERE.join('1khz_sine.mp3')), '/MUSIC/song.mp3', 1454388430)]
    interface.upload_files('flashair', files_attrs, shutdown_future)

    actual = list(zip(upload, execute))
    assert actual == expected
