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
    """Regression: _close_all_ctxs must hand every live ctx.close to a daemon
    thread joined with the passed timeout, so a stuck ctx.close() (dead receive
    loop) can never hold the interpreter alive at exit. The shadowing duplicate
    that called ctx.close() directly was removed.

    The thread is faked so the assertion is on the call the code makes
    (daemon=True, join(timeout)) rather than on wall-clock timing: a direct
    close on the calling thread would call ``ctx.close`` and fail here.
    """
    created = []

    class _FakeThread:
        def __init__(self, target=None, daemon=None, **kwargs):
            self.target = target
            self.daemon = daemon
            self.started = False
            self.joins = []
            created.append(self)

        def start(self):
            self.started = True

        def join(self, timeout=None):
            # Return immediately: the join times out while close() is stuck.
            self.joins.append(timeout)

    ctx = mock.Mock()  # a direct ctx.close() would run on this thread
    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
        moomoo._live_ctxs.add(ctx)

    with mock.patch.object(moomoo, "threading", mock.Mock(Thread=_FakeThread)):
        moomoo._close_all_ctxs(timeout=0.25)  # returns despite the stuck close

    assert len(created) == 1
    thread = created[0]
    assert thread.daemon is True
    assert thread.target is ctx.close
    assert thread.started is True
    assert thread.joins == [0.25]  # bounded by the passed timeout
    with moomoo._ctx_lock:
        assert moomoo._live_ctxs == set()
    ctx.close.assert_not_called()  # close runs only via the (faked) thread
