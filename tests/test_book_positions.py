"""Hermetic tests for book_positions (positions -> basket weights) + CLI.

Pure/offline: synthetic CSV rows, no network, no real portfolio data.
Covers cash detection, cross-account merge, weights-including-cash, the
exact .env render round-trip through default_config._coerce, the Option-B
holdings fallback, the gitignore secrecy guard, and the CLI dry-run/apply/
json paths (against temp files).
"""

import json
import pathlib

import pytest

from tradingagents.dataflows.utils import repo_root
from tradingagents.strategies import book_positions as bp

pytestmark = pytest.mark.timeout(120)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _row(symbol, value, qty=None, desc="", typ="Cash", **extra):
    r = {"Symbol": symbol, "Current value": value, "Quantity": qty,
         "Description": desc, "Percent of account": None, "Type": typ}
    r.update(extra)
    return r


@pytest.fixture
def book_csv_rows():
    """Synthetic two-account book: equities + money-market + dust."""
    a1 = [
        _row("AVGO", 2680.0, 30, typ="Cash"),        # Type says Cash -> real equity
        _row("NVDA", 10420.0, 100),
        _row("SPAXX**", 34000.0, None, desc="FDIC Sweep"),  # money market
        _row("", None, None),                         # blank trailer
    ]
    a2 = [
        _row("MSFT", 2340.0, 20),
        _row("FDRXX**", 1000.0, None, desc="Money Market"),
        _row("BRK.B", 5000.0, 5),                     # dotted share class
    ]
    return {"Account1": a1, "Account2": a2}


class TestCashDetection:
    def test_money_market_suffix_is_cash(self):
        assert bp.is_cash_row(_row("SPAXX**", 100.0, None, "FDIC Sweep"))
        assert bp.is_cash_row(_row("FDRXX**", 100.0, None, "Money Market"))

    def test_blank_symbol_with_value_is_cash(self):
        # unsettled / accrual rows: no symbol, has value
        assert bp.is_cash_row(_row("", 12.34, None))

    def test_pending_activity_is_cash(self):
        # Fidelity settlement row: Symbol = "Pending activity", no quantity,
        # empty Description - unsettled cash, never a ticker.
        assert bp.is_cash_row(_row("Pending activity", 8993.41, None))
        assert bp.is_cash_row(_row("PENDING ACTIVITY", 8993.41, None, desc=""))

    def test_equity_not_cash_despite_type_column(self):
        # Fidelity's Type column says "Cash" for equities too - must NOT use it
        assert not bp.is_cash_row(_row("AVGO", 2680.0, 30, typ="Cash"))
        assert not bp.is_cash_row(_row("NVDA", 10420.0, 100, typ="Cash"))

    def test_blank_symbol_no_value_not_cash(self):
        assert not bp.is_cash_row(_row("", None, None))


class TestParseRows:
    def test_skips_cash_and_trailer(self):
        rows = [_row("AVGO", 2680.0, 30), _row("SPAXX**", 34000.0, None), _row("", None, None)]
        poss, skipped = bp.parse_rows(rows)
        assert [p.symbol for p in poss] == ["AVGO"]
        assert skipped == []

    def test_normalizes_share_class(self):
        poss, _ = bp.parse_rows([_row("BRK.B", 5000.0, 5)])
        assert poss[0].symbol == "BRK-B"

    def test_no_value_skipped_with_reason(self):
        poss, skipped = bp.parse_rows([_row("GOOG", None, 10)])
        assert poss == []
        assert any("GOOG" in s and "no usable" in s for s in skipped)


