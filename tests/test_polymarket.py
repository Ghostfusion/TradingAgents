"""Polymarket prediction-market vendor: forward-looking filtering, volume
ranking, formatting, graceful degradation, and router integration.

All API access is mocked, so these run without a network connection.
"""

import unittest
from unittest import mock

import pytest
import requests

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface, polymarket
from tradingagents.dataflows.config import set_config


def _market(question, prob, *, volume, end_date, closed=False, wk=None):
    return {
        "question": question,
        "outcomes": '["Yes", "No"]',
        "outcomePrices": f'["{prob}", "{round(1 - prob, 4)}"]',
        "volumeNum": volume,
        "endDate": end_date,
        "closed": closed,
        "oneWeekPriceChange": wk,
    }


# One event with a mix: a high-volume open market, a closed one, a past-dated
# one, and a lower-volume open one. Far-future / far-past dates keep the test
# independent of the real clock.
_SEARCH = {
    "events": [
        {
            "markets": [
                _market(
                    "Open big?", 0.76, volume=5_000_000, end_date="2030-12-31T00:00:00Z", wk=-0.045
                ),
                _market(
                    "Resolved already?",
                    1.0,
                    volume=9_000_000,
                    end_date="2030-12-31T00:00:00Z",
                    closed=True,
                ),
                _market("Past event?", 0.5, volume=8_000_000, end_date="2020-01-01T00:00:00Z"),
                _market("Open small?", 0.30, volume=1_000, end_date="2030-06-30T00:00:00Z"),
            ]
        }
    ]
}


# Three cumulative "by <date>" rungs of ONE event: a ladder, not a point
# probability. Prices rise with the deadline, as a cumulative chain must.
_LADDER = {
    "events": [
        {
            "title": "Fed rate cut by...?",
            "markets": [
                _market("Fed rate cut by March 2027 meeting?", 0.18,
                        volume=500_000, end_date="2027-04-08T00:00:00Z"),
                _market("Fed rate cut by January 2027 meeting?", 0.07,
                        volume=700_000, end_date="2027-02-08T00:00:00Z"),
                _market("Fed rate cut by July 2027 meeting?", 0.62,
                        volume=300_000, end_date="2027-08-08T00:00:00Z"),
            ],
        }
    ]
}

# A single open market whose question is a "by <date>" contract.
_DEADLINE = {
    "events": [
        {
            "title": "single",
            "markets": [
                _market("Will the Fed cut by 2027-06-30?", 0.40,
                        volume=1_000, end_date="2027-06-30T00:00:00Z"),
            ],
        }
    ]
}

# A ladder whose raw quotes are non-monotone in the deadline: P(by June) sits
# below P(by January), which a cumulative chain cannot do.
_NON_MONOTONE = {
    "events": [
        {
            "title": "non-monotone",
            "markets": [
                _market("Fed cut by 2027-01-01?", 0.30, volume=10,
                        end_date="2027-01-01T00:00:00Z"),
                _market("Fed cut by 2027-06-01?", 0.20, volume=10,
                        end_date="2027-06-01T00:00:00Z"),
                _market("Fed cut by 2027-12-01?", 0.60, volume=10,
                        end_date="2027-12-01T00:00:00Z"),
            ],
        }
    ]
}


@pytest.mark.unit
class PolymarketFilterTests(unittest.TestCase):
    def test_closed_and_past_markets_are_excluded(self):
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=10)
        self.assertIn("Open big?", out)
        self.assertIn("Open small?", out)
        self.assertNotIn("Resolved already?", out)  # closed
        self.assertNotIn("Past event?", out)  # endDate in the past

    def test_ranked_by_volume(self):
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=10)
        self.assertLess(out.index("Open big?"), out.index("Open small?"))

    def test_limit_caps_results(self):
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=1)
        self.assertIn("Open big?", out)
        self.assertNotIn("Open small?", out)


