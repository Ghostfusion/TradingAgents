"""Seeking Alpha RSS vendor tests (hermetic; mock the ``urlopen`` seam).

No network: the feed body is canned XML and the fetch errors are simulated,
so CI runs deterministically without hitting seekingalpha.com.
"""

from __future__ import annotations

import urllib.error
from unittest import mock

import pytest

from tradingagents.dataflows import seekingalpha as module
from tradingagents.dataflows.errors import NoMarketDataError, VendorRateLimitError

pytestmark = pytest.mark.timeout(180)

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:sa="http://seekingalpha.com" version="2.0">
<channel>
<title>AAPL headlines</title>
<item>
  <title>In Window Piece</title>
  <link>https://seekingalpha.com/article/111</link>
  <guid>https://seekingalpha.com/Article:111</guid>
  <pubDate>Tue, 08 Sep 2026 15:00:39 -0400</pubDate>
  <sa:author_name>Ann Analyst</sa:author_name>
</item>
<item>
  <title>Out Of Window Piece</title>
  <link>https://seekingalpha.com/article/222</link>
  <guid>https://seekingalpha.com/Article:222</guid>
  <pubDate>Mon, 03 Aug 2026 09:00:00 -0400</pubDate>
  <sa:author_name>Calm Contributor</sa:author_name>
</item>
</channel>
</rss>
"""

def _resp(payload: bytes | str = _FEED, status: int = 200):
    """A context-manager mock standing in for a urllib response object."""
    r = mock.Mock()
    r.status = status
    if status == 200:
        r.read.return_value = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    else:
        r.read.side_effect = urllib.error.HTTPError(
            "https://seekingalpha.com/api/sa/combined/AAPL.xml",
            status, "boom", None, None,
        )
    r.__enter__ = mock.Mock(return_value=r)
    r.__exit__ = mock.Mock(return_value=False)
    return r


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def test_renders_title_author_date_link_opinion_pin():
    with mock.patch.object(module.urllib.request, "urlopen", return_value=_resp()) as m:
        out = module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")
        assert "OPINION CHANNEL" in out
        assert "- **In Window Piece** by Ann Analyst (Tue, 08 Sep 2026 15:00:39 -0400)" in out
        assert "https://seekingalpha.com/article/111" in out
        # out-of-window article is filtered
        assert "Out Of Window Piece" not in out
        m.assert_called_once()
        headers = {k.lower(): v for k, v in m.call_args[0][0].headers.items()}
        assert headers.get("user-agent", "").startswith("Mozilla/5.0")


def test_empty_feed_renders_no_articles():
    from xml.etree import ElementTree

    root = ElementTree.fromstring("<rss><channel></channel></rss>")
    with mock.patch.object(module, "_fetch_feed", return_value=root):
        out = module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")
        assert "No Seeking Alpha articles for AAPL" in out


def test_lowercase_ticker_resolves_and_renders_label():
    with mock.patch.object(module.urllib.request, "urlopen", return_value=_resp()):
        out = module.get_news_seekingalpha("aapl", "2026-09-01", "2026-09-10")
        assert "AAPL" in out and "not-a-real-tag" not in out


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


def _http_error(status: int):
    return urllib.error.HTTPError(
        "https://seekingalpha.com/api/sa/combined/AAPL.xml",
        status, "boom", None, None,
    )


def test_http_429_raises_rate_limit():
    with (
        mock.patch.object(module.urllib.request, "urlopen", side_effect=_http_error(429)),
        pytest.raises(VendorRateLimitError),
    ):
        module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")


def test_http_404_raises_no_data():
    with (
        mock.patch.object(module.urllib.request, "urlopen", side_effect=_http_error(404)),
        pytest.raises(NoMarketDataError),
    ):
        module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")


def test_broken_xml_raises_no_data():
    r = mock.Mock()
    r.status = 200
    r.read.return_value = b"<rss><channel><item>oops"
    r.__enter__ = mock.Mock(return_value=r)
    r.__exit__ = mock.Mock(return_value=False)
    with (
        mock.patch.object(module.urllib.request, "urlopen", return_value=r),
        pytest.raises(NoMarketDataError),
    ):
        module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")


def test_invalid_dates_raise_value_error():
    with pytest.raises(ValueError):
        module.get_news_seekingalpha("AAPL", "not-a-date", "2026-09-10")


def test_network_urlerror_raises_no_data():
    def _boom(*a, **k):
        raise urllib.error.URLError("connection refused")

    with (
        mock.patch.object(module.urllib.request, "urlopen", side_effect=_boom),
        pytest.raises(NoMarketDataError),
    ):
        module.get_news_seekingalpha("AAPL", "2026-09-01", "2026-09-10")


# ---------------------------------------------------------------------------
# interface registration
# ---------------------------------------------------------------------------


def test_registered_as_tail_of_get_news():
    from tradingagents.dataflows.interface import VENDOR_METHODS

    chain = list(VENDOR_METHODS["get_news"].keys())
    assert "seekingalpha" in chain
    assert chain[-1] == "seekingalpha"  # commentary tail, never primary