class TestBookStatsAndWeights:
    def test_merge_cross_account(self, book_csv_rows):
        st = bp.book_stats(book_csv_rows)
        # AVGO 2680 + NVDA 10420 + MSFT 2340 + BRK.B 5000 = 20440
        assert st["positions"] == {"AVGO": 2680.0, "NVDA": 10420.0, "MSFT": 2340.0, "BRK-B": 5000.0}
        assert st["cash_value"] == 35000.0  # SPAXX 34000 + FDRXX 1000
        assert st["total_value"] == pytest.approx(20440.0 + 35000.0)

    def test_weights_include_cash_in_denominator(self):
        w = bp.compute_weights({"A": 6000.0, "B": 4000.0}, cash_value=10000.0)
        assert w == {"A": 0.3, "B": 0.2}           # / 20000 total
        assert sum(w.values()) == pytest.approx(0.5)  # 50% cash remainder

    def test_cash_never_a_ticker(self):
        w = bp.compute_weights({"SPAXX**": 0.0}, 30000.0)
        assert "SPAXX**" not in w

    def test_min_value_drop(self):
        w = bp.compute_weights({"A": 100.0, "B": 5.0}, 1000.0, min_value=10.0)
        assert "B" not in w
        assert "A" in w

    def test_zero_total_returns_empty(self):
        assert bp.compute_weights({}, 0.0) == {}


class TestEnvRender:
    def test_render_env_format(self):
        t, w = bp.render_env_basket({"AVGO": 0.0268, "BAC": 0.006})
        assert t == "AVGO,BAC"
        assert w == "AVGO=0.0268,BAC=0.0060"

    def test_round_trip_through_default_config_coerce(self):
        from tradingagents.default_config import _coerce

        w = {"AVGO": 0.0268, "BAC": 0.006, "GLD": 0.1027, "SPY": 0.1857}
        tickers_line, weights_line = bp.render_env_basket(w)
        parsed_t = _coerce(tickers_line, [])
        parsed_w = _coerce(weights_line, {})
        assert parsed_t == list(w)
        assert parsed_w == w

    def test_patch_env_replaces_only_basket_lines(self):
        env = "A=1\nTRADINGAGENTS_RISK_BASKET_TICKERS=OLD\nB=2\nTRADINGAGENTS_RISK_BASKET_WEIGHTS=OLDW\nC=3\n"
        out = bp.patch_env_text(env, "N1,N2", "N1=0.5,N2=0.5")
        assert out == "A=1\nTRADINGAGENTS_RISK_BASKET_TICKERS=N1,N2\nB=2\nTRADINGAGENTS_RISK_BASKET_WEIGHTS=N1=0.5,N2=0.5\nC=3\n"

    def test_patch_env_appends_missing(self):
        env = "A=1\n"
        out = bp.patch_env_text(env, "N1", "N1=1.0")
        assert out.startswith("A=1\n")
        assert "TRADINGAGENTS_RISK_BASKET_TICKERS=N1\n" in out
        assert "TRADINGAGENTS_RISK_BASKET_WEIGHTS=N1=1.0\n" in out


class TestHoldingsBlock:
    def test_uses_holdings_when_set(self):
        cfg = {"holdings_tickers": ["NVDA", "MSFT"], "holdings_weights": {"NVDA": 0.3, "MSFT": 0.2},
               "risk_basket_tickers": ["SPY"], "risk_basket_weights": {"SPY": 1.0}}
        line = bp.render_holdings_block(cfg)
        assert "NVDA 30.0%" in line and "MSFT 20.0%" in line

    def test_falls_back_to_basket(self):
        cfg = {"holdings_tickers": [], "holdings_weights": {},
               "risk_basket_tickers": ["AVGO", "NVDA"], "risk_basket_weights": {"AVGO": 0.3, "NVDA": 0.7}}
        line = bp.render_holdings_block(cfg)
        assert "AVGO 30.0%" in line and "NVDA 70.0%" in line

    def test_empty_when_no_book(self):
        assert bp.render_holdings_block({}) == ""

    def test_cash_remainder_shown(self):
        cfg = {"holdings_tickers": ["A"], "holdings_weights": {"A": 0.4}}
        assert "unallocated (cash) 60.0%" in bp.render_holdings_block(cfg)


