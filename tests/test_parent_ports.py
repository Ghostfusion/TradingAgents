"""Hermetic tests for the parent-repo ports (#1 look-ahead window, #2 debate opening).

#1 - ``dataflows/date_window.py`` centralizes the half-open UTC content window
    (news / StockTwits / Reddit); StockTwits + Reddit now trim to the as-of
    window so a historical/backtest run cannot leak post-date chatter.
#2 - ``opponent_argument_or_opening`` gives every debate's opening speaker an
    explicit "opponent has not spoken" marker instead of interpolating an empty
    opponent response that makes the model fabricate the other side (#1176).

All offline / deterministic (network mocked), timed.
"""

from __future__ import annotations

import json
import unittest.mock as mock
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# #1 - date_window module
# ---------------------------------------------------------------------------


def test_in_window_exclusive_upper_bound():
    from tradingagents.dataflows.date_window import in_window

    start = datetime(2026, 8, 1)
    end = datetime(2026, 8, 3)
    assert in_window(datetime(2026, 8, 2, tzinfo=timezone.utc), start, end)
    # exactly at midnight after end must NOT leak
    assert not in_window(datetime(2026, 8, 4, tzinfo=timezone.utc), start, end)
    assert not in_window(datetime(2026, 7, 31, tzinfo=timezone.utc), start, end)


def test_in_window_undated_only_live():
    from tradingagents.dataflows.date_window import in_window

    now = datetime.now(timezone.utc)
    # a window reaching the present keeps undated items (live run)
    assert in_window(None, now - timedelta(days=7), now)
    # a historical window does not (backtest can't prove it isn't future)
    assert not in_window(None, datetime(2026, 1, 1), datetime(2026, 1, 8))


# ---------------------------------------------------------------------------
# #1 - StockTwits windowing
# ---------------------------------------------------------------------------


def _st_messages():
    return [
        {"body": "old", "created_at": "2026-08-01T10:00:00Z", "entities": {"sentiment": {"basic": "Bullish"}}, "user": {"username": "a"}},
        {"body": "in", "created_at": "2026-08-02T10:00:00Z", "entities": {"sentiment": {"basic": "Bullish"}}, "user": {"username": "b"}},
        {"body": "future", "created_at": "2099-01-01T10:00:00Z", "entities": {"sentiment": {"basic": "Bearish"}}, "user": {"username": "c"}},
        {"body": "undated"},
    ]


@mock.patch("tradingagents.dataflows.stocktwits.urlopen")
def test_stocktwits_trimmed_to_window(mock_urlopen):
    from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages

    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
        {"messages": _st_messages()}
    ).encode()
    out = fetch_stocktwits_messages(
        "AAPL", limit=4, start_date="2026-08-01", end_date="2026-08-02"
    )
    assert "old" in out and "in" in out
    assert "future" not in out  # post-date leak removed
    assert "undated" not in out  # unparseable dropped in a historical window


@mock.patch("tradingagents.dataflows.stocktwits.urlopen")
def test_stocktwits_no_window_keeps_all(mock_urlopen):
    from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages

    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
        {"messages": _st_messages()}
    ).encode()
    out = fetch_stocktwits_messages("AAPL", limit=4)
    assert "future" in out and "undated" in out  # live run: nothing trimmed


@mock.patch("tradingagents.dataflows.stocktwits.urlopen")
def test_stocktwits_all_filtered_returns_placeholder(mock_urlopen):
    from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages

    mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
        {"messages": _st_messages()}
    ).encode()
    out = fetch_stocktwits_messages(
        "AAPL", limit=4, start_date="2020-01-01", end_date="2020-01-02"
    )
    assert "no StockTwits messages" in out and "2020-01-01..2020-01-02" in out


# ---------------------------------------------------------------------------
# #1 - Reddit windowing
# ---------------------------------------------------------------------------


def _reddit_posts():
    now = datetime.now(timezone.utc)
    return [
        {"title": "old", "created_utc": datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()},
        {"title": "in", "created_utc": datetime(2026, 8, 2, tzinfo=timezone.utc).timestamp()},
        {"title": "future", "created_utc": (now + timedelta(days=30)).timestamp()},
        {"title": "undated", "created_utc": None},
    ]


