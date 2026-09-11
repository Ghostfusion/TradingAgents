"""Seeking Alpha per-ticker news feed (public RSS, keyless, no auth).

Seeking Alpha publishes an unattributed RSS feed per ticker at
``https://seekingalpha.com/api/sa/combined/{TICKER}.xml`` (articles + news).
There is no official public API; this adapter consumes the public feed only —
never the paywalled article pages, quant-grade/ratings endpoints, or the
undocumented internal JSON APIs (Cloudflare-protected, ToS-fragile). FMP
already owns earnings-call transcripts and the project computes its own factor
scores, so those SA layers are intentionally out of scope here.

The feed carries titles, publish times, links, and contributor author names —
no summaries. That makes this an **opinion channel**: analyst commentary with
the stance in the headline, not confirmable market facts. The rendered block
pins the source as contributor opinion so the news analyst never treats it as
a fact basis (mirrors the project's honesty folds).
"""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from .config import get_config
from .date_window import in_window as _in_window
from .errors import NoMarketDataError, VendorRateLimitError
from .symbol_utils import require_symbol

# Seeking Alpha blocks default Python User-Agents; pass a standard browser one
# (the same workaround the other keyless HTTP vendors use).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_BASE_URL = "https://seekingalpha.com/api/sa/combined"
_TIMEOUT = 15
_ARTICLE_LIMIT = 20

# Opinion pin rendered with every feed so the consuming agent models the
# source as authored commentary, never as observable market fact.
_OPINION_PIN = (
    "OPINION CHANNEL: below are individual Seeking Alpha contributor "
    "titles/commentary (single author, no summary). Nothing here is a "
    "primary market fact - use for sentiment/catalyst context only, and "
    "never attribute numbers to this feed."
)


def _fetch_feed(ticker: str) -> ElementTree.Element:
    """Fetch + parse the combined RSS feed for ``ticker`` (UPPERCASE)."""
    url = f"{_BASE_URL}/{ticker}.xml"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise VendorRateLimitError(
                f"Seeking Alpha rate limit (HTTP 429) for {ticker}"
            ) from None
        raise NoMarketDataError(ticker, detail=f"seekingalpha HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise NoMarketDataError(ticker, detail=f"seekingalpha {e.reason}") from e
    try:
        return ElementTree.fromstring(body)
    except ElementTree.ParseError as e:
        raise NoMarketDataError(ticker, detail=f"seekingalpha non-XML feed ({e})") from e


def _text(item: ElementTree.Element, local: str) -> str | None:
    """Text of a direct child by local tag name (strips the RSS namespace)."""
    for child in item:
        tag = str(child.tag or "").split("}", 1)[-1]
        txt = child.text
        if tag == local and txt and txt.strip():
            return txt.strip()
    return None


def _parse_items(root: ElementTree.Element) -> list[dict[str, str]]:
    """Flat item dicts: title / link / pub_date (RFC 2822 string) / author."""
    out: list[dict[str, str]] = []
    channel = root.find("channel") or root
    for item in channel.findall("item"):
        title = _text(item, "title") or "(no title)"
        link = _text(item, "link") or ""
        pub = _text(item, "pubDate") or ""
        author = _text(item, "author_name") or ""
        out.append(
            {"title": title, "link": link, "pub_date": pub, "author": author}
        )
    return out


def _render(items: list[dict[str, str]], ticker: str, start: str, end: str) -> str:
    """Markdown block in the shape of the other news vendors, with the pin."""
    lines = [
        f"## {ticker} News - Seeking Alpha (contributor commentary)",
        "",
        _OPINION_PIN,
        "",
    ]
    for it in items:
        by = f" by {it['author']}" if it["author"] else ""
        stamp = f" ({it['pub_date']})" if it["pub_date"] else ""
        lines.append(f"- **{it['title']}**{by}{stamp}")
        if it["link"]:
            lines.append(f"  {it['link']}")
    if not items:
        lines.append(
            f"No Seeking Alpha articles for {ticker} from {start} to {end} "
            "(commentary coverage in window)"
        )
    return "\n".join(lines)


def get_news_seekingalpha(ticker: str, start_date: str, end_date: str) -> str:
    """Ticker news/commentary from the Seeking Alpha public RSS feed.

    Keyless - no API key, no config entry. The feed has no summaries, only
    contributor titles/author/date/link, and the block is pinned as an opinion
    channel (never a fact basis). Raises the typed vendor errors
    (``VendorRateLimitError`` / ``NoMarketDataError``) so the router treats it
    like every other news vendor.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = datetime.fromisoformat(start_date + "T00:00:00")
    end_dt = datetime.fromisoformat(end_date + "T00:00:00")

    canonical = require_symbol(ticker)
    resolved = "" if canonical == ticker else f" (resolved to {canonical})"
    label = f"{ticker}{resolved}"

    try:
        root = _fetch_feed(canonical)
        items = _parse_items(root)
        keep: list[dict[str, str]] = []
        for it in items:
            pub_dt = None
            if it["pub_date"]:
                try:
                    pub_dt = parsedate_to_datetime(str(it["pub_date"]))
                except (ValueError, OverflowError, TypeError):
                    pub_dt = None
            if _in_window(pub_dt, start_dt, end_dt):
                keep.append(it)
        limit = int(get_config().get("news_article_limit", _ARTICLE_LIMIT) or _ARTICLE_LIMIT)
        return _render(keep[:limit], label, start_date, end_date)
    except (NoMarketDataError, VendorRateLimitError):
        raise
    except Exception as e:  # noqa: BLE001 - degrade like every news vendor
        raise NoMarketDataError(ticker, detail=f"seekingalpha {e}") from None