class TestSecrecyGuard:
    def test_positions_dir_is_gitignored(self):
        # The sensitive CSVs + book JSON must never be commit-able.
        import subprocess

        res = subprocess.run(
            ["git", "check-ignore", "-v", "positions/Account1/Portfolio_Positions_Sep-02-2026.csv",
             "positions/book_value.json"],
            cwd=repo_root(), capture_output=True, text=True,
        )
        # exit 0 = matched ignore; both paths must be ignored
        assert res.returncode == 0 and len(res.stdout.splitlines()) == 2


class TestCli:
    def _write(self, tmp: pathlib.Path, rows: list, acct: str):
        d = tmp / acct
        d.mkdir(parents=True, exist_ok=True)
        f = d / "positions.csv"
        import csv as _csv
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = _csv.DictWriter(fh, fieldnames=["Symbol", "Current value", "Quantity", "Description", "Percent of account", "Type"])
            w.writeheader()
            for r in rows:
                w.writerow({k: (r.get(k) if r.get(k) is not None else "") for k in w.fieldnames})
        return f

    def test_cli_dry_run_json(self, tmp_path, monkeypatch):
        self._write(tmp_path, [_row("AVGO", 6000.0, 30), _row("SPAXX**", 4000.0, None)], "A1")
        self._write(tmp_path, [_row("MSFT", 2000.0, 20)], "A2")
        from scripts import positions_to_basket as mod

        monkeypatch.setattr(mod, "POSITIONS_DIR", tmp_path)
        monkeypatch.setattr(mod, "BOOK_JSON", tmp_path / "book_value.json")
        captured = []
        mod._cli(["--positions", str(tmp_path), "--json"], _print=captured.append)
        data = json.loads(captured[-1])
        assert data["total_value"] == pytest.approx(12000.0)
        assert data["cash_value"] == pytest.approx(4000.0)
        assert data["weights"]["AVGO"] == pytest.approx(0.5)
        assert data["weights"]["MSFT"] == pytest.approx(1 / 6, abs=1e-4)
        assert "SPAXX**" not in data["tickers"]

    def test_cli_apply_updates_env(self, tmp_path, monkeypatch):
        self._write(tmp_path, [_row("AVGO", 6000.0, 30), _row("SPAXX**", 4000.0, None)], "A1")
        from scripts import positions_to_basket as mod

        env = tmp_path / ".env"
        env.write_text(
            "KEEP=1\nTRADINGAGENTS_RISK_BASKET_TICKERS=OLD\n"
            "TRADINGAGENTS_RISK_BASKET_WEIGHTS=OLDW=0.5\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(mod, "POSITIONS_DIR", tmp_path)
        monkeypatch.setattr(mod, "ENV_FILE", env)
        monkeypatch.setattr(mod, "BOOK_JSON", tmp_path / "book_value.json")
        mod._cli(["--positions", str(tmp_path), "--apply"], _print=lambda _s: None)
        txt = env.read_text(encoding="utf-8")
        assert "TRADINGAGENTS_RISK_BASKET_TICKERS=AVGO" in txt
        assert "TRADINGAGENTS_RISK_BASKET_WEIGHTS=AVGO=0.6" in txt
        assert "KEEP=1" in txt and "OLDW=0.5" not in txt
        assert (tmp_path / ".env.bak").exists()

    def test_cli_write_book_json(self, tmp_path, monkeypatch):
        self._write(tmp_path, [_row("AVGO", 6000.0, 30), _row("SPAXX**", 4000.0, None)], "A1")
        from scripts import positions_to_basket as mod

        monkeypatch.setattr(mod, "POSITIONS_DIR", tmp_path)
        monkeypatch.setattr(mod, "BOOK_JSON", tmp_path / "book_value.json")
        captured = []
        mod._cli(["--positions", str(tmp_path), "--write-book-json", "--json"],
                 _print=captured.append)
        data = json.loads(captured[-1])
        assert "book_json" in data
        book = json.loads((tmp_path / "book_value.json").read_text(encoding="utf-8"))
        assert book["cash_value"] == pytest.approx(4000.0)
        assert book["positions"]["AVGO"]["value"] == pytest.approx(6000.0)
