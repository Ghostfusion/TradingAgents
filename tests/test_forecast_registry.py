"""Guards for the forecast registry (design doc §7.2 rules 2/6/8, plan FL-2).

The registry is a manifest of *declarations*, so the way it rots is silence: a
producer is renamed and the declared ``implementation_ref`` points at nothing, or
a second authority is added for a key already owned. Each test below therefore
carries a named mutation that must fail it - the plan's §6 table.

Offline, pure, sub-second: no vendor, no config, no network.
"""

from __future__ import annotations

import json

import pytest

from tradingagents import default_config
from tradingagents.strategies import forecast_contract as fc, forecast_registry as fr

pytestmark = pytest.mark.timeout(60)

_RV_KEY = ("realized_volatility", "single_asset", "1d", 1)


def _row(
    *,
    name="realized_volatility",
    scope="single_asset",
    frequency="1d",
    horizon=1,
    producer_id="dup.v1",
    ref="strategies/long_memory.py::rv_forecast",
    gate="enable_long_memory",
    status="ok",
    benchmark_ref="volatility.har_rv",
    reason_code=None,
    citation=None,
):
    return fr.RegistryRow(
        target=fc.TargetRef(
            name=name,
            definition="d",
            definition_version="d.v1",
            unit="variance",
            annualization=None,
        ),
        entity_scope=scope,
        frequency=frequency,
        horizon_steps=horizon,
        producer_id=producer_id,
        implementation_ref=ref,
        gate=gate,
        status=status,
        benchmark_ref=benchmark_ref,
        reason_code=reason_code,
        citation=citation,
    )


def test_no_key_has_two_authoritative_producers():
    dupes = fr._duplicate_keys(fr.FORECAST_REGISTRY)
    assert dupes == {}, f"two authoritative producers declared for {dupes}"

    # Mutation: point one key at two producers. The same check must see it.
    flagged = fr._duplicate_keys(
        (*fr.FORECAST_REGISTRY, _row(producer_id="long_memory.realized_volatility.v2"))
    )
    assert list(flagged) == [_RV_KEY]
    assert flagged[_RV_KEY] == 2


def test_candidate_members_do_not_collide_with_the_registry():
    union = (*fr.FORECAST_REGISTRY, *fr.CANDIDATE_MEMBERS)
    assert fr._duplicate_keys(union) == {}

    # FD-1 §3.2: a pool member may produce a value for the SAME key - several
    # candidates per target is the normal case, not a violation. What it may not
    # do is become a second AUTHORITY for that key.
    member = _row(producer_id="har_rv.pool_member.v1")
    assert fr._candidate_collisions(fr.FORECAST_REGISTRY, (member,)) == [_RV_KEY]
    assert fr._duplicate_keys((*union, member)), (
        "a member registered as an authority must trip the uniqueness gate"
    )


def test_every_declared_implementation_ref_resolves():
    producers = [row for row in fr.FORECAST_REGISTRY if row.status != "declined"]
    assert producers, "the registry declares at least one producer"
    for row in producers:
        module_name, symbol = fr._module_and_attr(row.implementation_ref)
        assert module_name.startswith("tradingagents."), row.implementation_ref
        assert symbol
        assert callable(fr._resolve(row.implementation_ref)), row.implementation_ref

    # Mutation: rename a symbol - the failure names the symbol, not a silent None.
    with pytest.raises(fr.ForecastRegistryError) as excinfo:
        fr._resolve("strategies/long_memory.py::rv_forecast_renamed")
    assert "rv_forecast_renamed" in str(excinfo.value)
    with pytest.raises(fr.ForecastRegistryError):
        fr._resolve("strategies/long_memory.py")


def test_every_producer_id_is_stable_and_not_a_code_path():
    for row in (*fr.FORECAST_REGISTRY, *fr.CANDIDATE_MEMBERS):
        if row.status == "declined":
            assert row.producer_id is None
            continue
        assert ".py" not in row.producer_id
        assert "::" not in row.producer_id
        assert row.producer_id != row.implementation_ref
    with pytest.raises(fr.ForecastRegistryError):
        _row(producer_id="strategies/long_memory.py::rv_forecast")


def test_every_declared_gate_is_a_real_config_key():
    declared = default_config.DEFAULT_CONFIG
    for row in (*fr.FORECAST_REGISTRY, *fr.CANDIDATE_MEMBERS):
        if row.gate is not None:
            assert row.gate in declared, f"{row.gate} is not a config key"
            assert declared[row.gate] is False, (
                f"{row.gate} ships on; a forecast producer's gate ships off (docs/gate_registry.md)"
            )
    with pytest.raises(fr.ForecastRegistryError):
        _row(gate="nope")
    # And the loop's own check is the real one: a name outside DEFAULT_CONFIG is
    # exactly what it refuses, even when it wears the `enable_` prefix.
    assert "enable_nope" not in declared


def test_the_block_is_json_able_and_declares_every_row():
    block = fr.forecast_registry_block()
    assert block["n_rows"] == len(fr.FORECAST_REGISTRY)
    assert len(block["rows"]) == len(fr.FORECAST_REGISTRY)
    json.dumps(block)
    first = block["rows"][0]
    assert set(first["key"]) == {"target_name", "entity_scope", "frequency", "horizon_steps"}
    assert first["status"] in fc.FORECAST_STATUSES
    assert first["benchmark_ref"] in fr.BENCHMARK_REFS


# ---------------------------------------------------------------------------
# FL-6 - the benchmark declaration (design doc §8.2)
# ---------------------------------------------------------------------------


