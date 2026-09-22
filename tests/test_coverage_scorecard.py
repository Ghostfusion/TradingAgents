"""Field-level coverage scorecard (``scripts/coverage_scorecard.py``).

The scorecard's whole value is that a zero fill rate is *classified*, not just
counted, so these tests defend the classification and the two ways it could
silently lie: reading presence off a value instead of an explicit list, and
calling a producer unwired when it is merely imported under an alias.
"""

from __future__ import annotations

import json

import scripts.coverage_scorecard as cs

# ---------------------------------------------------------------------------
# Presence: explicit signals only
# ---------------------------------------------------------------------------


def test_a_measured_zero_is_present_not_a_gap():
    """`adx: 0.0` is a measurement. Reading presence off truthiness loses it."""
    block = {"score": 50.0, "components": {"adx": {"raw": 0.0, "aligned": 0.0}}}
    declared = {"adx": {"category": "trend", "producer": ""}}
    assert cs.field_states(block, declared) == {"adx": "present"}


def test_a_none_reading_is_absent():
    block = {"score": 50.0, "components": {"adx": {"raw": None, "aligned": None}}}
    declared = {"adx": {"category": "trend", "producer": ""}}
    assert cs.field_states(block, declared) == {"adx": "absent"}


def test_an_absent_only_engine_uses_the_complement_rule():
    """sentiment/news publish only `absent`; the engines define it as the
    complement of what they measured, so reading it back is reading their rule."""
    block = {"score": 1.0, "absent": ["a"]}
    declared = {"a": {"producer": ""}, "b": {"producer": ""}}
    assert cs.field_states(block, declared) == {"a": "absent", "b": "present"}


def test_an_explicit_present_list_wins_over_the_complement_rule():
    """A field the card says nothing about is omitted, never guessed at."""
    block = {"score": 1.0, "absent": ["b"],
             "categories": {"trend": {"components": ["a"]}}}
    declared = {"a": {"producer": ""}, "b": {"producer": ""}, "c": {"producer": ""}}
    states = cs.field_states(block, declared)
    assert states == {"a": "present", "b": "absent"}
    assert "c" not in states


def test_every_absent_signal_is_read():
    """Engine `absent`, a subscore's `factors_NA`, and a regime-style
    `components` entry whose `raw` is None all mean the same thing."""
    block = {
        "score": 1.0,
        "absent": ["e1"],
        "subscores": {"FQS": {"factors_NA": ["s1"], "coverage": {"metrics": ["s2"]}}},
        "components": {"r1": {"raw": None}, "r2": {"raw": 0.5}},
    }
    declared = {k: {"producer": ""} for k in ("e1", "s1", "s2", "r1", "r2")}
    states = cs.field_states(block, declared)
    assert states["e1"] == "absent"
    assert states["s1"] == "absent"
    assert states["s2"] == "present"
    assert states["r1"] == "absent"
    assert states["r2"] == "present"


# ---------------------------------------------------------------------------
# The denominator
# ---------------------------------------------------------------------------


def _write_tree(root, name, card):
    d = root / name
    d.mkdir(parents=True)
    (d / cs.CARD_NAME).write_text(json.dumps(card), encoding="utf-8")


def test_a_gated_off_engine_leaves_the_denominator(tmp_path):
    """A tree where the engine was not scored must not dilute its fill rate."""
    scored = {"score": 10.0, "absent": ["pct_above_50d"]}
    _write_tree(tmp_path, "T1", {"technical_score": scored})
    _write_tree(tmp_path, "T2", {"technical_score": scored})
    _write_tree(tmp_path, "T3", {"news_score": {"score": 1.0}})  # engine absent

    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    ent = report["engines"]["technical_score"]
    assert ent["trees_measured"] == 2
    assert ent["fields"]["pct_above_50d"]["stated"] == 2
    assert ent["fields"]["pct_above_50d"]["measured"] == 0
    assert ent["fields"]["pct_above_50d"]["fill_rate"] == 0.0


def test_a_tree_without_a_card_is_skipped(tmp_path):
    _write_tree(tmp_path, "T1", {"technical_score": {"score": 10.0, "absent": []}})
    (tmp_path / "BROKEN").mkdir()
    (tmp_path / "BROKEN" / cs.CARD_NAME).write_text("{not json", encoding="utf-8")
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    assert report["trees"] == 1


