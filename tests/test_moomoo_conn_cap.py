"""Moomoo connection cap: parallel workers must not exceed the gateway limit."""

from unittest import mock

import tradingagents.dataflows.moomoo as moomoo


def test_cap_closes_oldest_ctxs():
    ctxs = [mock.Mock() for _ in range(6)]
    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
        for c in ctxs:
            moomoo._live_ctxs.add(c)
    with mock.patch.object(moomoo, "_max_open_ctxs", return_value=3):
        moomoo._cap_open_ctxs()
    with moomoo._ctx_lock:
        assert len(moomoo._live_ctxs) <= 3
    closed = [c for c in ctxs if c.close.called]
    assert len(closed) >= 3
    moomoo._live_ctxs.clear()


def test_cap_below_limit_noop():
    ctxs = [mock.Mock() for _ in range(2)]
    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
        for c in ctxs:
            moomoo._live_ctxs.add(c)
    with mock.patch.object(moomoo, "_max_open_ctxs", return_value=10):
        moomoo._cap_open_ctxs()
    with moomoo._ctx_lock:
        assert len(moomoo._live_ctxs) == 2
    moomoo._live_ctxs.clear()


def test_close_all_ctxs_uses_daemon_thread_timeout():
    """Regression: _close_all_ctxs must close every live context on a daemon
    thread joined with a timeout, so a stuck ctx.close() (dead receive loop)
    can never hold the interpreter alive at exit. The shadowing duplicate that
    called ctx.close() directly was removed."""
    import inspect

    src = inspect.getsource(moomoo._close_all_ctxs)
    assert "timeout: float = 3.0" in src
    assert "daemon=True" in src
    assert "join(timeout)" in src
    # a ctx whose close() blocks forever must not block the call
    class _Stuck:
        def close(self):
            import time

            time.sleep(60)

    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
        moomoo._live_ctxs.add(_Stuck())
    import time

    t0 = time.time()
    moomoo._close_all_ctxs(timeout=0.2)
    assert time.time() - t0 < 5  # returned despite the stuck close
    moomoo._live_ctxs.clear()
