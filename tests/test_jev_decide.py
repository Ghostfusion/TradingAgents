"""Hermetic tests for the TypeSafe decisions utility (``scripts/jev_decide.py``).

The utility exists because ``typesafe/jev-1.13`` is not a chat model: it is
rejected from ``/chat/completions`` and served only by ``/api/alpha/decisions``
with a ``{model, state, questions}`` body. These tests pin the four things that
made that hard to discover, with no vendor and no key:

* the key resolves the way the engine resolves it - a quoted ``.env`` value
  must come back unquoted, because the raw bytes carry the quotes into the
  token and every call then 401s with a message that blames the header;
* the question battery satisfies the endpoint's own discriminator contract, so
  a shipped default cannot be a 400;
* the body has no ``messages`` key - the chat shape is the thing that fails;
* a non-200 is reported with the vendor's own message and a non-zero exit,
  never swallowed into an empty result.
"""

from __future__ import annotations

import json

import pytest

import scripts.jev_decide as jev

# ---------------------------------------------------------------------------
# key resolution - the 401 that blamed the header
# ---------------------------------------------------------------------------


def test_resolve_key_strips_the_quotes_the_raw_bytes_keep(tmp_path):
    env = tmp_path / ".env"
    env.write_text('OPENROUTER_API_KEY="sk-or-v1-abc123"\n', encoding="utf-8")

    key = jev.resolve_key(env)

    assert key == "sk-or-v1-abc123"
    # The failure mode: the quote characters ride along inside the token.
    assert '"' not in key


def test_resolve_key_is_empty_when_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SOME_OTHER_KEY=x\n", encoding="utf-8")

    assert jev.resolve_key(env) == ""


# ---------------------------------------------------------------------------
# the question contract
# ---------------------------------------------------------------------------


def test_default_battery_satisfies_the_endpoint_discriminator():
    """A shipped default that 400s is a broken default."""
    jev.validate_questions(jev.DEFAULT_QUESTIONS)
    assert jev.DEFAULT_QUESTIONS["stance"]["type"] == "choice"
    assert isinstance(jev.DEFAULT_QUESTIONS["stance"]["criteria"], dict)
    assert isinstance(jev.DEFAULT_QUESTIONS["evidence"]["criteria"], list)


@pytest.mark.parametrize(
    "questions, needle",
    [
        ({}, "at least one"),
        ({"q": {"instructions": "x"}}, "not one of"),
        ({"q": {"type": "bool", "instructions": "x"}}, "not one of"),
        ({"q": {"type": "choice"}}, "instructions is required"),
        # choice needs a RECORD; score needs an ARRAY. Swapping them is the
        # mistake the endpoint's error names but does not explain.
        ({"q": {"type": "choice", "instructions": "x", "criteria": ["a", "b"]}}, "record"),
        ({"q": {"type": "score", "instructions": "x", "criteria": {"a": None}}}, "array"),
        ({"q": {"type": "noul", "instructions": "x", "criteria": {}}}, None),
    ],
)
def test_validate_questions_rejects_only_what_the_endpoint_rejects(questions, needle):
    if needle is None:
        jev.validate_questions(questions)  # noul takes no criteria - accepted
        return
    with pytest.raises(ValueError, match=needle):
        jev.validate_questions(questions)


def test_payload_is_not_a_chat_request():
    payload = jev.build_payload("m", "the document", jev.DEFAULT_QUESTIONS)

    assert set(payload) == {"model", "state", "questions"}
    assert "messages" not in payload, "the chat shape is what the endpoint rejects"
    assert payload["state"] == "the document"


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def test_answer_lines_render_each_variant_including_the_spread():
    choice = jev.answer_lines("stance", {
        "type": "choice", "choice": "neutral", "confidence": 0.99,
        "probabilities": {"neutral": 0.99, "bullish": 0.01, "bearish": 0.0},
    })
    assert any("choice = neutral" in ln and "confidence=0.99" in ln for ln in choice)
    # Ordered by probability, so the runner-up is visible without reading all.
    assert "neutral=0.99  bullish=0.01" in choice[1]

    score = jev.answer_lines("evidence", {
        "type": "score", "score": 3.24, "confidence": 0.69,
        "legend": {"0": "none", "1": "weak", "2": "moderate", "3": "strong"},
        "probabilities": {"3": 0.63, "2": 0.06, "0": 0.0},
    })
    assert any("score  = 3.24" in ln for ln in score)
    # Sorted by LEVEL, and labelled from the legend, not by the raw key.
    assert "none=0  moderate=0.06  strong=0.63" in score[1]

    # noul is a float, not prose - rendering it as text would be a lie.
    noul = jev.answer_lines("notes", {"type": "noul", "noul": 0.67})
    assert noul == ["  notes  noul   = 0.67"]


