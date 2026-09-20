"""Sentiment analyst — multi-source sentiment analysis for a target ticker.

Previously named ``social_media_analyst``. Renamed and redesigned because
the old version had a prompt that demanded social-media analysis but the
only tool available was Yahoo Finance news — which led LLMs to fabricate
Reddit/X/StockTwits content under prompt pressure (verified live).

The redesigned agent pre-fetches three complementary data sources before
the LLM is invoked and injects them into the prompt as structured blocks:

  1. News headlines     — Yahoo Finance (institutional framing)
  2. StockTwits messages — retail-trader posts indexed by cashtag, with
                           user-labeled Bullish/Bearish sentiment tags
  3. Reddit posts        — r/wallstreetbets, r/stocks, r/investing

The agent does not use tool-calling; the data is in the prompt from
turn 0. Output uses the structured-output pattern (json_schema for
OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic), falling
back to free-text generation for providers that lack native support, so
the sentiment header (band + score + confidence) is deterministic across
runs and providers instead of free-form per-model prose.

See: https://github.com/TauricResearch/TradingAgents/issues/557
See: https://github.com/TauricResearch/TradingAgents/issues/796
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_macro_indicators,
    get_news,
    get_output_budget,
)
from tradingagents.agents.utils.prompt_metrics import record_stage
from tradingagents.agents.utils.report_hygiene import (
    REPORT_HYGIENE_RULES,
    engine_score_block,
    scorecard_context_block,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.dataflows.reddit import fetch_reddit_posts
from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def _prefetch_status(content: str) -> str:
    """Status of a pre-fetched block: "no_data" when the fetcher returned an
    empty or explicit-unavailable placeholder, else "ok"."""
    c = (content or "").strip()
    if not c or "unavailable" in c.lower():
        return "no_data"
    return "ok"


def create_sentiment_analyst(llm, backup_llm=None, config=None):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a deterministic sentiment
    report via structured output (with a free-text fallback for providers
    that do not support it).

    ``backup_llm`` (optional): the cut-at-cap continuation retry runs on this
    model instead of the truncated one (TRADINGAGENTS_BACKUP_LLM).

    ``config`` (optional, unused here): the forced-tool gather is a no-op for
    this analyst — it pre-fetches a FIXED source set into the prompt (already
    deterministic in composition), so there is no tool-selection variance to
    remove. The parameter keeps the four factory signatures uniform.
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # Pre-fetch all three sources. Each fetcher degrades gracefully and
        # returns a string (no exceptions surface from here), so the LLM
        # always sees something — either real data or a clear placeholder.
        # The StockTwits / Reddit fetchers take the as-of window so a
        # historical run can't leak post-date chatter into a backtest (#1220).
        news_block = get_news.func(ticker, start_date, end_date)
        stocktwits_block = fetch_stocktwits_messages(
            ticker, limit=30, start_date=start_date, end_date=end_date
        )
        reddit_block = fetch_reddit_posts(
            ticker, start_date=start_date, end_date=end_date
        )

        # Deterministic sentiment computed BEFORE the prompt is built so the
        # model sees the value and can bind overall_score to it. Previously
        # the compute ran after message formatting and only reached the report
        # post-hoc — the model then invented a 0-10 score contradicting the
        # computed signal (MSTR 2026-09-08: "Mildly Bearish (4.0/10)" vs
        # deterministic +0.08; the report verifier caught the class).
        cfg = None
        try:
            from tradingagents.dataflows.config import get_config

            cfg = get_config()
        except Exception:
            cfg = None
        computed = None
        if cfg is not None and cfg.get("enable_sentiment"):
            try:
                from tradingagents.strategies.sentiment import (
                    compute_social_scores,
                    computed_sentiment_line,
                )

                computed = compute_social_scores(
                    ticker, cache_dir=cfg.get("data_cache_dir"), limit=30
                )
            except Exception:
                computed = None
        computed_line = (
            computed_sentiment_line(computed) if computed is not None else ""
        )

        # S11b for THIS stem (gate: enable_evidence_symmetry). The news analyst
        # synthesizes the deterministic 10-year FRED leaf inside
        # gather_for_analyst_node, but this node binds no tools and pre-fetches
        # a fixed source set, so it had only recalled macro levels from
        # headlines: the SKHY 2026-09-14 run wrote "US 10-year above 5%" with no
        # macro leaf anywhere in its evidence and the report verifier flagged
        # the line as UNSUPPORTED (the class pinned by the SKHY 2026-09-09
        # review loop). Additive and default-off; a fetch failure leaves the
        # stem exactly as it was.
        macro_block = ""
        if cfg is not None and cfg.get("enable_evidence_symmetry"):
            try:
                macro_block = get_macro_indicators.func("10y_treasury", end_date, 30)
            except Exception:  # noqa: BLE001 - additive evidence, never fatal
                macro_block = ""

        system_message = _build_system_message(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            news_block=news_block,
            stocktwits_block=stocktwits_block,
            reddit_block=reddit_block,
            computed_line=computed_line,
            macro_block=macro_block,
            # This analyst binds NO tools, so the SentimentScore engine's result
            # reaches this report only by being supplied here. A "call
            # get_sentiment_score" instruction would be a hallucinated call
            # (the prompt carries NO_EXTERNAL_TOOLS).
            # §13.1: the full scorecard rides beside the owned engine - it is
            # supplied text either way, which is the only route into a prompt
            # that binds no tools.
            engine_block=engine_score_block("sentiment", ticker, end_date, cfg)
            + scorecard_context_block(ticker, end_date, cfg, state.get("quant_scorecard")),
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    # No tool-calling here: the data is pre-fetched into the
                    # prompt, so tool-range wording would only invite a
                    # hallucinated tool call (#1130).
                    " Today's date is {current_date}; treat it as 'now' for all analysis. {instrument_context}"
                    " " + NO_EXTERNAL_TOOLS + "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

        # Journal the pre-fetched source set (news / StockTwits / Reddit) and
        # the deterministic sentiment compute into state["tool_evidence"]
        # under "sentiment", so tool_evidence.json records exactly what this
        # analyst reduced from — closing the post-hoc verification gap that
        # made the QCOM 2026-09-07 sentiment tallies ("13 Bull vs 1 Bear",
        # velocity -0.82 vs -0.78) uncheckable after the run.
        from tradingagents.agents.utils.evidence_gather import (
            TOOL_EVIDENCE_KEY,
            make_evidence_leaf,
        )

        _window = 12000
        try:
            _window = int((cfg or {}).get("analyst_forced_tools_summary_window") or _window)
        except Exception:
            _window = 12000
        sentiment_leaves = [
            make_evidence_leaf(
                "news_headlines",
                news_block,
                args={"ticker": ticker, "start_date": start_date, "end_date": end_date},
                status=_prefetch_status(news_block),
                summary_window=_window,
            ),
            make_evidence_leaf(
                "stocktwits_messages",
                stocktwits_block,
                args={
                    "ticker": ticker,
                    "limit": 30,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                status=_prefetch_status(stocktwits_block),
                summary_window=_window,
            ),
            make_evidence_leaf(
                "reddit_posts",
                reddit_block,
                args={"ticker": ticker, "start_date": start_date, "end_date": end_date},
                status=_prefetch_status(reddit_block),
                summary_window=_window,
            ),
        ]
        if computed is not None:
            sentiment_leaves.append(
                make_evidence_leaf(
                    "sentiment_computed",
                    computed_sentiment_line(computed),
                    status="ok",
                    summary_window=_window,
                )
            )
        else:
            sentiment_leaves.append(
                make_evidence_leaf(
                    "sentiment_computed",
                    "computed sentiment unavailable (enable_sentiment off or "
                    "StockTwits fetch failed)",
                    status="no_data",
                    summary_window=_window,
                )
            )
        if macro_block:
            sentiment_leaves.append(
                make_evidence_leaf(
                    "get_macro_indicators",
                    macro_block,
                    args={
                        "indicator": "10y_treasury",
                        "curr_date": end_date,
                        "look_back_days": 30,
                    },
                    status=_prefetch_status(macro_block),
                    summary_window=_window,
                )
            )
        evidence = dict(state.get(TOOL_EVIDENCE_KEY) or {})
        evidence["sentiment"] = sentiment_leaves

        def _sentiment_hook(report):
            if computed is None:
                return
            report.computed_score = computed["computed_score"]
            report.computed_velocity = computed.get("computed_velocity")
            report.sample_size = computed.get("sample_size")

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
            result_hook=_sentiment_hook if computed else None,
            backup_llm=backup_llm,
        )
        if computed and "Computed Sentiment" not in report_text:
            report_text = report_text.rstrip() + "\n\n" + computed_sentiment_line(computed)

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
            **record_stage("analyst_sentiment", formatted_messages),
            "tool_evidence": evidence,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
    computed_line: str = "",
    macro_block: str = "",
    engine_block: str = "",
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    macro_section = (
        "\n### Macro rate level — FRED via get_macro_indicators, deterministic leaf\n"
        "The only macro level you may state. Headlines in the feeds below may quote "
        "a different figure (often a round number, or yesterday's print): when they "
        "disagree with this leaf, quote the leaf, date it, and say the headline "
        "figure differs.\n\n<start_of_macro>\n"
        f"{macro_block}\n<end_of_macro>\n"
        if macro_block
        else ""
    )
    macro_pin = (
        "- **MACRO DATA PROVENANCE (10-year).** Any macro rate level you mention (10-year "
        "Treasury / DGS10, Fed funds) must be quoted from the macro leaf above "
        "with its date. Recalled levels — from headlines, posts, or memory — must "
        "not appear as figures: if the feeds talk about a level you cannot find in "
        "the leaf, describe it qualitatively.\n"
        if macro_block
        else ""
    )
    computed_block = (
        "### Deterministic computed sentiment (pre-computed by the pipeline; "
        "numbers the LLM must not contradict)\n\n"
        f"{computed_line}\n\n"
        if computed_line
        else ""
    )
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

{computed_block}

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### StockTwits messages — retail-trader social platform indexed by cashtag
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### Reddit posts — r/wallstreetbets, r/stocks, r/investing (past 7 days)
Community discussion. Engagement signal via upvote score and comment count. Subreddit character matters (r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term).

<start_of_reddit>
{reddit_block}
<end_of_reddit>
{macro_section}
## How to analyze this data (best practices)

1. **Read the StockTwits Bullish/Bearish ratio as a leading retail-sentiment signal, calibrated to sample size.** A 70/30 bullish/bearish split is moderately bullish; ≥90/10 may indicate over-extension and contrarian risk; 50/50 is uncertainty. Base rates on the actual message count, not percentages alone — a 90/10 split on 10 messages is a much weaker signal than the same split on 200, and the gap between those two cases is exactly what the `confidence` field and the data-limits note (see below) exist to capture.

2. **Look for cross-source divergences, and say which source you weighted more when they conflict.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious). Don't just note the divergence and move on: when it's large enough to push `overall_band` toward Mixed or to pull `overall_score` away from a naive average, state in the narrative which source(s) drove the final call and why (e.g. sample size, recency, event- vs. opinion-based) — never resolve a real conflict silently.

3. **Weight Reddit posts by engagement.** A 400-upvote / 200-comment thread reflects community attention; a 3-upvote post is noise. Read the body excerpts for context — the title alone often misleads.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this explicitly in the `confidence` field and the narrative. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Ground every macro figure in the leaf.**
{macro_pin}
9. **Copy counts and quotes verbatim.** Message counts, upvote/comment totals, and any figure from the computed block are quoted exactly as given, never rounded or estimated from a partial read of the blocks above.

10. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

## Output fields

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. Use Mixed when sources point in clearly different directions; Neutral only when all sources are genuinely silent. When you use Mixed, the narrative must name which sources are in conflict (per item 2 above) — Mixed is a finding to explain, not a way to avoid resolving the divergence.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral. Keep it consistent with overall_band. When the Deterministic computed sentiment block above is present, anchor it there: map computed_score in [-1, 1] to the 0-10 scale as `5 + 5 * computed_score` and keep your score within ±0.5 of that anchor — never contradict a computed value (the report verifier cross-checks the saved report against the tool evidence). When no computed block is present, derive the score directly from the source evidence and say so in `confidence`.
- **confidence**: low / medium / high, based on data quality and sample size.
- **narrative**: Full source-by-source breakdown, divergences (with the weighting stated per item 2), dominant narrative themes, catalysts and risks, and a markdown summary table of key sentiment signals (direction, source, supporting evidence).

## Grounding

You also have `get_news(ticker, start_date, end_date)` - the headline feed for the ticker; anchor your sentiment claims in specific headlines and adjustment dates rather than raw scores.

{get_language_instruction()}{get_output_budget("analyst")}{REPORT_HYGIENE_RULES}{engine_block}"""



