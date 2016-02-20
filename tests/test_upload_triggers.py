"""Test functions in module."""

import asyncio
import socket

from flash_air_music.upload import triggers


def test_skip(monkeypatch, caplog):
    """Test with watch_for_flashair() disabled/skipped.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    loop = asyncio.get_event_loop()
    shutdown_future = asyncio.Future()
    shutdown_future.set_result(True)

    monkeypatch.setattr(triggers, 'GLOBAL_MUTABLE_CONFIG', {'--ip-addr': None})

    loop.run_until_complete(triggers.watch_for_flashair(shutdown_future))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert '127.0.0.1 is reachable. calling run().' not in messages
    assert 'watch_for_flashair() saw shutdown signal.' in messages


def test_fail(monkeypatch, caplog):
    """Test socket error.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    def func(*_):
        """Raise exception."""
        raise socket.error('Error')
    loop = asyncio.get_event_loop()
    shutdown_future = asyncio.Future()
    shutdown_future.set_result(True)

    monkeypatch.setattr(triggers, 'GLOBAL_MUTABLE_CONFIG', {'--ip-addr': '127.0.0.1'})
    monkeypatch.setattr(triggers.socket, 'connect', func)

    loop.run_until_complete(triggers.watch_for_flashair(shutdown_future))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert '127.0.0.1 is reachable. calling run().' not in messages
    assert 'watch_for_flashair() saw shutdown signal.' in messages


def test_success(monkeypatch, caplog):
    """Test two loop iterations.

    :param monkeypatch: pytest fixture.
    :param caplog: pytest extension fixture.
    """
    loop = asyncio.get_event_loop()
    shutdown_future = asyncio.Future()
    tries = list(range(3))

    monkeypatch.setattr(triggers, 'GLOBAL_MUTABLE_CONFIG', {'--ip-addr': '127.0.0.1'})
    monkeypatch.setattr(triggers, 'run', asyncio.coroutine(lambda *_: tries.pop() or shutdown_future.set_result(True)))
    monkeypatch.setattr(triggers, 'SUCCESS_SLEEP', 1)
    monkeypatch.setattr(triggers.socket, 'connect', lambda *_: None)

    loop.run_until_complete(triggers.watch_for_flashair(shutdown_future))

    messages = [r.message for r in caplog.records if r.name.startswith('flash_air_music')]
    assert '127.0.0.1 is reachable. calling run().' in messages
    assert 'watch_for_flashair() saw shutdown signal.' in messages
