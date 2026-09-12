"""Moomoo connection cap: parallel workers must not exceed the gateway limit."""

import threading
import time
from unittest import mock

import pytest

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
    """Regression: a stuck ctx.close() must not hold the interpreter alive.

    Asserted as BEHAVIOUR: the call returns within its timeout although the
    close parks forever, the close was attempted, the registry is cleared, and
    the parked close is running on a daemon thread (which is what "cannot hold
    the interpreter alive" means). The previous version pinned the wiring
    instead - it asserted ``thread.target is ctx.close`` - so it failed the
    moment every close started going through one bounded helper, without any
    behaviour changing.
    """
    ctx = _HungCtx()
    with moomoo._ctx_lock:
        moomoo._live_ctxs.clear()
        moomoo._live_ctxs.add(ctx)

    t0 = time.monotonic()
    moomoo._close_all_ctxs(timeout=0.25)
    elapsed = time.monotonic() - t0

    assert elapsed < 5.0, "a stuck close must not block the caller"
    assert ctx.close_started.is_set(), "the close must still be attempted"
    with moomoo._ctx_lock:
        assert ctx not in moomoo._live_ctxs, "a closed context must leave the registry"
    parked = [
        t for t in threading.enumerate() if t.is_alive() and t.daemon and t.name == "moomoo-bounded"
    ]
    assert parked, "the abandoned close must run on a daemon thread"


def test_public_close_all_contexts_delegates():
    """The web app closes in-process SDK clients through this public wrapper.

    (Its session-end fixture and jobs.shutdown() both call it: the SDK's threads
    are non-daemon and only end via close or a timeout.)
    """
    with mock.patch.object(moomoo, "_close_all_ctxs") as inner:
        moomoo.close_all_contexts(timeout=0.5)
    inner.assert_called_once_with(timeout=0.5)


# ---------------------------------------------------------------------------
# W-P0-2 (engine side): every SDK interaction that can park forever is bounded
# ---------------------------------------------------------------------------


class _HungCtx:
    """A context whose ``close()`` never returns (the dead receive loop)."""

    def __init__(self):
        self.close_started = threading.Event()

    def close(self, *_a, **_k):
        self.close_started.set()
        threading.Event().wait(5)

    def __getattr__(self, _name):  # any other SDK call: no-op
        return lambda *_a, **_k: None


def test_ensure_ctx_bounds_a_blocking_constructor(monkeypatch):
    """A reachable-but-wedged OpenD must not freeze the caller for good.

    The constructor does the TCP connect + handshake and takes no deadline; the
    probe passes (the port is open) while the handshake never completes.
    """
    import moomoo as sdk

    def blocking_ctor(**_kwargs):
        threading.Event().wait(5)

    monkeypatch.setattr(moomoo, "_get_moomoo_config", lambda: {"host": "127.0.0.1", "port": 11111})
    monkeypatch.setattr(moomoo, "_probe_or_use_cache", lambda _h, _p: True)
    monkeypatch.setattr(moomoo, "_timeout_setting", lambda _k, _d: 0.2)
    monkeypatch.setattr(sdk, "OpenQuoteContext", blocking_ctor, raising=False)
    monkeypatch.setattr(moomoo._tls, "moomoo_ctx", None, raising=False)

    t0 = time.monotonic()
    with pytest.raises(moomoo.MoomooNotConfiguredError) as exc:
        moomoo._ensure_ctx()
    assert time.monotonic() - t0 < 5.0, "the constructor must be abandoned on time"
    assert "handshake" in str(exc.value)


def test_sdk_call_timeout_is_not_blocked_by_a_hung_close(monkeypatch):
    """The 70 h zombie: the timeout handler hung inside ctx.close().

    The branch runs *because* the receive loop is suspect; an unbounded close
    there means the call never raises and nothing records an error at all.
    """
    ctx = _HungCtx()
    monkeypatch.setattr(moomoo._tls, "moomoo_ctx", ctx, raising=False)
    monkeypatch.setattr(moomoo, "_timeout_setting", lambda _k, _d: 0.2)

    def slow(*_a, **_k):
        threading.Event().wait(5)

    t0 = time.monotonic()
    with pytest.raises(moomoo.VendorRateLimitError):
        moomoo._sdk_call(slow, timeout=0.2)
    assert time.monotonic() - t0 < 5.0, "the timeout path must still return"


