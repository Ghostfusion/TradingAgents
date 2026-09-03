"""Share-count cross-check in get_dcf_valuation's _dcf_shares (fix #1).

Regression for the SNDK phantom-margin-of-safety: a reported diluted share
count (1.61B) wildly inconsistent with the market-cap/close basis (~147M)
must NOT win — the price-consistent derived count is used instead so the
per-share DCF and margin-of-safety stay on one basis.
"""

import pytest

from tradingagents.agents.utils import analysis_tools as at

pytestmark = pytest.mark.timeout(30)


class TestDcfSharesCrossCheck:
    def test_reported_within_band_wins(self, monkeypatch):
        # market_cap 200B, close 100 -> derived 2B; reported 2.0B (ratio 1.0)
        monkeypatch.setattr(at, "_dcf_last_close", lambda t: 100.0)
        shares, basis = at._dcf_shares({"shares_outstanding": 2.0e9}, {}, 2.0e11, "X")
        assert shares == pytest.approx(2.0e9) and basis == "reported"

    def test_reported_off_base_derived_wins(self, monkeypatch):
        # SNDK case: reported 1.61e9 vs derived (222.9e9 / 1455 ≈ 1.53e8) -> 10x off
        monkeypatch.setattr(at, "_dcf_last_close", lambda t: 1455.02)
        shares, basis = at._dcf_shares({"shares_outstanding": 1.61e9}, {},
                                       2.229e11, "X")
        assert basis == "derived"
        assert shares == pytest.approx(2.229e11 / 1455.02, rel=0.01)

    def test_only_reported(self):
        shares, basis = at._dcf_shares({"diluted_shares": 1e8}, {}, None, "X")
        assert shares == pytest.approx(1e8) and basis == "reported"

    def test_only_derived_via_close(self, monkeypatch):
        monkeypatch.setattr(at, "_dcf_last_close", lambda t: 100.0)
        shares, basis = at._dcf_shares({}, {}, 1.0e11, "X")
        assert shares == pytest.approx(1.0e9) and basis == "derived"

    def test_no_inputs_none(self):
        shares, basis = at._dcf_shares({}, {}, None, "X")
        assert shares is None and basis is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
