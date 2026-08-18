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
