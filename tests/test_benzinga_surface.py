"""Benzinga event surface: transport, readers, routing and the gate.

Every test here defends a contract a plausible bug would break. The two
transport tests are the failing-first proofs for the defects found on
2026-09-20; the rest pin the behaviour the surface promises.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from tradingagents.dataflows.errors import NoMarketDataError


def _fake_response(body, status=200):
    """A minimal requests-Response stand-in carrying ``body``."""

    class _Resp:
        status_code = status

        @property
        def text(self):
            return body if isinstance(body, str) else json.dumps(body)

        def json(self):
            if isinstance(body, str):
                return json.loads(body)
            return body

    return _Resp()


def _recording_get(captured, body):
    """A ``requests.get`` replacement that records the URL it was handed."""

    def _get(url, params=None, timeout=None, headers=None, **kwargs):
        captured["url"] = url
        captured["params"] = dict(params or {})
        captured["headers"] = dict(headers or {})
        return _fake_response(body)

    return _get


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------


def test_transport_uses_the_caller_s_versioned_path(monkeypatch):
    """``BASE`` must be the API ROOT, not a hardcoded ``/api/v2``.

    Measured live 2026-09-20: news lives at ``/api/v2``, the calendars at
    ``/api/v2.1`` and the alt-data surface at ``/api/v1``. With ``BASE`` pinned
    to ``https://api.benzinga.com/api/v2`` every calendar request was built as
    ``/api/v2/v2.1/calendar/ratings`` and answered with the gateway's own
    ``no Route matched with those values`` 404 - the module could only ever
    reach the ``/v2`` routes, so no calendar was implementable.
    """
    from tradingagents.dataflows import benzinga

    captured: dict = {}
    monkeypatch.setattr(
        benzinga, "_requests", type("R", (), {"get": staticmethod(_recording_get(captured, {"ratings": []}))})
    )
    monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: "bz.TEST")

    benzinga._benzinga_get("v2.1/calendar/ratings", {"parameters[tickers]": "AAPL"})

    assert captured["url"] == "https://api.benzinga.com/api/v2.1/calendar/ratings"
    assert "/api/v2/v2.1/" not in captured["url"]
    # and the header is still the only way to get JSON
    assert "json" in str(captured["headers"].get("Accept", "")).lower()


def test_transport_unwraps_the_family_envelope(monkeypatch):
    """A dict-wrapped 200 must yield its rows, not ``None``.

    Benzinga is inconsistent: ``/v2/news`` answers with a bare list, every
    calendar answers with a dict keyed by its own family (``{"ratings": [...]}``),
    the alt-data surface answers ``{"data": [...]}`` and ``/v2.1/fundamentals``
    answers ``{"result": [...]}``. Collapsing any dict to ``None`` - which the
    transport did - reported every one of those routes as "no data" on a 200
    that carried rows. Only the bare-list news route ever worked.
    """
    from tradingagents.dataflows import benzinga

    assert benzinga._unwrap_records({"ratings": [{"id": 1}]}) == [{"id": 1}]
    assert benzinga._unwrap_records({"data": [{"id": 2}]}) == [{"id": 2}]
    assert benzinga._unwrap_records({"result": [{"id": 3}]}) == [{"id": 3}]
    assert benzinga._unwrap_records([{"id": 4}]) == [{"id": 4}]
    assert benzinga._unwrap_records({"nothing": "here"}) is None

    captured: dict = {}
    monkeypatch.setattr(
        benzinga, "_requests", type("R", (), {"get": staticmethod(_recording_get(captured, {"guidance": [{"ticker": "AAPL"}]}))})
    )
    monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: "bz.TEST")
    assert benzinga._benzinga_get("v2.1/calendar/guidance") == [{"ticker": "AAPL"}]


def test_transport_reports_an_ok_envelope_as_no_data(monkeypatch):
    """``{"ok": "true", "errors": [...]}`` is a failure, not a row list.

    ``/v3/fundamentals`` answers 200 with that shape. ``errors`` is itself a
    list, so a naive unwrapper would hand the caller the error strings as if
    they were records.
    """
    from tradingagents.dataflows import benzinga

    captured: dict = {}
    body = {"ok": "true", "errors": ["Please provide either from & to or date parameter"]}
    monkeypatch.setattr(
        benzinga, "_requests", type("R", (), {"get": staticmethod(_recording_get(captured, body))})
    )
    monkeypatch.setattr(benzinga, "benzinga_api_key", lambda: "bz.TEST")

    with pytest.raises(NoMarketDataError) as excinfo:
        benzinga._benzinga_get("v3/fundamentals", {"symbols": "AAPL"})
    assert "from & to" in str(excinfo.value)


# ---------------------------------------------------------------------------
# the five new capabilities
# ---------------------------------------------------------------------------


def test_guidance_renders_the_forward_range_and_prior(monkeypatch):
    """Guidance is the only forward growth producer; the range must survive."""
    from tradingagents.dataflows import benzinga

    payload = [
        {
            "date": "2026-07-30", "period": "Q4", "period_year": 2026,
            "is_primary": "Y", "prelim": "N", "importance": 5, "currency": "USD",
            "revenue_type": "GAAP", "revenue_guidance_min": "111688000000.000",
            "revenue_guidance_max": "113737000000.000",
            "revenue_guidance_est": "114332669224.000",
            "revenue_guidance_prior_min": "", "revenue_guidance_prior_max": "",
            "eps_guidance_min": "", "eps_guidance_max": "", "eps_guidance_est": "",
            "eps_guidance_prior_min": "", "eps_guidance_prior_max": "",
            "eps_type": "", "notes": "Revenue for 2026 Q4 is expected to up by 9 to 11% YoY",
        }
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_guidance_benzinga("AAPL", "2026-01-01", "2026-09-20")

    assert "Guidance Revisions" in out
    assert "111.69B" in out and "113.74B" in out and "114.33B" in out
    assert "9 to 11% YoY" in out
    assert "primary" in out
    # an absent prior range is a named gap, never a zero
    assert "prior" not in out


def test_fda_renders_the_drug_indication_and_sponsors(monkeypatch):
    from tradingagents.dataflows import benzinga

    payload = [
        {
            "date": "2026-08-27", "event_type": "FDA approved",
            "drug": {"name": "COMIRNATY XFG", "generic": False,
                     "indication_symptom": ["COVID-19"]},
            "companies": [
                {"name": "Pfizer Inc", "securities": [{"symbol": "PFE", "exchange": "NYSE"}]},
                {"name": "BioNTech SE", "securities": [{"symbol": "BNTX", "exchange": "NASDAQ"}]},
            ],
            "status": "supplemental New Drug Application (sNDA)",
            "outcome_brief": "approved the supplemental Biologics License Application",
        }
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_fda_calendar_benzinga("PFE", "2026-01-01", "2026-12-31")

    assert "FDA / Clinical Milestones" in out
    assert "FDA approved" in out
    assert "COMIRNATY XFG" in out and "indication: COVID-19" in out
    assert "Pfizer Inc (PFE)" in out and "BioNTech SE (BNTX)" in out


def test_offerings_omits_absent_size_fields(monkeypatch):
    """A shelf registration carries no size; "0 shares" would be a wrong number.

    Measured live: INTC's 2026-01-23 row has ``number_shares: 0``, an empty
    ``price`` and an empty ``dollar_shares``. Rendering those as ``0 shares`` /
    ``price -`` / ``gross -`` invents a figure where the vendor gave none.
    """
    from tradingagents.dataflows import benzinga

    payload = [
        {"date": "2026-08-11", "ticker": "INTC", "name": "Intel",
         "number_shares": 210526000, "price": "95.000", "shelf": False,
         "dollar_shares": "20000000000.000", "currency": "USD", "offering_type": ""},
        {"date": "2026-01-23", "ticker": "INTC", "name": "Intel",
         "number_shares": 0, "price": "", "shelf": True,
         "dollar_shares": "", "currency": "USD", "offering_type": ""},
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_offerings_benzinga("INTC", "2026-01-01", "2026-09-20")

    assert "210,526,000 shares, price 95.00, gross 20.00B USD, no shelf" in out
    # the shelf row keeps the flag, which is its whole signal
    assert "shelf" in out
    # ...and must not invent a size. A bare substring check on "0 shares" would
    # match inside "210,526,000 shares", so the field position is asserted.
    assert "  0 shares" not in out and " 0 shares," not in out
    assert "gross -" not in out
    assert "price -" not in out


def test_analyst_actions_normalise_inconsistent_target_precision(monkeypatch):
    """The vendor mixes ``365.00`` and ``380.0000`` inside one row."""
    from tradingagents.dataflows import benzinga

    payload = [
        {"date": "2026-09-18", "time": "07:45:30", "analyst": "Evercore ISI Group",
         "analyst_name": "Amit Daryanani", "action_company": "Maintains",
         "action_pt": "Raises", "rating_current": "Outperform",
         "rating_prior": "Outperform", "pt_current": "380.0000",
         "pt_prior": "365.00", "pt_pct_change": "4.11"},
    ]
    with mock.patch.object(benzinga, "_benzinga_get", return_value=payload):
        out = benzinga.get_analyst_actions_benzinga("AAPL", "2026-09-01", "2026-09-20")

    assert "pt Raises 365.00 \u2192 380.00 (4.11%)" in out
    assert "380.0000" not in out


def test_news_removed_claims_no_date_window(monkeypatch):
    """The endpoint silently ignores every date parameter.

    Measured live 2026-09-20: an empty filter, a one-day window, a three-month
    window and ``dateFrom``/``dateTo`` all returned the identical first row.
    ``pageSize`` and ``page`` DO work. So the reader takes a limit and a page
    and must not offer a window it cannot honour.
    """
    from tradingagents.dataflows import benzinga

    captured: dict = {}

    def _get(path, params=None):
        captured["path"] = path
        captured["params"] = dict(params or {})
        return [{"id": 61839326, "updated": "Thu, 17 Sep 2026 08:14:03 -0400"}]

    with mock.patch.object(benzinga, "_benzinga_get", side_effect=_get):
        out = benzinga.get_news_removed_benzinga(limit=3, page=2)

    assert captured["params"] == {"pageSize": 3, "page": 2}
    assert "no date window" in out
    assert "61839326" in out

    with pytest.raises(ValueError):
        benzinga.get_news_removed_benzinga(limit=0)
    with pytest.raises(ValueError):
        benzinga.get_news_removed_benzinga(page=0)


@pytest.mark.parametrize(
    "call",
    [
        lambda b: b.get_guidance_benzinga("AAPL", "2026-01-01", "2026-09-20"),
        lambda b: b.get_fda_calendar_benzinga("AAPL", "2026-01-01", "2026-09-20"),
        lambda b: b.get_offerings_benzinga("AAPL", "2026-01-01", "2026-09-20"),
        lambda b: b.get_analyst_actions_benzinga("AAPL", "2026-01-01", "2026-09-20"),
    ],
)
def test_an_empty_window_raises_typed_no_data(monkeypatch, call):
    """An empty window must be a typed absence so the router can degrade.

    A bare heading returned as success would stop the chain and read as "the
    company has no such events", which is a different claim from "the vendor
    returned nothing".
    """
    from tradingagents.dataflows import benzinga

    with (
        mock.patch.object(benzinga, "_benzinga_get", return_value=[]),
        pytest.raises(NoMarketDataError),
    ):
        call(benzinga)


def test_the_two_firehose_readers_page_with_the_lowercase_spelling(monkeypatch):
    """The paging parameter is spelled differently per route family.

    Measured live 2026-09-20: the ``/v1/*`` endpoints page on lowercase
    ``pagesize`` - camelCase ``pageSize`` is ignored there and the "pages" come
    back ragged (50/150/141 rows, a different slice each time) - while
    ``/v2/news-removed`` honours camelCase ``pageSize``. Using the wrong
    spelling does not error; it silently returns a different slice. The first
    version of ``_filtered_pages`` used ``pageSize``, scanned four "pages" of
    the Form 4 stream, and found no AAPL row - AAPL is on the fourth real page.
    """
    from tradingagents.dataflows import benzinga

    seen: list[dict] = []

    def _get(path, params=None):
        seen.append(dict(params or {}))
        # A FULL page of non-matching rows, so the walk continues to page 2
        # rather than stopping at what looks like the end of the stream.
        return [{"filing": {"company_symbol": "ZZZZ"}}] * 100

    with mock.patch.object(benzinga, "_benzinga_get", side_effect=_get):
        benzinga._filtered_pages(
            "v1/sec/insider_transactions/transactions", "AAPL", 2, 100,
            benzinga._insider_symbol, 5,
        )

    assert seen, "no request was made"
    for params in seen:
        assert "pagesize" in params, params
        assert "pageSize" not in params, params
        assert params["pagesize"] == 100
    assert [p["page"] for p in seen] == [1, 2], "the reader must walk pages in order"


def test_news_removed_still_uses_the_camelcase_spelling(monkeypatch):
    """The /v2 route family is the opposite spelling - do not unify them."""
    from tradingagents.dataflows import benzinga

    captured: dict = {}

    def _get(path, params=None):
        captured.update(params or {})
        return [{"id": 1, "updated": "x"}]

    with mock.patch.object(benzinga, "_benzinga_get", side_effect=_get):
        benzinga.get_news_removed_benzinga(limit=7, page=3)

    assert captured == {"pageSize": 7, "page": 3}


# ---------------------------------------------------------------------------
# the congress fallthrough defect
# ---------------------------------------------------------------------------


def test_congress_raises_so_the_chain_can_fall_through(monkeypatch):
    """A vendor that cannot fail cannot fall back.

    ``route_to_vendor`` treats ANY returned string as a successful result and
    returns it, so ``get_congress_trades`` returning the prose "congress trades
    unavailable for X: ..." stopped the chain - every later vendor configured
    for ``get_congress_trades`` was unreachable. Measured by reading the router
    loop: ``result = impl_func(...)`` is followed directly by the cache-write
    and return.
    """
    from tradingagents.dataflows import congress

    def _boom(*_a, **_k):
        raise RuntimeError("mirror unreachable")

    monkeypatch.setattr(congress, "_cached_rows", _boom)
    with pytest.raises(NoMarketDataError) as excinfo:
        congress.get_congress_trades("AAPL")
    assert "mirror unreachable" in str(excinfo.value)

    with pytest.raises(ValueError):
        congress.get_congress_trades("")


def test_congress_still_renders_when_a_chamber_answers(monkeypatch):
    """A partial result is still data and must NOT raise."""
    from tradingagents.dataflows import congress

    # The watcher row shape the normaliser reads: ticker / type / amount /
    # transaction_date (congress._row). An open-market Purchase with an amount
    # is the only shape _filter_rows keeps.
    rows = [
        {
            "ticker": "AAPL",
            "type": "Purchase",
            "amount": "$1,001 - $15,000",
            "transaction_date": "2026-08-26",
            "representative": "Jane Example",
        }
    ]
    monkeypatch.setattr(congress, "_cached_rows", lambda *a, **k: rows)
    out = congress.get_congress_trades("AAPL")
    assert "House" in out
    assert "1 buys" in out


# ---------------------------------------------------------------------------
# routing and registration
# ---------------------------------------------------------------------------


def test_benzinga_is_second_in_the_default_news_chain():
    """Ticker-scoped and financial-first, so it precedes the keyword feeds."""
    from tradingagents.default_config import DEFAULT_CONFIG

    chain = DEFAULT_CONFIG["data_vendors"]["news_data"].split(",")
    assert chain[0] == "eodhd"
    assert chain[1] == "benzinga"


def test_insider_transactions_overrides_the_category_chain():
    """It shares the ``news_data`` CATEGORY, so it needs a tool-level override.

    Without one it inherits the news chain, which would put the Benzinga
    firehose - which pages the market-wide Form 4 stream and filters locally -
    FIRST on every insider lookup.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    override = DEFAULT_CONFIG["tool_vendors"]["get_insider_transactions"].split(",")
    assert override[-1] == "benzinga", "the firehose backup must be last"
    assert override[0] == "moomoo", "local + unlimited + richest goes first"
    assert override.index("alpha_vantage") < override.index("benzinga")


def test_benzinga_registered_as_a_backup_on_the_existing_routes():
    from tradingagents.dataflows import interface as I

    for method in (
        "get_stock_data",
        "get_earnings_calendar",
        "get_analyst_ratings",
        "get_insider_transactions",
        "get_congress_trades",
        "get_corporate_actions",
    ):
        assert "benzinga" in I.VENDOR_METHODS[method], method

    for method in (
        "get_guidance_revisions",
        "get_fda_calendar",
        "get_offerings_calendar",
        "get_analyst_actions",
        "get_news_removed",
    ):
        assert list(I.VENDOR_METHODS[method]) == ["benzinga"], method
        assert method in I.TOOLS_CATEGORIES[
            I.get_category_for_method(method)
        ]["tools"]


def test_earnings_calendar_backup_looks_forward(monkeypatch):
    """The tool's purpose is the next print, so the window must be forward."""
    from tradingagents.dataflows import benzinga

    captured: dict = {}

    def _get(path, params=None):
        captured.update(params or {})
        return [{"date": "2026-10-29", "period": "Q4", "period_year": 2026,
                 "date_confirmed": 0, "eps_est": "1.980", "eps_prior": "1.850",
                 "revenue_est": "113467617344.000", "revenue_prior": "102466000000.000"}]

    with mock.patch.object(benzinga, "_benzinga_get", side_effect=_get):
        out = benzinga.get_earnings_calendar_benzinga("AAPL", "2026-09-20", 40)

    assert captured["parameters[date_from]"] == "2026-09-20"
    assert captured["parameters[date_to]"] == "2026-10-30"
    assert "2026-10-29" in out
    assert "eps estimate 1.980 (prior 1.850)" in out
    assert "unconfirmed" in out


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("get_guidance_revisions", {"ticker": "AAPL", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
        ("get_fda_calendar", {"ticker": "PFE", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
        ("get_offerings_calendar", {"ticker": "INTC", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
        ("get_analyst_actions", {"ticker": "AAPL", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
        ("get_news_removed", {}),
    ],
)
def test_every_tool_is_disabled_while_the_gate_is_off(name, kwargs):
    """Gate off must be a DISABLED sentinel - never a fetch, never a guess."""
    from tradingagents.agents.utils import benzinga_tools

    tool = getattr(benzinga_tools, name)
    with mock.patch.object(benzinga_tools, "route_to_vendor") as router:
        out = tool.invoke(kwargs)
    router.assert_not_called()
    assert "DATA_DISABLED" in out
    # the sentinel spells the key out with spaces and names the env var
    assert "benzinga surface" in out
    assert "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE" in out


def test_the_gate_is_registered_and_defaults_off():
    from tradingagents.default_config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["enable_benzinga_surface"] is False


def test_every_tool_reaches_the_router_once_the_gate_is_on(monkeypatch):
    from tradingagents.agents.utils import benzinga_tools

    monkeypatch.setattr(
        benzinga_tools,
        "_feature_gate",
        lambda *_a, **_k: None,
    )
    with mock.patch.object(benzinga_tools, "route_to_vendor", return_value="OK") as router:
        for name, kwargs in (
            ("get_guidance_revisions", {"ticker": "AAPL", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
            ("get_fda_calendar", {"ticker": "PFE", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
            ("get_offerings_calendar", {"ticker": "INTC", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
            ("get_analyst_actions", {"ticker": "AAPL", "start_date": "2026-01-01", "end_date": "2026-09-20"}),
            ("get_news_removed", {}),
        ):
            assert getattr(benzinga_tools, name).invoke(kwargs) == "OK"
    assert router.call_count == 5
