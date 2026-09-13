"""Basis labelling + ROA reconciliation contract for Finnhub basic financials.

D3: ``get_basic_financials_finnhub`` emitted every Finnhub metric verbatim, so
the vendor's TTM ``roaTTM`` (81.41%) sat next to a computed ROA (58.06%) with
nothing distinguishing a vendor TTM value from a period-agnostic one. Each
emitted line now carries its own basis and source, and the payload's own TTM
net margin x asset turnover inputs are cross-checked against ``roaTTM``.

Hermetic: the Finnhub client seam is stubbed with canned metric payloads - no
network, no SDK.
"""

from __future__ import annotations

from tradingagents.dataflows import finnhub


class _MetricClient:
    """Minimal ``finnhub.Client`` stand-in for ``company_basic_financials``."""

    def __init__(self, metric):
        self._metric = metric

    def company_basic_financials(self, symbol, metric_type):
        return {"symbol": symbol, "sector": "Technology", "metric": self._metric}


def _emit(monkeypatch, metric, symbol="NVDA"):
    monkeypatch.setattr(finnhub, "_client", lambda: _MetricClient(metric))
    return finnhub.get_basic_financials_finnhub(symbol)


# ---------------------------------------------------------------------------
# Every metric line carries its own basis + source
# ---------------------------------------------------------------------------


def test_every_metric_line_carries_its_basis_and_source(monkeypatch):
    out = _emit(
        monkeypatch,
        {
            "roaTTM": 81.41,
            "netProfitMarginAnnual": 55.6,
            "currentRatioQuarterly": 4.5889,
        },
    )
    assert "roaTTM (TTM, Finnhub): 81.41" in out
    assert "netProfitMarginAnnual (annual, Finnhub): 55.6" in out
    assert "currentRatioQuarterly (quarterly, Finnhub): 4.5889" in out


def test_unknown_metric_key_is_emitted_and_labelled_unknown(monkeypatch):
    out = _emit(monkeypatch, {"newFangledRatio": 7.0, "beta": 2.2224941})
    # never dropped, never guessed at
    assert "newFangledRatio (vendor, basis unknown): 7.0" in out
    assert "beta (vendor, basis unknown): 2.2224941" in out


def test_basis_labels_do_not_break_canonical_parsing(monkeypatch):
    # The screener reads this text back; the added label must stay additive.
    from tradingagents.dataflows.statement_parsing import _canonicalize

    out = _emit(
        monkeypatch,
        {
            "epsGrowthQuarterlyYoy": 128.21,
            "revenueGrowthTTMYoy": 83.38,
            "roeTTM": 110.11,
            "marketCapitalization": 5299590.0,
        },
    )
    canon = _canonicalize(out)
    assert canon["eps_yoy"] == 128.21
    assert canon["revenue_yoy"] == 83.38
    assert canon["roe"] == 110.11
    assert canon["market_cap"] == 5299590000000.0


# ---------------------------------------------------------------------------
# ROA reconciliation note (payload's own margin x turnover)
# ---------------------------------------------------------------------------


def test_roa_note_fires_when_payload_inputs_contradict_roa(monkeypatch):
    out = _emit(
        monkeypatch,
        {"roaTTM": 81.41, "netProfitMarginTTM": 63.66, "assetTurnoverTTM": 0.5},
    )
    assert "# NOTE:" in out
    assert "'ROA TTM' (81.41)" in out
    assert "implies 31.83" in out  # 63.66 * 0.5


def test_roa_note_silent_without_turnover_input(monkeypatch):
    out = _emit(monkeypatch, {"roaTTM": 81.41, "netProfitMarginTTM": 63.66})
    assert "# NOTE:" not in out


def test_roa_note_silent_when_payload_inputs_agree(monkeypatch):
    out = _emit(
        monkeypatch,
        {"roaTTM": 81.41, "netProfitMarginTTM": 63.66, "assetTurnoverTTM": 1.2788},
    )
    assert "# NOTE:" not in out


def test_roa_note_falls_back_to_revenue_over_assets(monkeypatch):
    out = _emit(
        monkeypatch,
        {
            "roaTTM": 81.41,
            "netProfitMarginTTM": 63.66,
            "revenueTTM": 100.0,
            "totalAssets": 200.0,
        },
    )
    assert "# NOTE:" in out
    assert "implies 31.83" in out  # 63.66 * (100 / 200)
