"""Test functions in module."""

import asyncio

import pytest

from flash_air_music.exceptions import FlashAirError, FlashAirNetworkError
from flash_air_music.upload import run
from tests import TZINFO


@pytest.mark.parametrize('exc', [FlashAirNetworkError, FlashAirError, None])
def test_scan(monkeypatch, exc):
    """Test scan().

    :param monkeypatch: pytest fixture.
    :param exception exc: Exception to test for.
    """
    def func(_):
        """Mock function.

        :param _: unused.
        """
        if exc:
            raise exc('Error')
        return TZINFO
    monkeypatch.setattr(run, 'GLOBAL_MUTABLE_CONFIG', {'--music-source': ''})
    monkeypatch.setattr(run, 'get_card_time_zone', func)
    monkeypatch.setattr(run, 'get_songs', lambda *_: ([1, 2, 3], None, None, None))
    monkeypatch.setattr(run, 'files_dirs_to_delete', lambda *_: {4, 5, 6})

    if exc != FlashAirNetworkError:
        actual = run.scan('', asyncio.Future())
        expected = (list(), set(), None) if exc == FlashAirError else ([1, 2, 3], {4, 5, 6}, TZINFO)
        assert actual == expected
        return

    with pytest.raises(FlashAirNetworkError):
        run.scan('', asyncio.Future())