def test_result_lines_mark_a_missing_answer_rather_than_omitting_it():
    lines = jev.result_lines(
        {"answers": {"stance": {"type": "noul", "noul": 1.0}}, "usage": {}},
        {"stance": {}, "evidence": {}},
    )
    assert any("stance" in ln and "1.0" in ln for ln in lines)
    assert any("<missing>" in ln and "evidence" in ln for ln in lines)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def test_report_states_skips_absent_stems_and_keeps_the_requested_order(tmp_path):
    analysts = tmp_path / "1_analysts"
    analysts.mkdir()
    (analysts / "market.md").write_text("M", encoding="utf-8")
    (analysts / "news.md").write_text("N", encoding="utf-8")

    states = jev.report_states(tmp_path, ("news", "sentiment", "market"))

    assert [name for name, _ in states] == ["news", "market"], "order and skipping both matter"
    assert [text for _, text in states] == ["N", "M"]


def test_newest_tree_picks_the_last_timestamped_tree(tmp_path):
    for name in ("AAA_20260101_000000", "AAA_20260102_000000"):
        (tmp_path / name / "1_analysts").mkdir(parents=True)
    (tmp_path / "not_a_tree").mkdir()  # no 1_analysts/ - must be ignored

    assert jev.newest_tree(tmp_path).name == "AAA_20260102_000000"


def test_newest_tree_raises_when_there_is_none(tmp_path):
    with pytest.raises(FileNotFoundError):
        jev.newest_tree(tmp_path)


# ---------------------------------------------------------------------------
# the CLI against an injected transport
# ---------------------------------------------------------------------------


class _Recorder:
    """A transport that records what it was asked to send."""

    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        self.calls: list[tuple[str, dict, dict]] = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload))
        return self.status, self.body


def _fake_poster(status, body):
    return _Recorder(status, body)


OK_BODY = json.dumps({
    "model": "typesafe/jev-1.13-20260917",
    "provider": "TypeSafe",
    "answers": {
        "stance": {"type": "choice", "choice": "bullish", "confidence": 1.0,
                   "probabilities": {"bullish": 1.0, "neutral": 0.0, "bearish": 0.0}},
    },
    "usage": {"input_tokens": 10, "output_tokens": 5, "cost": 0.0002},
})


def _run_main(monkeypatch, tmp_path, poster, argv):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=sk-or-v1-test\n", encoding="utf-8")
    monkeypatch.setattr(jev, "post_json", poster)
    return jev.main(["--env-file", str(env), *argv])


def test_main_prints_the_answer_and_exits_zero(monkeypatch, tmp_path, capsys):
    state = tmp_path / "market.md"
    state.write_text("MSFT closed up 1.2%.", encoding="utf-8")
    poster = _fake_poster(200, OK_BODY)

    code = _run_main(monkeypatch, tmp_path, poster, ["--state-file", str(state)])

    out = capsys.readouterr().out
    assert code == 0
    assert "JEV-DECIDE-COMPLETE" in out
    assert "choice = bullish" in out
    assert "total cost: $0.000200" in out
    # The transport saw the decisions shape and the bearer token.
    url, headers, payload = poster.calls[0]
    assert url == jev.DEFAULT_ENDPOINT
    assert headers["Authorization"] == "Bearer sk-or-v1-test"
    assert payload["state"] == "MSFT closed up 1.2%."


def test_main_reports_the_vendor_message_and_exits_one(monkeypatch, tmp_path, capsys):
    """A 400 must surface the endpoint's own sentence, not a generic failure."""
    state = tmp_path / "market.md"
    state.write_text("x", encoding="utf-8")
    vendor = json.dumps({"error": {"message": "… use /api/alpha/decisions instead.",
                                   "code": 400}})

    code = _run_main(monkeypatch, tmp_path, _fake_poster(400, vendor),
                     ["--state-file", str(state)])

    out = capsys.readouterr().out
    assert code == 1
    assert "HTTP 400" in out
    assert "/api/alpha/decisions instead." in out
    assert "JEV-DECIDE-FAILED" in out


