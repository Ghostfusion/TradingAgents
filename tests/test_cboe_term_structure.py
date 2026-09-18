"""P0-5: the VIX9D/VIX3M term structure (a real VIX slope, never the equity-IV one)."""

import pytest

from tradingagents.dataflows import cboe


def _csv(*rows):
    return "DATE,OPEN,HIGH,LOW,CLOSE\n" + "".join(rows)


_CONTANGO = {
    "VIX9D": _csv("2026-09-15,14.0,15.0,13.5,14.20\n", "2026-09-16,14.1,15.2,13.9,14.60\n"),
    "VIX3M": _csv("2026-09-15,18.0,19.0,17.5,18.10\n", "2026-09-16,18.2,19.1,18.0,18.90\n"),
}
_BACKWARDATION = {
    "VIX9D": _csv("2026-09-16,25.0,27.0,24.0,26.40\n"),
    "VIX3M": _csv("2026-09-16,21.0,22.0,20.5,21.10\n"),
}


class _Resp:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


def _patch(monkeypatch, payloads, *, fail=()):
    """Stand in for the CDN: the real ``_vix_last_level`` still parses and still
    owns its own error handling, which is the half under test."""
    import requests

    def _fake_get(url, timeout=None):
        name = url.rsplit("/", 1)[-1].split("_")[0]  # VIX9D_History.csv -> VIX9D
        if name in fail:
            raise requests.ConnectionError("no route to host")
        return _Resp(payloads[name])

    monkeypatch.setattr(cboe.requests, "get", _fake_get)
    monkeypatch.setattr(cboe, "_vix_cache_read", lambda: None)
    monkeypatch.setattr(cboe, "_vix_cache_write", lambda payload: None)


def test_contango_and_backwardation_map_to_the_two_states(monkeypatch):
    """Acceptance: the two fixtures map to the two states, on the SHARED slope
    convention (long minus short) so the number is comparable with the equity-IV
    slope - which is a different object and is never returned under a VIX name."""
    _patch(monkeypatch, _CONTANGO)
    up = cboe.vix_term_structure()
    assert up["vix9d"] == pytest.approx(14.60)
    assert up["vix3m"] == pytest.approx(18.90)
    assert up["slope"] == pytest.approx(4.30)
    assert up["state"] == "contango"
    assert up["as_of"] == "2026-09-16"
    assert "not one name's equity-IV slope" in up["basis"]
    assert up["reason"] is None

    _patch(monkeypatch, _BACKWARDATION)
    down = cboe.vix_term_structure()
    assert down["slope"] == pytest.approx(-5.30)
    assert down["state"] == "backwardation"


def test_an_unreachable_source_is_none_with_the_reason(monkeypatch):
    """Acceptance: an unreachable source yields None and a printed reason - never
    the equity-IV slope under a VIX name, and never a defaulted state."""
    _patch(monkeypatch, _CONTANGO, fail=("VIX3M",))
    got = cboe.vix_term_structure()
    assert got["vix3m"] is None
    assert got["vix9d"] == pytest.approx(14.60)
    assert got["slope"] is None
    assert got["state"] is None
    assert "VIX3M" in got["reason"]
    assert "unavailable" in got["basis"]


def test_a_zero_slope_is_contango_not_stressed(monkeypatch):
    """A flat curve is not stress: the state is contango at slope 0, and only a
    negative slope is backwardation."""
    _patch(monkeypatch, {"VIX9D": _csv("2026-09-16,18.0,18.0,18.0,18.00\n"),
                         "VIX3M": _csv("2026-09-16,18.0,18.0,18.0,18.00\n")})
    got = cboe.vix_term_structure()
    assert got["slope"] == pytest.approx(0.0)
    assert got["state"] == "contango"


def test_the_cache_serves_a_second_call(monkeypatch):
    """One fetch per day: the files are end-of-day, so a cached read is served
    without touching the network."""
    calls: list[str] = []

    def _fake(name):
        calls.append(name)
        return "2026-09-16", 20.0

    monkeypatch.setattr(cboe, "_vix_last_level", _fake)
    monkeypatch.setattr(cboe, "_vix_cache_read", lambda: None)
    stored: dict = {}
    monkeypatch.setattr(cboe, "_vix_cache_write", lambda payload: stored.update(payload))
    first = cboe.vix_term_structure()
    assert len(calls) == 2
    monkeypatch.setattr(cboe, "_vix_cache_read", lambda: stored)
    second = cboe.vix_term_structure()
    assert len(calls) == 2  # no second fetch
    assert second["vix9d"] == pytest.approx(first["vix9d"])


def test_the_options_surface_vendor_is_untouched(monkeypatch):
    """The VIX history lives in the SAME module as the delayed options-chain
    vendor: adding it must not disturb the routed surface."""
    assert callable(cboe.get_options_surface)
    assert "delayed_quotes" in cboe.CBOE_OPTIONS_URL
    assert "daily_prices" in cboe.CBOE_VIX_HISTORY_URL
