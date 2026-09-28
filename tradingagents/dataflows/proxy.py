"""DEF 14A proxy statements - download and governance-table extraction.

UNIV-GOV. The repository had **no HTML parsing capability at all**: a tree-wide
grep for ``read_html``/``BeautifulSoup``/``lxml``/``html.parser``/``HTMLParser``
over ``tradingagents/`` returned zero hits, and a proxy statement carries no
XBRL, so the SEC financial machinery cannot be reused. This adds the capability
with the **standard library only** - no new dependency - via
``html.parser.HTMLParser``, plus a classifier that keeps the tables that are
governance-relevant.

A proxy is a very large HTML document whose governance content lives in tables,
so the table is the unit of extraction: each is captured with the heading that
names it, and the classifier matches that heading against a published list of
governance tables. Extraction is deliberately shallow - text and cells, never
interpretation - so a reader can see the numbers as filed.
"""

from __future__ import annotations

from html.parser import HTMLParser

__all__ = [
    "GOVERNANCE_HEADINGS",
    "extract_tables",
    "fetch_proxy_html",
    "governance_tables",
]

#: Headings that name a governance table a proxy statement is required to carry
#: (Regulation S-K Item 402 / Item 403). Matched case-insensitively against the
#: text preceding the table, so a re-worded caption still lands.
GOVERNANCE_HEADINGS = (
    "summary compensation table",
    "compensation actually paid",
    "pay versus performance",
    "director compensation",
    "outstanding equity awards",
    "option exercises",
    "stock vested",
    "pension benefits",
    "nonqualified deferred compensation",
    "equity compensation plan information",
    "security ownership",
    "beneficial ownership",
    "principal stockholders",
    "related person transactions",
)

#: How much preceding text is kept as a table's heading. A real caption is short;
#: a long run of prose means the table simply follows narrative, and the tail is
#: the closest thing to a title.
_HEADING_CHARS = 240


class _TableParser(HTMLParser):
    """Collect every ``<table>`` as rows of cleaned cell text, with its heading."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict] = []
        self._ctx: list[str] = []
        self._last: str | None = None
        self._in_table = False
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._heading: str | None = None

    # -- context (the text that names a table) -----------------------------
    def _flush_ctx(self) -> None:
        text = " ".join("".join(self._ctx).split())
        self._ctx = []
        if text:
            self._last = text[-_HEADING_CHARS:]

    def _take_context(self) -> str | None:
        text = " ".join("".join(self._ctx).split())
        self._ctx = []
        if text:
            self._last = text[-_HEADING_CHARS:]
        return self._last

    # -- tags --------------------------------------------------------------
    def handle_starttag(self, tag, attrs):  # noqa: ARG002
        name = tag.lower()
        if name == "table":
            if self._in_table:
                return
            self._heading = self._take_context()
            self._in_table = True
            self._rows = []
            self._row = None
            self._cell = None
        elif self._in_table:
            if name == "tr":
                self._row = []
            elif name in ("td", "th"):
                self._cell = []
        elif name in ("h1", "h2", "h3", "h4", "caption", "p", "div"):
            self._flush_ctx()

    def handle_endtag(self, tag):
        name = tag.lower()
        if name == "table" and self._in_table:
            self._in_table = False
            rows = [r for r in (self._rows or []) if r]
            if rows:
                self.tables.append({"heading": self._heading, "rows": rows})
            self._rows = self._row = self._cell = None
        elif self._in_table and name in ("td", "th"):
            if self._row is not None:
                self._row.append(" ".join("".join(self._cell or []).split()))
            self._cell = None
        elif self._in_table and name == "tr":
            if self._rows is not None and self._row:
                self._rows.append(self._row)
            self._row = None
        elif not self._in_table and name in ("h1", "h2", "h3", "h4", "caption", "p", "div"):
            self._flush_ctx()

    def handle_data(self, data):
        if self._in_table:
            if self._cell is not None:
                self._cell.append(data)
        else:
            self._ctx.append(data)


def extract_tables(html: str) -> list[dict]:
    """Every table in the document, with its heading, row and column counts.

    Returns an empty list for unparseable input rather than raising: a proxy
    that cannot be read is an absent observation, not a crash.
    """
    parser = _TableParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML must not raise
        return []
    out = []
    for index, table in enumerate(parser.tables):
        rows = table["rows"]
        out.append({
            "index": index,
            "heading": table["heading"],
            "rows": rows,
            "n_rows": len(rows),
            "n_cols": max((len(r) for r in rows), default=0),
        })
    return out


def governance_tables(html: str) -> list[dict]:
    """The subset of tables whose heading names a governance disclosure.

    The match is on the heading text alone, case-insensitively. A table with no
    recoverable heading is never claimed as governance - it is omitted, not
    guessed at.
    """
    kept = []
    for table in extract_tables(html):
        heading = (table.get("heading") or "").lower()
        if not heading:
            continue
        if any(marker in heading for marker in GOVERNANCE_HEADINGS):
            kept.append(table)
    return kept


def fetch_proxy_html(ticker: str, timeout: int = 30) -> tuple[str, str]:
    """The newest DEF 14A for a ticker as ``(url, html)``, or ``("", "")``.

    Reuses the EDGAR conventions ``sec_edgar`` already established - the same
    descriptive User-Agent SEC fair access requires, the same submissions
    endpoint, and the same archive path shape it uses for every other filing.
    Never raises: a missing proxy is an absent observation.
    """
    try:
        import urllib.request

        from tradingagents.dataflows.sec_edgar import _UA, _cik_for, _json_get

        cik = _cik_for(ticker)
        if not cik:
            return "", ""
        cik_int = int(cik)
        payload = _json_get(f"https://data.sec.gov/submissions/CIK{cik_int:010d}.json")
        recent = (payload or {}).get("filings", {}).get("recent", {}) or {}
        forms = recent.get("form", []) or []
        accessions = recent.get("accessionNumber", []) or []
        docs = recent.get("primaryDocument", []) or []
        for form, accession, doc in zip(forms, accessions, docs, strict=False):
            if str(form).strip().upper() != "DEF 14A" or not doc:
                continue
            # The archive path takes the accession with its dashes STRIPPED -
            # the same transform sec_edgar applies (sec_edgar.py:507). With the
            # dashed form the URL 404s.
            acc = str(accession).replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc}"
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
                return url, response.read().decode("utf-8", errors="replace")
        return "", ""
    except Exception:  # noqa: BLE001 - absent, never fatal
        return "", ""
