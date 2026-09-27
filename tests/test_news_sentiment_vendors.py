"""News/sentiment providers (GDELT, NewsAPI, Benzinga) - hermetic tests.

Phase A-C of the news/sentiment enhancement: GDELT (keyless news article list),
NewsAPI (key-gated global headlines) and Benzinga (free ticker-scoped financial
news). Covers key resolution, typed-error degradation, render shape, and the
interface registration. Network is mocked (``_requests.get`` / module getters).
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest import mock

import pytest

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
)

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# GDELT (keyless)
# ---------------------------------------------------------------------------


def test_gdelt_no_key_needed():
    from tradingagents.dataflows import gdelt

    # GDELT is keyless: the config/env key lookup must be a no-op returning None
    # but the fetch still runs (uses _gdelt_get without a token).
    assert gdelt.BASE  # import succeeded


def test_gdelt_articles_render_without_a_tone_claim(monkeypatch):
    from tradingagents.dataflows import gdelt

    payload = [
        {
            "title": "AAPL beats earnings",
            "url": "https://x.com/a",
            "source": "cnn.com",
            "seendate": "20260830000000",
        }
    ]
    with mock.patch.object(gdelt, "_gdelt_get", return_value=payload):
        out = gdelt.get_news_gdelt("AAPL", "2026-08-28", "2026-08-30")
    assert "## AAPL News — GDELT" in out
    assert "AAPL beats earnings" in out
    assert "https://x.com/a" in out
    assert "tone" not in out.lower(), (
        "the DOC artlist response carries no per-article tone; the render must "
        "not imply one (the claim was never measured live - all fixtures were "
        "hand-written mocks)"
    )


def test_gdelt_no_articles_raises(monkeypatch):
    from tradingagents.dataflows import gdelt

    with mock.patch.object(gdelt, "_gdelt_get", return_value=[]), pytest.raises(NoMarketDataError):
        gdelt.get_news_gdelt("AAPL", "2026-08-28", "2026-08-30")


def test_gdelt_window_uses_the_documented_datetime_form(monkeypatch):
    """STARTDATETIME/ENDDATETIME are documented as YYYYMMDDHHMMSS.

    The old call sites sent ``YYYY-MM-DD`` + ``"000000"``, a string that is not
    that format - and a window the API cannot read is a window it does not
    apply, which on a historical run is the lookahead class this repo treats as
    critical.
    """
    from tradingagents.dataflows import gdelt

    seen: dict = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"articles": [{"title": "t", "seendate": "20260830000000"}]}

    def _get(url, params=None, timeout=None):
        seen.update(params or {})
        return _Resp()

    monkeypatch.setattr(gdelt._requests, "get", _get)
    gdelt.get_news_gdelt("AAPL", "2026-08-28", "2026-08-30")
    assert seen["startdatetime"] == "20260828000000"
    assert seen["enddatetime"] == "20260830235959"


def test_gdelt_rate_limited_text_body_is_a_rate_limit(monkeypatch):
    """A 429 body is plain text with no content-type - measured live 2026-09-27.

    Parsing the body before the status check classified GDELT's rate limit as
    "non-JSON response" (NoMarketDataError), a no-data verdict that skips the
    rate-limit path entirely.
    """
    from tradingagents.dataflows import gdelt
    from tradingagents.dataflows.errors import VendorRateLimitError

    class _Resp:
        status_code = 429
        text = "Please limit requests to one every 5 seconds or contact kalev..."

        @staticmethod
        def json():
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(gdelt, "_MAX_RETRIES", 0)
    monkeypatch.setattr(gdelt._requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(VendorRateLimitError):
        gdelt._gdelt_get({"query": '"AAPL"'})


def test_gdelt_tone_series_names_the_missing_capability(monkeypatch):
    """The tone series refuses with the reason, and never fetches to pretend.

    GDELT's ``tone`` is a query filter/sort in DOC 2.0; the artlist response has
    no per-article tone field, so there is nothing to aggregate. The old
    producer aggregated a mocked field and would have returned "tone fields
    missing" forever against the live API.
    """
    from tradingagents.dataflows import gdelt

    def _must_not_fetch(*a, **k):
        raise AssertionError("the tone series must not fetch: it cannot measure")

    monkeypatch.setattr(gdelt, "_gdelt_get", _must_not_fetch)
    out = gdelt.get_gdelt_tone_series("AAPL", look_back_days=5)
    assert "unavailable" in out
    assert "no per-article tone" in out
    assert gdelt._sentiment_points_gdelt("AAPL", "2026-08-28", "2026-08-30") is None


# ---------------------------------------------------------------------------
# NewsAPI (key-gated)
# ---------------------------------------------------------------------------


def test_newsapi_missing_key(monkeypatch):
    from contextlib import ExitStack

    from tradingagents.dataflows import newsapi
    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("NEWSAPI_API_KEY", raising=False)
        monkeypatch.setattr(newsapi, "newsapi_api_key", lambda: None)
        with pytest.raises(VendorNotConfiguredError):
            newsapi.get_global_news_newsapi("2026-08-30")


def test_newsapi_renders_global(monkeypatch):
    from tradingagents.dataflows import newsapi

    payload = {
        "status": "ok",
        "articles": [
            {"title": "Fed signals", "description": "macro",
             "source": {"name": "Reuters"}, "url": "https://r.com",
             "publishedAt": "2026-08-30T10:00:00Z"},
        ],
    }
    with mock.patch.object(newsapi, "_newsapi_get", return_value=payload):
        out = newsapi.get_global_news_newsapi("2026-08-30")
    assert "Global Macro News — NewsAPI.org" in out
    assert "Fed signals" in out


def test_newsapi_error_status_degrades(monkeypatch):
    from tradingagents.dataflows import newsapi

    with mock.patch.object(newsapi, "_newsapi_get") as m:
        m.side_effect = NoMarketDataError("newsapi", "x", detail="no articles")
        with pytest.raises(NoMarketDataError):
            newsapi.get_news_newsapi("AAPL", "2026-08-28", "2026-08-30")


def test_newsapi_registered():
    from tradingagents.dataflows.interface import VENDOR_METHODS

    assert "newsapi" in VENDOR_METHODS["get_news"]
    assert "newsapi" in VENDOR_METHODS["get_global_news"]


# ---------------------------------------------------------------------------
# Benzinga (key-gated)
# ---------------------------------------------------------------------------


def test_benzinga_negotiates_json_because_the_default_response_is_xml(monkeypatch):
    """The transport must ask for JSON; Benzinga's default is XML.

    Measured live 2026-09-20 against ``api.benzinga.com`` with the real key:

        no header                  -> 200  Content-Type: application/xml
        Accept: application/json   -> 200  Content-Type: application/json
        format=json                -> 200  Content-Type: application/xml  (IGNORED)

    ``format=json`` is a query parameter the vendor silently ignores, and
    ``resp.json()`` on an XML body raises ``ValueError`` - which
    ``_benzinga_get`` typed as ``NoMarketDataError("non-JSON response")``. So
    every call failed:

        get_news_benzinga('AAPL', '2026-09-10', '2026-09-20')
        -> NoMarketDataError: No market data for 'benzinga' (queried as
           'news'): non-JSON response

    The four sibling tests all ``mock.patch.object(benzinga, "_benzinga_get")``,
    which is why this was invisible: they stub out the one layer that was
    broken. This test drives the real transport against a stand-in that behaves
    like the vendor - XML unless the ``Accept`` header asks for JSON.
    """
    from tradingagents.dataflows import benzinga

    JSON_BODY = (
        '[{"id": 61885260, "author": "Mohd Haider",'
        ' "created": "Sun, 20 Sep 2026 10:00:00 -0400",'
        ' "title": "Apple upgrade", "teaser": "analyst raises target",'
        ' "url": "https://www.benzinga.com/news/26/09/61885260/apple-upgrade"}]'
    )
    XML_BODY = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<result is_array="true"><item><id>61885260</id></item></result>'
    )

    class _VendorLike:
        """Behaves like the vendor: XML unless Accept asks for JSON."""

        status_code = 200
        sent_headers: dict = {}

        def __init__(self, **kw):
            type(self).sent_headers = kw.get("headers") or {}

        @property
        def text(self) -> str:
            accept = str((type(self).sent_headers or {}).get("Accept") or "")
            return JSON_BODY if "json" in accept.lower() else XML_BODY

        def json(self):
            accept = str((type(self).sent_headers or {}).get("Accept") or "")
            if "json" not in accept.lower():
                raise ValueError("Expecting value: line 1 column 1 (char 0)")
            import json as _json

            return _json.loads(JSON_BODY)

    monkeypatch.setattr(benzinga, "_requests", type("R", (), {"get": staticmethod(lambda *a, **k: _VendorLike(**k))}))
    monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: "bz.TEST")

    out = benzinga.get_news_benzinga("AAPL", "2026-09-10", "2026-09-20")
    assert "## AAPL News — Benzinga" in out
    assert "Apple upgrade" in out
    assert "analyst raises target" in out
    # and the request actually asked for JSON
    assert "json" in str(_VendorLike.sent_headers.get("Accept", "")).lower()


def test_benzinga_decodes_html_entities_in_headlines(monkeypatch):
    """The vendor escapes ampersands; the render must not pass them through.

    Measured live 2026-09-20: the payload carries
    ``Technology Hardware, Storage &amp; Peripherals Industry``. The report is
    markdown read by a human and by the analyst, so a raw entity is a wrong
    string, not a cosmetic wart.
    """
    from tradingagents.dataflows import benzinga

    payload = [
        {"title": "Evaluating Apple In Technology Hardware, Storage &amp; Peripherals",
         "created": "2026-09-10T12:00:00", "author": "Benzinga Insights",
         "teaser": "R&amp;D spend &amp; margins", "url": "https://benzinga.com/1"},
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_news_benzinga("AAPL", "2026-09-10", "2026-09-20")
    assert "Storage & Peripherals" in out
    assert "R&D spend & margins" in out
    assert "&amp;" not in out


def test_benzinga_missing_key(monkeypatch):
    from tradingagents.dataflows import benzinga

    with ExitStack() as stack:
        stack.enter_context(monkeypatch.context())
        monkeypatch.delenv("BENZINGA_API_KEY", raising=False)
        monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: None)
        with pytest.raises(VendorNotConfiguredError):
            benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")


def test_benzinga_renders_teaser(monkeypatch):
    from tradingagents.dataflows import benzinga

    payload = [
        {"title": "AAPL upgrade", "created": "2026-08-29T12:00:00",
         "author": "Benzinga", "teaser": "analyst raises target",
         "url": "https://benzinga.com/1"},
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")
    assert "## AAPL News — Benzinga" in out
    assert "AAPL upgrade" in out
    assert "analyst raises target" in out


def test_benzinga_no_articles_raises(monkeypatch):
    from tradingagents.dataflows import benzinga

    with mock.patch.object(benzinga, "_benzinga_get", return_value=[]), pytest.raises(NoMarketDataError):
        benzinga.get_news_benzinga("AAPL", "2026-08-28", "2026-08-30")


def test_benzinga_registered():
    from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS

    assert "benzinga" in VENDOR_LIST
    assert "benzinga" in VENDOR_METHODS["get_news"]


# ---------------------------------------------------------------------------
# gdelt registered + tool wrapper
# ---------------------------------------------------------------------------


def test_gdelt_registered_and_tool():
    from tradingagents.agents.utils.agent_utils import get_gdelt_sentiment
    from tradingagents.dataflows.interface import VENDOR_METHODS

    assert "gdelt" in VENDOR_METHODS["get_news"]
    assert "gdelt" in VENDOR_METHODS["get_global_news"]
    assert callable(getattr(get_gdelt_sentiment, "invoke", None))


def test_gdelt_tool_degrades_on_unavailable(monkeypatch):
    from tradingagents.agents.utils.agent_utils import get_gdelt_sentiment
    from tradingagents.dataflows import gdelt

    with mock.patch.object(
        gdelt, "get_gdelt_tone_series", side_effect=NoMarketDataError("gdelt", "x")
    ):
        out = get_gdelt_sentiment.invoke({"ticker": "AAPL", "look_back_days": 5})
    assert "unavailable" in out