def test_a_half_measured_field_reports_half(tmp_path):
    _write_tree(tmp_path, "T1", {"technical_score": {"score": 10.0, "absent": []}})
    _write_tree(tmp_path, "T2", {"technical_score": {"score": 10.0, "absent": ["rsi"]}})
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    rsi = report["engines"]["technical_score"]["fields"]["rsi"]
    assert (rsi["measured"], rsi["stated"], rsi["fill_rate"]) == (1, 2, 0.5)
    assert rsi["class"] == "monitor"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classify_separates_the_three_zero_fill_cases():
    assert cs.classify(0.0, "", True) == "unbuilt"
    assert cs.classify(0.0, "p.py::f:1", False) == "unwired"
    assert cs.classify(0.0, "p.py::f:1", True) == "structural"


def test_classify_is_unknown_rather_than_guessing():
    assert cs.classify(0.0, "p.py::f:1", None) == "unknown"
    assert cs.classify(None, "p.py::f:1", None) == "unknown"


def test_classify_bands():
    assert cs.classify(1.0, "", None) == "ok"
    assert cs.classify(cs.FILL_OK, "", None) == "ok"
    assert cs.classify(cs.FILL_MONITOR, "", None) == "monitor"
    assert cs.classify(0.01, "", None) == "sparse"


def test_an_engine_without_a_producer_column_is_not_reported_unbuilt():
    """fundamental_score's factors come from SUBSCORE_FACTORS, which carries no
    producer. An empty producer there says nothing about the field."""
    assert cs.classify(0.0, "", None, has_producer_column=False) == "unknown"
    assert cs.classify(0.0, "", None, has_producer_column=True) == "unbuilt"


# ---------------------------------------------------------------------------
# Producer parsing
# ---------------------------------------------------------------------------


def test_parse_producer_reads_both_declared_shapes():
    own, funcs = cs.parse_producer("strategies/market_breadth.py::market_breadth:44")
    assert own == "strategies/market_breadth.py"
    assert funcs == ("market_breadth",)

    own, funcs = cs.parse_producer("options_surface.implied_move_pct:42")
    assert own is not None and own.endswith("options_surface.py")
    assert funcs == ("implied_move_pct",)


def test_parse_producer_names_no_callable_for_prose():
    assert cs.parse_producer("") == (None, ())
    assert cs.parse_producer("caller-supplied (EventScore, owner Q6)") == (None, ())


def test_parse_producer_reads_the_two_producer_form():
    own, funcs = cs.parse_producer("sentiment.mention_volume:43 + decayed_weight:91")
    assert own is not None and own.endswith("sentiment.py")
    assert set(funcs) == {"mention_volume", "decayed_weight"}


# ---------------------------------------------------------------------------
# The call-site scan
# ---------------------------------------------------------------------------


def _scan(tmp_path, producer_file: str, caller: str):
    (tmp_path / "producer.py").write_text(producer_file, encoding="utf-8")
    if caller is not None:
        (tmp_path / "caller.py").write_text(caller, encoding="utf-8")
    spec = f"{tmp_path / 'producer.py'}::thing:1"
    return cs.has_call_site(spec, roots=(str(tmp_path),))


def test_a_string_citation_is_not_a_call_site(tmp_path):
    """The engines cite their producers as string literals in their own
    component tables. A citation is not a call."""
    got = _scan(tmp_path, "def thing():\n    return 1\n",
                'CITE = "thing"\nNOTE = "producer.thing:1"\n')
    assert got is False


def test_a_plain_call_is_a_call_site(tmp_path):
    assert _scan(tmp_path, "def thing():\n    return 1\n",
                 "from producer import thing\nthing()\n") is True


def test_an_alias_import_is_a_call_site(tmp_path):
    """`analysis_tools.get_liquidation_days` renames its producer on import
    (`days_to_absorb as _dta`). Reading only the call node's own name reports
    that producer as never called - a manufactured defect."""
    assert _scan(tmp_path, "def thing():\n    return 1\n",
                 "from producer import thing as _t\n_t()\n") is True


def test_an_attribute_call_is_a_call_site(tmp_path):
    assert _scan(tmp_path, "def thing():\n    return 1\n",
                 "import producer\nproducer.thing()\n") is True


def test_has_call_site_is_none_when_the_file_does_not_define_the_function(tmp_path):
    """A same-named module in another checkout must not be called unwired."""
    assert _scan(tmp_path, "def other():\n    return 1\n",
                 "other()\n") is None


def test_has_call_site_is_none_when_the_module_resolves_nowhere():
    assert cs.has_call_site("no_such_module_anywhere.thing:1") is None