def test_close_ctx_is_bounded_and_forgets_a_hung_context(monkeypatch):
    ctx = _HungCtx()
    monkeypatch.setattr(moomoo._tls, "moomoo_ctx", ctx, raising=False)
    monkeypatch.setattr(moomoo, "_timeout_setting", lambda _k, _d: 0.2)
    with moomoo._ctx_lock:
        moomoo._live_ctxs.add(ctx)

    t0 = time.monotonic()
    moomoo._close_ctx()
    assert time.monotonic() - t0 < 5.0
    assert ctx not in moomoo._live_ctxs
    assert getattr(moomoo._tls, "moomoo_ctx", None) is None


def test_cap_eviction_does_not_hold_the_lock_across_a_hung_close(monkeypatch):
    """Eviction closes OUTSIDE _ctx_lock, or one hung close freezes every thread."""
    hung = [_HungCtx() for _ in range(3)]
    monkeypatch.setattr(moomoo, "_timeout_setting", lambda _k, _d: 1.0)
    monkeypatch.setattr(moomoo, "_max_open_ctxs", lambda: 1)
    with moomoo._ctx_lock:
        for ctx in hung:
            moomoo._live_ctxs.add(ctx)

    worker = threading.Thread(target=moomoo._cap_open_ctxs, daemon=True)
    worker.start()
    # WHICH context is evicted first is a set-iteration detail; wait for any of
    # them to park, not for a specific one (the first version asserted hung[0]
    # and passed in isolation while failing in the full suite).
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any(c.close_started.is_set() for c in hung):
        time.sleep(0.02)
    assert any(c.close_started.is_set() for c in hung), "the eviction never reached a close"
    # While that close is parked, the registry lock must be free for other threads.
    acquired = moomoo._ctx_lock.acquire(timeout=0.2)
    if acquired:
        moomoo._ctx_lock.release()
    worker.join(timeout=5)
    assert acquired, "the registry lock was held across a blocking close"
    with moomoo._ctx_lock:
        moomoo._live_ctxs.difference_update(hung)


# ---------------------------------------------------------------------------
# Interpreter exit: the SDK's non-daemon threads must not outlive the process
# ---------------------------------------------------------------------------


class _FakeExecutor:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _OrphanCtx:
    """A context that behaves like the SDK's: closing installs a NEW executor.

    ``open_context_base._close_callback_executor`` does exactly this when
    auto-reconnect is on (it closes the old executor and replaces
    ``self._callback_executor`` with a fresh one), which is how a close leaves
    a thread behind with nothing left to stop it. The attribute name matters:
    the cleanup reads ``ctx._callback_executor`` like the SDK writes it.
    """

    def __init__(self):
        self._callback_executor = _FakeExecutor()

    def close(self, *_a, **_k):
        self._callback_executor.close()
        self._callback_executor = _FakeExecutor()


def test_bounded_close_stops_the_orphan_executor():
    """Regression: a full suite printed its summary and then hung ~50 min.

    The exit probe showed MainThread parked in ``threading._shutdown`` joining
    two non-daemon ``callback_executor`` threads; the SDK installs a fresh
    executor while closing the old one, so nothing was left to stop it.
    """
    ctx = _OrphanCtx()
    stale = ctx._callback_executor
    assert moomoo._bounded_close(ctx, timeout=1.0) is True
    assert stale.closed is True, "the SDK's own close must still run"
    assert ctx._callback_executor.closed is True, (
        "the executor the close installed must be stopped, or its thread idles "
        "in queue.get() forever and holds the interpreter open"
    )


def test_orphan_executor_cleanup_never_raises():
    class _Bad:
        def close(self):
            raise RuntimeError("nope")

    assert moomoo._close_orphan_executor(_Bad()) is None
    assert moomoo._close_orphan_executor(object()) is None
    assert moomoo._close_orphan_executor(None) is None


def test_daemonise_sdk_threads_sets_the_sdk_flag():
    """Every SDK thread created afterwards is a daemon, so an orphan cannot
    block interpreter exit (the flag is read when the thread starts)."""
    sys_config = pytest.importorskip("moomoo.common.sys_config")
    sys_config.SysConfig.set_all_thread_daemon(False)
    moomoo._daemonise_sdk_threads()
    assert sys_config.SysConfig.get_all_thread_daemon() is True