@mock.patch("tradingagents.dataflows.reddit._fetch_subreddit")
@mock.patch("tradingagents.dataflows.reddit._pace_reddit_request")
def test_reddit_trimmed_to_window(mock_pace, mock_fetch):
    from tradingagents.dataflows.reddit import fetch_reddit_posts

    mock_fetch.return_value = _reddit_posts()
    out = fetch_reddit_posts(
        "AAPL",
        subreddits=("stocks",),
        limit_per_sub=4,
        inter_request_delay=0,
        start_date="2026-08-01",
        end_date="2026-08-02",
    )
    assert "old" in out and "in" in out
    assert "future" not in out  # post-date leak removed
    assert "undated" not in out  # no-epoch dropped in a historical window


@mock.patch("tradingagents.dataflows.reddit._fetch_subreddit")
@mock.patch("tradingagents.dataflows.reddit._pace_reddit_request")
def test_reddit_no_window_keeps_all(mock_pace, mock_fetch):
    from tradingagents.dataflows.reddit import fetch_reddit_posts

    mock_fetch.return_value = _reddit_posts()
    out = fetch_reddit_posts(
        "AAPL", subreddits=("stocks",), limit_per_sub=4, inter_request_delay=0
    )
    assert "future" in out and "undated" in out  # live run: nothing trimmed


# ---------------------------------------------------------------------------
# #2 - debate opening marker
# ---------------------------------------------------------------------------


def _capturing_llm(captured: dict):
    llm = mock.MagicMock()
    llm.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", str(prompt)) or mock.MagicMock(content="argument")
    )
    return llm


def _state(reports: dict | None = None, **extra):
    s = {
        "company_of_interest": "AAPL",
        "asset_type": "stock",
        "market_report": "m",
        "sentiment_report": "s",
        "news_report": "n",
        "fundamentals_report": "f",
        "messages": [],
    }
    s.update(reports or {})
    s.update(extra)
    return s


def test_bull_opening_marker_when_bear_absent():
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    captured: dict = {}
    node = create_bull_researcher(_capturing_llm(captured))
    state = {
        **_state(
            {
                "investment_debate_state": {
                    "history": "", "bull_history": "", "bear_history": "",
                    "current_response": "", "count": 0,
                }
            }
        ),
        "trade_date": "2026-08-02",
    }
    node(state)
    assert "has not spoken yet" in captured["prompt"]
    assert "open the debate with your own case" in captured["prompt"]


def test_bear_opening_marker_when_bull_absent():
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    captured: dict = {}
    node = create_bear_researcher(_capturing_llm(captured))
    state = {
        **_state(
            {
                "investment_debate_state": {
                    "history": "", "bull_history": "", "bear_history": "",
                    "current_response": "", "count": 0,
                }
            }
        ),
        "trade_date": "2026-08-02",
    }
    node(state)
    assert "has not spoken yet" in captured["prompt"]


def test_debater_pass_through_real_opponent_argument():
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    captured: dict = {}
    node = create_bull_researcher(_capturing_llm(captured))
    state = {
        **_state(
            {
                "investment_debate_state": {
                    "history": "prev\n", "bull_history": "b\n", "bear_history": "br\n",
                    "current_response": "Bear Analyst: the risks are real",
                    "count": 1,
                }
            }
        ),
        "trade_date": "2026-08-02",
    }
    node(state)
    assert "has not spoken yet" not in captured["prompt"]
    assert "the risks are real" in captured["prompt"]


def test_risk_aggressive_opening_markers():
    from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
    from tradingagents.agents.utils import risk_tool_loop as _rtl

    captured: dict = {}

    def _tool_loop(llm, prompt, tools, max_rounds=2):
        captured["prompt"] = str(prompt)
        return "argument", []

    node = create_aggressive_debator(_capturing_llm(captured))
    state = _state(
        {
            "risk_debate_state": {
                "history": "", "aggressive_history": "", "conservative_history": "",
                "neutral_history": "", "latest_speaker": "",
                "current_aggressive_response": "",
                "current_conservative_response": "",
                "current_neutral_response": "", "count": 0,
            },
            "trader_investment_plan": "plan",
        },
        trade_date="2026-08-02",
    )
    with mock.patch.object(_rtl, "run_tool_loop", side_effect=_tool_loop):
        node(state)
    assert "has not spoken yet" in captured["prompt"]
    assert "open the debate with your own case" in captured["prompt"]


def test_opponent_argument_or_opening_helper():
    from tradingagents.agents.utils.agent_utils import opponent_argument_or_opening

    assert "has not spoken yet" in opponent_argument_or_opening("", "bear analyst")
    assert "has not spoken yet" in opponent_argument_or_opening(None, "neutral analyst")
    assert opponent_argument_or_opening("  Bear Analyst: x  ", "bull") == "Bear Analyst: x"
    assert opponent_argument_or_opening("x", "y") == "x"