def test_the_scan_reads_the_real_producer_strings():
    """The declared producers resolve under the package root, not the cwd."""
    own, funcs = cs.parse_producer("strategies/market_breadth.py::market_breadth:44")
    resolved = cs._resolve_own(own)
    assert resolved is not None and resolved.replace("\\", "/").endswith(
        "tradingagents/strategies/market_breadth.py")
    assert cs._defines(resolved, funcs) is True


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_text_reports_the_totals(tmp_path):
    _write_tree(tmp_path, "T1", {"technical_score": {"score": 10.0, "absent": ["rsi"]}})
    report = cs.build_scorecard(str(tmp_path), engines=("technical_score",))
    text = cs.render_text(report)
    assert "Field coverage scorecard" in text
    assert "rsi" in text
    assert "totals:" in text


def test_render_text_survives_an_empty_reports_dir(tmp_path):
    report = cs.build_scorecard(str(tmp_path))
    assert "no trees" in cs.render_text(report)


def test_main_actionable_lists_only_the_actionable_gaps(tmp_path, capsys):
    """`--actionable` is the to-do list: unbuilt/unwired rows, not healthy ones."""
    _write_tree(tmp_path, "T1",
                {"news_score": {"score": 10.0, "absent": ["fundamental_impact"]}})
    rc = cs.main(["--reports-dir", str(tmp_path), "--engine", "news_score",
                  "--actionable"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fundamental_impact" in out  # declared producer is empty -> unbuilt
    assert "relevance" not in out  # measured, so not a gap


# ---------------------------------------------------------------------------
# Why a gap is a gap
# ---------------------------------------------------------------------------


def test_every_unmeasured_field_carries_a_reason(tmp_path):
    """An empty field states WHY it is empty. The whole point is that the gap
    stays visible instead of inviting a number the repo cannot support."""
    card = {
        "news_score": {
            "score": 12.0,
            "absent": ["fundamental_impact", "persistence"],
            "categories": {"fundamental_impact": {"score": None, "weight": 20.0}},
        },
    }
    _write_tree(tmp_path, "T1", card)
    report = cs.build_scorecard(str(tmp_path), engines=("news_score",))
    fields = report["engines"]["news_score"]["fields"]
    for name in ("fundamental_impact", "persistence"):
        f = fields[name]
        assert f["fill_rate"] == 0.0
        assert f["gap"], f"{name} is empty with no recorded reason"
        assert len(f["gap"]) > 40, "a reason, not a placeholder"
    assert "do not build it" in fields["fundamental_impact"]["gap"]


def test_a_measured_field_carries_no_excuse(tmp_path):
    """The reason is for gaps only - a filled field needs none."""
    card = {"news_score": {"score": 60.0, "absent": ["fundamental_impact"],
                           "categories": {"novelty": {"components": ["novelty"]}}}}
    _write_tree(tmp_path, "T1", card)
    report = cs.build_scorecard(str(tmp_path), engines=("news_score",))
    fields = report["engines"]["news_score"]["fields"]
    assert fields["novelty"]["fill_rate"] == 1.0
    assert fields["novelty"]["gap"] is None


def test_the_engines_own_reason_is_used_when_none_is_authored():
    """An engine that records its own absent-reason gets it printed, so the
    report and the engine cannot drift apart - and an authored reason wins."""
    table = {"widget": "no widget producer exists"}
    assert cs.gap_reason("unknown_engine", "widget", "unbuilt", absent=table) == (
        "no widget producer exists (the engine's own reason)"
    )
    # the authored reason for a known gap WINS over any engine table
    authored = cs.gap_reason("news_score", "fundamental_impact", "unbuilt", absent=table)
    assert authored.startswith("no revenue or margin ESTIMATE")
    # with nothing recorded anywhere, a class default still answers
    assert cs.gap_reason("unknown_engine", "widget", "unbuilt", absent={})


def test_the_real_engine_absent_table_is_read_at_runtime():
    """`news_score.ABSENT_REASONS` is read from the engine, never copied here."""
    reasons = cs._absent_reasons("tradingagents.strategies.news_score")
    assert "materiality" in reasons
    assert "revenue/margin" in reasons["fundamental_impact"]
    assert cs._absent_reasons("") == {}
    assert cs._absent_reasons("no.such.module") == {}


def test_an_unwired_reason_names_the_indirect_dispatch_blind_spot():
    """`unwired` means "no DIRECT call site" - the scan cannot see a
    VENDOR_METHODS / route_to_vendor dict lookup, and the default says so."""
    reason = cs.gap_reason("some_engine", "some_field", "unwired", absent={})
    assert "DIRECT" in reason and "VENDOR_METHODS" in reason
