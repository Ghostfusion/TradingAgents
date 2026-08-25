"""Tests for symbol normalization and the no-data routing sentinel."""

import unittest

import pytest

from tradingagents.dataflows.symbol_utils import (
    NoMarketDataError,
    crypto_base,
    normalize_symbol,
)


@pytest.mark.unit
class TestNormalizeSymbol(unittest.TestCase):
    def test_plain_equities_unchanged(self):
        # Multi-letter exchange suffixes, indices, Yahoo futures, plain tickers.
        for sym in ("AAPL", "MSFT", "TSM", "0700.HK", "BHP.AX", "AZN.L",
                    "^GSPC", "GC=F", "PETR4.SA", "FRC-PL"):
            self.assertEqual(normalize_symbol(sym), sym)

    def test_us_share_class_dot_becomes_hyphen(self):
        # moomoo returns dotted US share classes (PBR.A, MOG.A, MOG.B) but
        # Yahoo only resolves the hyphen form (PBR-A, MOG-A, MOG-B, BRK-B).
        self.assertEqual(normalize_symbol("PBR.A"), "PBR-A")
        self.assertEqual(normalize_symbol("MOG.A"), "MOG-A")
        self.assertEqual(normalize_symbol("MOG.B"), "MOG-B")
        self.assertEqual(normalize_symbol("BRK.B"), "BRK-B")
        self.assertEqual(normalize_symbol("BF.B"), "BF-B")
        self.assertEqual(normalize_symbol("brk.b"), "BRK-B")
        # Already-hyphenated stay put (idempotent).
        self.assertEqual(normalize_symbol("BRK-B"), "BRK-B")

    def test_lowercases_are_upper(self):
        self.assertEqual(normalize_symbol("aapl"), "AAPL")
        self.assertEqual(normalize_symbol("  msft  "), "MSFT")

    def test_metal_aliases_map_to_futures(self):
        self.assertEqual(normalize_symbol("XAUUSD"), "GC=F")
        self.assertEqual(normalize_symbol("XAUUSD+"), "GC=F")   # broker CFD suffix
        self.assertEqual(normalize_symbol("xauusd+"), "GC=F")
        self.assertEqual(normalize_symbol("GOLD"), "GC=F")
        self.assertEqual(normalize_symbol("XAGUSD"), "SI=F")

    def test_energy_and_index_aliases(self):
        self.assertEqual(normalize_symbol("USOIL"), "CL=F")
        self.assertEqual(normalize_symbol("SPX500"), "^GSPC")
        self.assertEqual(normalize_symbol("NAS100"), "^NDX")
        self.assertEqual(normalize_symbol("US30"), "^DJI")

    def test_forex_pairs_get_x_suffix(self):
        self.assertEqual(normalize_symbol("EURUSD"), "EURUSD=X")
        self.assertEqual(normalize_symbol("GBPJPY"), "GBPJPY=X")
        self.assertEqual(normalize_symbol("eurusd"), "EURUSD=X")

    def test_crypto_pairs_get_dash_usd(self):
        self.assertEqual(normalize_symbol("BTCUSD"), "BTC-USD")
        self.assertEqual(normalize_symbol("ETHUSD"), "ETH-USD")

    def test_six_letter_non_currency_left_alone(self):
        # GOOGLE-style 6-letter tickers that aren't two currency codes
        # must not be mangled into a fake forex pair.
        self.assertEqual(normalize_symbol("ABCDEF"), "ABCDEF")

    def test_london_and_exchange_suffixes_kept(self):
        # ``.L`` is the single-letter London exchange, not a share class;
        # multi-letter exchange suffixes (SA/TO/AX/HK/NS/BO) are kept too.
        self.assertEqual(normalize_symbol("AZN.L"), "AZN.L")
        self.assertEqual(normalize_symbol("BHP.AX"), "BHP.AX")
        self.assertEqual(normalize_symbol("0700.HK"), "0700.HK")
        self.assertEqual(normalize_symbol("PETR4.SA"), "PETR4.SA")

    def test_empty_input_passthrough(self):
        self.assertEqual(normalize_symbol(""), "")


@pytest.mark.unit
class TestNoMarketDataError(unittest.TestCase):
    def test_message_includes_resolution(self):
        err = NoMarketDataError("XAUUSD+", "GC=F", "no rows")
        self.assertIn("XAUUSD+", str(err))
        self.assertIn("GC=F", str(err))
        self.assertEqual(err.symbol, "XAUUSD+")
        self.assertEqual(err.canonical, "GC=F")

    def test_canonical_defaults_to_symbol(self):
        err = NoMarketDataError("FOOBAR")
        self.assertEqual(err.canonical, "FOOBAR")


@pytest.mark.unit
class TestCryptoBase(unittest.TestCase):
    def test_resolves_known_crypto_forms(self):
        for raw in ("BTC-USD", "BTCUSD", "btc-usdt", "BTC-USDC", "BTCUSD+"):
            self.assertEqual(crypto_base(raw), "BTC")
        self.assertEqual(crypto_base("ETH-USD"), "ETH")
        self.assertEqual(crypto_base("sol-usd"), "SOL")

    def test_non_crypto_returns_none(self):
        # Plain equities, class shares, and real tickers that alias elsewhere
        # (GOLD -> gold future on the Yahoo path) must NOT read as crypto.
        for raw in ("AAPL", "BRK-B", "GOLD", "XYZ-USD", "EURUSD", "", None):
            self.assertIsNone(crypto_base(raw))

    def test_agrees_with_normalize_symbol(self):
        # crypto_base is the shared primitive behind the -USD normalization.
        self.assertEqual(normalize_symbol("BTCUSD"), "BTC-USD")
        self.assertEqual(crypto_base("BTCUSD"), "BTC")


if __name__ == "__main__":
    unittest.main()


@pytest.mark.unit
class TestBlankSymbolGuard(unittest.TestCase):
    """Blank/whitespace symbols must canonicalize to '' and raise the typed
    NoMarketDataError (never leak yfinance's raw TypeError / HTTP 4xx logs)."""

    def test_whitespace_canonicalizes_to_empty(self):
        for raw in (" ", "  ", "\t", "\n", " \t\n "):
            self.assertEqual(normalize_symbol(raw), "")

    def test_none_and_empty_canonicalize_to_empty(self):
        self.assertEqual(normalize_symbol(None), "")
        self.assertEqual(normalize_symbol(""), "")

    def test_real_symbols_unaffected(self):
        self.assertEqual(normalize_symbol("eix"), "EIX")
        self.assertEqual(normalize_symbol("  msft  "), "MSFT")

    def test_require_symbol_raises_typed_error_on_blank(self):
        from tradingagents.dataflows.symbol_utils import require_symbol

        for raw in ("", " ", None):
            with self.assertRaises(NoMarketDataError) as ctx:
                require_symbol(raw)
            self.assertIn("blank", str(ctx.exception))

    def test_require_symbol_returns_canonical_on_real(self):
        from tradingagents.dataflows.symbol_utils import require_symbol

        self.assertEqual(require_symbol("eix "), "EIX")
        self.assertEqual(require_symbol("XAUUSD"), "GC=F")
