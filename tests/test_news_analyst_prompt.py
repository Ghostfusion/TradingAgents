"""Guard the news analyst prompt against tool-signature drift (#1116).

The prompt used to advertise ``get_news(query, ...)`` while the tool takes a
``ticker``, tricking the LLM into hallucinating free-text query calls.
"""
import pytest

import tradingagents.agents.analysts.news_analyst as na
from tests.prompt_text import prompt_strings
from tradingagents.agents.utils.news_data_tools import get_news


@pytest.mark.unit
def test_get_news_takes_ticker_not_query():
    arg_names = set(get_news.args.keys())
    assert "ticker" in arg_names
    assert "query" not in arg_names


@pytest.mark.unit
def test_news_prompt_matches_get_news_signature():
    text = prompt_strings(na.__file__)
    assert "get_news(ticker, start_date, end_date)" in text
    assert "get_news(query" not in text


@pytest.mark.unit
def test_news_prompt_macro_must_source_tools():
    """Macro figures (Treasury yields / RRP / EFFR, market-implied odds, TGA)
    must be sourced from the corresponding tools, never recalled from memory -
    the AMZN 2026-09-09 review loop uncited a 10Y 9.78% (actual ~4.78), RRP
    0.626B and Polymarket 93% with zero tool leaves. The prompt must pin every
    macro class to its tool."""
    text = prompt_strings(na.__file__)
    assert "MACRO MUSTS" in text
    assert "MUST come from get_macro_indicators" in text
    assert "MUST come from get_prediction_markets" in text
    assert "MUST come from get_tga_balance" in text
    assert "Never paste a recalled" in text