@pytest.mark.unit
class PolymarketFormatTests(unittest.TestCase):
    def test_probability_volume_and_weekly_change_render(self):
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=10)
        self.assertIn("Yes 76%", out)
        self.assertIn("$5,000,000 volume", out)
        self.assertIn("resolves 2030-12-31", out)
        self.assertIn("1-week -4.5pp", out)  # -0.045 -> -4.5pp

    def test_weekly_change_omitted_when_absent(self):
        # "Open small?" has wk=None -> no 1-week clause on its line.
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=10)
        small_line = next(ln for ln in out.splitlines() if "Open small?" in ln)
        self.assertNotIn("1-week", small_line)

    def test_no_matches_reports_clearly(self):
        with mock.patch.object(polymarket, "_request", return_value={"events": []}):
            out = polymarket.get_prediction_markets("obscure ticker", limit=6)
        self.assertIn("No open prediction markets", out)


@pytest.mark.unit
class PolymarketLadderTests(unittest.TestCase):
    """C2: a cumulative "by <date>" ladder is a distribution, not one number."""

    def test_ladder_reports_cumulative_rungs_and_median_deadline(self):
        with mock.patch.object(polymarket, "_request", return_value=_LADDER):
            out = polymarket.get_prediction_markets("Fed rate cut", limit=6)
        self.assertIn("deadline ladder", out)
        # rungs render in DATE order, each with its cumulative probability
        self.assertIn("by 2027-02-08: 7% (cumulative 7%)", out)
        self.assertIn("by 2027-04-08: 18% (cumulative 18%)", out)
        self.assertIn("by 2027-08-08: 62% (cumulative 62%)", out)
        self.assertIn("implied median deadline: 2027-08-08 (cumulative 62%)", out)
        # no rung is presented as a bare "the probability of the topic"
        self.assertNotIn("Yes ", out)

    def test_single_deadline_contract_is_labelled(self):
        with mock.patch.object(polymarket, "_request", return_value=_DEADLINE):
            out = polymarket.get_prediction_markets("Fed", limit=6)
        self.assertIn("deadline contract", out)
        self.assertIn("P(the event occurs BY 2027-06-30)", out)
        self.assertIn("Yes 40%", out)

    def test_non_monotone_ladder_uses_the_monotone_envelope(self):
        with mock.patch.object(polymarket, "_request", return_value=_NON_MONOTONE):
            out = polymarket.get_prediction_markets("Fed", limit=6)
        self.assertIn("monotone envelope", out)
        self.assertIn("implied median deadline: 2027-12-01 (cumulative 60%)", out)

    def test_multi_market_event_marks_each_rung(self):
        with mock.patch.object(polymarket, "_request", return_value=_SEARCH):
            out = polymarket.get_prediction_markets("anything", limit=10)
        self.assertIn("one of 2 open markets in this event", out)


@pytest.mark.unit
class PolymarketResilienceTests(unittest.TestCase):
    def test_network_error_degrades_gracefully(self):
        # An external-service hiccup must not raise into the analyst.
        with mock.patch.object(
            polymarket, "_request", side_effect=requests.RequestException("boom")
        ):
            out = polymarket.get_prediction_markets("Fed rate cut")
        self.assertIn("unavailable", out.lower())
        self.assertIn("Fed rate cut", out)


@pytest.mark.unit
class PolymarketRoutingTests(unittest.TestCase):
    def setUp(self):
        config_module.reset_config()

    def tearDown(self):
        config_module.reset_config()

    def test_category_routes_to_polymarket(self):
        self.assertEqual(
            interface.get_category_for_method("get_prediction_markets"),
            "prediction_markets",
        )
        set_config({"data_vendors": {"prediction_markets": "polymarket"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_prediction_markets": {"polymarket": lambda *a, **k: "POLY_OK"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_prediction_markets", "fed", 5)
        self.assertEqual(out, "POLY_OK")


if __name__ == "__main__":
    unittest.main()