def test_every_admitted_forecast_names_a_benchmark():
    for row in fr.FORECAST_REGISTRY:
        if row.status == "declined":
            assert row.benchmark_ref is None, "a declined row is not scored, so it names no benchmark"
            continue
        assert row.benchmark_ref in fr.BENCHMARK_BY_FAMILY[row.target.name], row.target.name

    # Mutation: add a row with no benchmark - refused by name, not silently scored.
    with pytest.raises(fr.ForecastRegistryError) as excinfo:
        _row(benchmark_ref=None)
    assert "benchmark" in str(excinfo.value)
    with pytest.raises(fr.ForecastRegistryError):
        _row(benchmark_ref="volatility.made_up")
    # ...and a properly CITED declined row may leave the benchmark unset.
    declined = _row(
        name="absolute_return",
        status="declined",
        producer_id=None,
        ref=None,
        gate=None,
        benchmark_ref=None,
        reason_code="RETURN_LEVEL_NOT_ADMITTED",
        citation="cited; never scored, so never benchmarked",
    )
    assert declined.benchmark_ref is None


def test_every_target_family_declares_a_benchmark():
    for name in fc.TARGET_NAMES:
        assert name in fr.BENCHMARK_BY_FAMILY, f"{name} has no declared benchmark"
        assert fr.BENCHMARK_BY_FAMILY[name], name
    assert fr.INTERVAL_BENCHMARK in fr.BENCHMARK_REFS
    # `absolute_return`'s three baselines are three distinct hypotheses, not one line.
    assert len(fr.BENCHMARK_BY_FAMILY["absolute_return"]) == 3


def test_directional_families_carry_both_ceilings():
    for name in fr.DIRECTIONAL_TARGETS:
        assert name in fr.BENCHMARK_BY_FAMILY
    assert fr.DIRECTIONAL_CEILINGS == {"out_of_sample_r2": "2602.07841", "base_rate": "H4"}


# ---------------------------------------------------------------------------
# FL-3 - the return families ship declined, cited
# ---------------------------------------------------------------------------


def test_return_targets_are_declined_with_codes():
    declined = {row.target.name: row for row in fr.FORECAST_REGISTRY if row.status == "declined"}
    assert set(declined) == {"absolute_return", "return_rank"}, (
        "exactly the two owner-ratified refusals ship declined (design doc §11.1)"
    )
    assert declined["absolute_return"].reason_code == "RETURN_LEVEL_NOT_ADMITTED"
    assert declined["return_rank"].reason_code == "RETURN_RANK_NOT_ADMITTED"
    assert "Hjalmarsson" in declined["absolute_return"].citation
    assert "2607.27461" in declined["return_rank"].citation
    for row in declined.values():
        assert row.citation.strip()
        assert row.producer_id is None
        assert row.implementation_ref is None
        assert row.gate is None
        assert row.benchmark_ref is None

    # The refusal is a policy, not a hole: no directional return target may be `ok`.
    for row in fr.FORECAST_REGISTRY:
        if row.target.name in fr.DIRECTIONAL_TARGETS:
            assert row.status == "declined", f"{row.target.name} must not be admitted"

    # Mutations: an uncited refusal, a free-prose code, and a declined row that
    # still claims a producer are each refused by name.
    with pytest.raises(fr.ForecastRegistryError) as excinfo:
        _row(name="absolute_return", status="declined", reason_code=None, citation="x")
    assert "uncited" in str(excinfo.value)
    with pytest.raises(fr.ForecastRegistryError):
        _row(name="absolute_return", status="declined", reason_code="not_admitted", citation="x")
    with pytest.raises(fr.ForecastRegistryError):
        _row(
            name="absolute_return",
            status="declined",
            reason_code="RETURN_LEVEL_NOT_ADMITTED",
            citation="x",
        )
    # ...and an `ok` row may not carry a refusal's code/citation.
    with pytest.raises(fr.ForecastRegistryError):
        _row(reason_code="GATE_OFF", citation="x")


# ---------------------------------------------------------------------------
# FL-6: a ref the registry binds to an implementation must resolve.
# ---------------------------------------------------------------------------


def test_every_bound_benchmark_ref_resolves_against_the_live_tree():
    """A ref in ``BENCHMARK_IMPLEMENTATIONS`` must name a real symbol.

    This is the rule ``implementation_ref`` already gets, applied to the
    benchmark half: a renamed producer has to fail a build rather than leave a
    row declaring a benchmark nobody can produce - which is how
    ``regime.sticky_markov`` was missing before E15 implemented it (D5).
    """
    for ref, (module_path, symbol) in fr.BENCHMARK_IMPLEMENTATIONS.items():
        assert ref in fr.BENCHMARK_REFS, f"{ref} is not a declared benchmark ref"
        producer = fr.benchmark_producer(ref)
        assert producer is not None, f"{module_path}::{symbol} does not resolve"
        assert producer.__name__ == symbol


def test_a_label_only_benchmark_has_no_producer():
    """Most refs are labels: the caller supplies the score (FINDINGS §5)."""
    assert fr.benchmark_producer("volatility.har_rv") is None
    assert fr.benchmark_producer("no.such.ref") is None


def test_the_regime_rows_declared_benchmark_is_producible():
    row = next(r for r in fr.FORECAST_REGISTRY
               if r.target.name == "regime_stress_probability")
    assert row.benchmark_ref == "regime.sticky_markov"
    assert fr.benchmark_producer(row.benchmark_ref) is not None