def test_main_fails_when_the_key_is_absent(monkeypatch, tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("NOT_THE_KEY=x\n", encoding="utf-8")
    state = tmp_path / "market.md"
    state.write_text("x", encoding="utf-8")
    monkeypatch.setattr(jev, "post_json", _fake_poster(200, OK_BODY))

    code = jev.main(["--env-file", str(env), "--state-file", str(state)])

    assert code == 1
    assert "OPENROUTER_API_KEY not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# a tree is STAGED - a stem list that can only reach 1_analysts/ cannot judge
# a research, trading, risk or portfolio report
# ---------------------------------------------------------------------------


def _staged_tree(tmp_path):
    """A miniature tree with one report in each stage plus the root roll-up."""
    files = {
        "1_analysts/market.md": "M",
        "2_research/bull.md": "BULL",
        "3_trading/trader.md": "T",
        "4_risk/aggressive.md": "A",
        "5_portfolio/decision.md": "D",
        "complete_report.md": "ALL",
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_report_states_resolves_a_stage_qualified_spec(tmp_path):
    """The gap this closes: `2_research/bull` is not under 1_analysts/."""
    tree = _staged_tree(tmp_path)

    states = jev.report_states(tree, ("2_research/bull", "5_portfolio/decision"))

    assert [name for name, _ in states] == ["2_research/bull", "5_portfolio/decision"]
    assert [text for _, text in states] == ["BULL", "D"]


def test_report_states_falls_back_to_a_tree_root_report(tmp_path):
    """`complete_report.md` is not an analyst report either."""
    tree = _staged_tree(tmp_path)

    states = jev.report_states(tree, ("complete_report",))

    assert [name for name, _ in states] == ["complete_report"]
    assert [text for _, text in states] == ["ALL"]


def test_a_bare_stem_prefers_the_analyst_report_over_the_tree_root(tmp_path):
    """A bare name means the analyst report; that is what it has always meant."""
    tree = _staged_tree(tmp_path)
    (tree / "market.md").write_text("ROOT", encoding="utf-8")

    states = jev.report_states(tree, ("market",))

    assert [text for _, text in states] == ["M"], "the analyst report wins"


def test_report_states_never_escapes_the_tree_it_was_given(tmp_path):
    """`--stems` names a report IN the tree; `--state-file` is the any-file flag."""
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET", encoding="utf-8")
    tree = tmp_path / "tree"
    tree.mkdir()

    assert jev.report_states(tree, ("../outside",)) == []


def test_all_report_states_returns_every_report_in_pipeline_order(tmp_path):
    tree = _staged_tree(tmp_path)

    states = jev.all_report_states(tree)

    assert [name for name, _ in states] == [
        "1_analysts/market",
        "2_research/bull",
        "3_trading/trader",
        "4_risk/aggressive",
        "5_portfolio/decision",
        "complete_report",   # the roll-up last, not sorted among the stages
    ]


def test_all_report_states_on_a_tree_with_no_reports_is_empty(tmp_path):
    (tmp_path / "1_analysts").mkdir()

    assert jev.all_report_states(tmp_path) == []


def test_main_all_sends_one_call_per_report(monkeypatch, tmp_path, capsys):
    """`--all` must reach the staged reports the clone of this tree omitted."""
    tree = _staged_tree(tmp_path)
    poster = _fake_poster(200, OK_BODY)

    code = _run_main(monkeypatch, tmp_path, poster, ["--tree", str(tree), "--all"])

    out = capsys.readouterr().out
    assert code == 0
    assert "JEV-DECIDE-COMPLETE" in out
    assert len(poster.calls) == 6, "one call per report, not one call for the tree"
    sent = [p[2]["state"] for p in poster.calls]
    assert sent == ["M", "BULL", "T", "A", "D", "ALL"]
    assert "2_research/bull" in out, "the read-out names the file a reader would open"


def test_main_reports_when_no_spec_matches(monkeypatch, tmp_path, capsys):
    tree = _staged_tree(tmp_path)
    poster = _fake_poster(200, OK_BODY)

    code = _run_main(monkeypatch, tmp_path, poster,
                     ["--tree", str(tree), "--stems", "nope,also_nope"])

    assert code == 1
    assert "no matching reports" in capsys.readouterr().err
    assert poster.calls == []


# ---------------------------------------------------------------------------
# --verdict: analyst reports only, de-biased, judged buy/hold/sell
# ---------------------------------------------------------------------------


def test_neutralize_replaces_position_words_case_insensitively():
    text = "We rate NVDA a Buy. Others say SELL, and the desk says hold."

    clean, hits = jev.neutralize_positions(text)

    assert hits == 3
    assert jev.POSITION_MARKER in clean
    for word in ("Buy", "SELL", "hold"):
        assert word not in clean, f"{word!r} survived neutralisation"


def test_neutralize_consumes_a_multiword_position_whole():
    """`strong buy` must not leave `strong` sitting beside a marker."""
    clean, hits = jev.neutralize_positions("Our call is a strong buy here.")

    assert hits == 1
    assert "strong" not in clean
    assert clean.count(jev.POSITION_MARKER) == 1


def test_neutralize_leaves_words_that_merely_contain_a_position_alone():
    """The word boundaries are the whole point: `hold` is in `shareholders`."""
    text = "Buybacks lifted shareholders; holdings rose and a seller sold."

    clean, hits = jev.neutralize_positions(text)

    assert hits == 0, f"over-matched: {clean!r}"
    assert clean == text


def test_neutralize_leaves_ambiguous_market_english_alone():
    """`long`/`short`/`reduce`/`neutral` are evidence, not bias, in this domain."""
    text = "Long-term demand is firm; short interest fell; this reduces margin risk."

    clean, hits = jev.neutralize_positions(text)

    assert hits == 0, f"stripped evidence: {clean!r}"


def test_neutralize_is_a_no_op_on_a_report_with_no_position():
    text = "Revenue grew 12% and gross margin expanded 140bp."

    assert jev.neutralize_positions(text) == (text, 0)


def test_rating_battery_satisfies_the_endpoint_discriminator():
    jev.validate_questions(jev.RATING_QUESTIONS)
    assert set(jev.RATING_QUESTIONS["rating"]["criteria"]) == {"buy", "hold", "sell"}
    # the directional question is REPLACED, not joined by a second one
    assert "stance" not in jev.RATING_QUESTIONS


RATING_OK_BODY = json.dumps({
    "model": "typesafe/jev-1.13-20260917",
    "provider": "TypeSafe",
    "answers": {
        "rating": {"type": "choice", "choice": "hold", "confidence": 0.7,
                   "probabilities": {"buy": 0.1, "hold": 0.7, "sell": 0.2}},
    },
    "usage": {"input_tokens": 10, "output_tokens": 5, "cost": 0.0002},
})


def test_verdict_sends_only_analyst_reports_neutralised_and_rated(
    monkeypatch, tmp_path, capsys
):
    """The three requirements, asserted end to end through the CLI."""
    tree = _staged_tree(tmp_path)
    # All four analyst reports, so "analyst only" is a real filter and not an
    # artefact of the fixture having one.
    for stem in ("fundamentals", "news", "sentiment"):
        (tree / "1_analysts" / f"{stem}.md").write_text(f"{stem} body.", encoding="utf-8")
    (tree / "1_analysts" / "market.md").write_text(
        "We recommend a Buy on NVDA; the desk is at hold.", encoding="utf-8"
    )
    poster = _fake_poster(200, RATING_OK_BODY)

    code = _run_main(monkeypatch, tmp_path, poster, ["--tree", str(tree), "--verdict"])

    out = capsys.readouterr().out
    assert code == 0
    # (1) analyst reports ONLY - the tree holds 6 reports, 4 are analyst ones
    sent_names = [c[2]["state"] for c in poster.calls]
    assert len(poster.calls) == 4, f"sent {len(poster.calls)} states, expected 4"
    assert "BULL" not in sent_names, "a research report reached the judge"
    # (2) position language is gone before sending
    market = next(s for s in sent_names if "recommend" in s)
    assert jev.POSITION_MARKER in market
    assert "Buy" not in market and "hold" not in market
    assert "neutralize: market: 2 position term(s)" in out
    assert "neutralize: 2 replacement(s) across 4 report(s)" in out
    # (3) the buy/hold/sell battery is what was asked
    asked = poster.calls[0][2]["questions"]
    assert set(asked) == {"rating", "evidence", "horizon"}
    assert set(asked["rating"]["criteria"]) == {"buy", "hold", "sell"}
    assert "choice = hold" in out


def test_rating_alone_rates_without_stripping(monkeypatch, tmp_path, capsys):
    """The pieces compose: `--rating` must not silently de-bias."""
    tree = _staged_tree(tmp_path)
    (tree / "1_analysts" / "market.md").write_text("We recommend a Buy.", encoding="utf-8")
    poster = _fake_poster(200, RATING_OK_BODY)

    _run_main(monkeypatch, tmp_path, poster, ["--tree", str(tree), "--rating"])

    market = next(c[2]["state"] for c in poster.calls if "recommend" in c[2]["state"])
    assert "Buy" in market, "--rating must not neutralise on its own"
    assert jev.POSITION_MARKER not in market


def test_neutralize_alone_keeps_the_default_battery(monkeypatch, tmp_path):
    tree = _staged_tree(tmp_path)
    poster = _fake_poster(200, OK_BODY)

    _run_main(monkeypatch, tmp_path, poster, ["--tree", str(tree), "--neutralize"])

    assert set(poster.calls[0][2]["questions"]) == {"stance", "evidence", "horizon"}


def test_verdict_and_all_are_mutually_exclusive(tmp_path):
    """`--verdict` means analyst reports only; `--all` contradicts it."""
    with pytest.raises(SystemExit):
        jev._parse_args(["--verdict", "--all"])
