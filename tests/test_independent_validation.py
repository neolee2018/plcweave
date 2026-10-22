"""Independent comparison regressions: interior defects must not escape."""
import copy
import hashlib
import pytest
from plcweave.testing import compare, engine_gate
from plcweave.validation import (
    INPUTS, KINDS, PARAMS, SCHEMA, InputImage, TraceOracle,
    independent_fingerprint, validate_suite,
)

CAPS = {"full_scan_trace": True, "verified_applied_inputs": True}

def check(kind, *, caps=CAPS):
    suite = {"scan_ms": 10, "relationship_invariants": [{"id": "r", "kind": kind}]}
    return TraceOracle(suite, {"id": "t"}, capabilities=caps)

def inputs(**kwargs):
    result = dict.fromkeys(INPUTS, 0)
    result.update(D102=60, D190=1, D261=60)
    result.update(kwargs)
    return result

def test_one_scan_routing_fault_with_correct_endpoint_is_rejected():
    oracle = check("physical_routing")
    correct = {"M0": 1, "D154": 2101, "Y0": 1, "D8050": 1680, "D8051": 0}
    for t, values in [(10, correct), (20, {**correct, "D8050": 2101}), (30, correct)]:
        oracle.consume(values, inputs(D193=1), t)
    result = oracle.finish()[0]
    assert result["status"] == "PROGRAM_FAIL"
    assert result["evaluated_scans"] == 3
    assert result["failures"][0]["time_ms"] == 20

@pytest.mark.parametrize("caps", [{}, {"full_scan_trace": False, "verified_applied_inputs": True}])
def test_sampled_trace_cannot_certify_scan_level_assertions(caps):
    oracle = check("physical_routing", caps=caps)
    oracle.consume({"M0": 0, "D154": 0, "Y0": 0, "D8050": 0, "D8051": 0}, inputs(), 10)
    assert oracle.finish()[0]["status"] == "UNVERIFIED"

def test_gap_and_missing_observation_are_unverified():
    oracle = check("physical_routing")
    values = {"M0": 0, "D154": 0, "Y0": 0, "D8050": 0, "D8051": 0}
    oracle.consume(values, inputs(), 10)
    oracle.consume(values, inputs(), 30)
    assert oracle.finish()[0]["status"] == "UNVERIFIED"
    missing = check("physical_routing")
    missing.consume({}, inputs(), 10)
    assert missing.finish()[0]["status"] == "UNVERIFIED"

def test_pi_only_updates_on_rising_edges_and_skips_transition_scan():
    oracle = check("independent_pi_recurrence")
    def obs(run=1, clock=1, integral=0, frequency=2000):
        return {"M0": run, "M10": 0, "M11": 0, "M8012": clock,
                "D100": 50, "D102": 60, "D120": integral, "D154": frequency}
    oracle.consume(obs(run=0, frequency=0), inputs(D1056=1250), 10)
    oracle.consume(obs(), inputs(D191=1, D1056=1250), 20)
    # A nonedge interior update that is restored before the endpoint still fails.
    oracle.consume(obs(integral=10, frequency=2101), inputs(D191=1, D1056=1250), 30)
    oracle.consume(obs(), inputs(D191=1, D1056=1250), 40)
    assert oracle.finish()[0]["status"] == "PROGRAM_FAIL"
    good = check("independent_pi_recurrence")
    good.consume(obs(run=0, frequency=0), inputs(D1056=1250), 10)
    good.consume(obs(), inputs(D191=1, D1056=1250), 20)
    good.consume(obs(clock=0), inputs(D191=1, D1056=1250), 30)
    good.consume(obs(clock=1, integral=10, frequency=2101), inputs(D191=1, D1056=1250), 40)
    assert good.finish()[0]["status"] == "PASS"
    assert good.metrics()["pi_updates"] == 1

def test_invalid_mode_requires_valid_zero_then_subsequent_one():
    oracle = check("command_state_oracle")
    sequence = [
        (inputs(), 0), (inputs(D191=1), 1),
        (inputs(D190=2, D191=1), 0),
        (inputs(D190=2, D191=0), 0),
        (inputs(D191=1), 0),  # invalid-mode zero did not release inhibit
        (inputs(D191=0), 0), (inputs(D191=1), 1),
        (inputs(D191=1, D192=1), 0),
    ]
    for n, (image, run) in enumerate(sequence, 1):
        oracle.consume({"M0": run}, image, n*10)
    assert oracle.finish()[0]["status"] == "PASS"

def test_timer_rejects_accumulation_across_one_scan_gap():
    oracle = check("continuous_timers")
    oracle.consume({"M0": 0, "M10": 0, "M11": 0, "D100": 0, "D260": 58, "D262": 51}, inputs(), 10)
    for n in range(2, 482):
        oracle.consume({"M0": 1, "M10": 1, "M11": 0, "D100": 58, "D260": 58, "D262": 51}, inputs(D191=1, D1056=1450), n*10)
    oracle.consume({"M0": 1, "M10": 0, "M11": 0, "D100": 57, "D260": 58, "D262": 51}, inputs(D191=1, D1056=1425), 4820)
    oracle.consume({"M0": 1, "M10": 1, "M11": 0, "D100": 58, "D260": 58, "D262": 51}, inputs(D191=1, D1056=1450), 4830)
    oracle.consume({"M0": 1, "M10": 0, "M11": 1, "D100": 58, "D260": 58, "D262": 51}, inputs(D191=1, D1056=1450), 4840)
    result = oracle.finish()[0]
    assert result["status"] == "PROGRAM_FAIL"
    assert result["failures"][0]["actual"] == 10

def test_input_shadow_is_independent_of_program_mutation_and_first_scan_defaults():
    image = InputImage({"D191": 1, "D261": 9, "D195": 234})
    assert image.next_scan() == inputs()
    image.apply({"D102": -1, "D190": 2, "D261": 100})
    expected = image.next_scan()
    assert expected["D102"] == 10 and expected["D190"] == 2 and expected["D261"] == 100

def test_independent_fingerprint_normalization_and_exclusion(tmp_path):
    path = tmp_path / "source.fxil"
    path.write_text("#instructions\nld  m8000 // control\n// BEGIN_IDENTITY\nLD M8002\nMOV K3 D200\n// END_IDENTITY\nend\n#comments\n", encoding="utf-8")
    result = independent_fingerprint(path)
    digest = hashlib.sha256(b"LD M8000\nEND\n").digest()
    assert result["canonical_sha256"] == digest.hex()
    path.write_text(path.read_text().replace("MOV K3 D200", "SET Y0"))
    with pytest.raises(ValueError, match="nonidentity"):
        independent_fingerprint(path)
    path.write_text("#instructions\nEND\n#comments\n")
    with pytest.raises(ValueError, match="identity block"):
        independent_fingerprint(path)

def contract():
    return {"schema_version": SCHEMA, "scan_ms": 10, "relationship_invariants": [
        {"id": str(n), "kind": kind, "params": PARAMS.get(kind, {})}
        for n, kind in enumerate(sorted(KINDS))], "oracle_contract": {},
        "cases": [{"id": "t", "priority": "MUST", "steps": [{"duration_ms": 10}]}]}

def test_unknown_contract_fields_types_and_parameters_fail_closed():
    suite = contract()
    validate_suite(suite)
    bad = copy.deepcopy(suite)
    bad["cases"][0]["steps"][0]["new_check"] = 1
    with pytest.raises(ValueError, match="Unsupported step"):
        validate_suite(bad)
    bad = copy.deepcopy(suite)
    bad["relationship_invariants"][0]["kind"] = "ignore_me"
    with pytest.raises(ValueError, match="Unsupported relationship kind"):
        validate_suite(bad)
    bad = copy.deepcopy(suite)
    next(x for x in bad["relationship_invariants"] if x["kind"] == "independent_pi_recurrence")["params"]["integral_divisor"] = 9
    with pytest.raises(ValueError, match="Unsupported parameters"):
        validate_suite(bad)
    with pytest.raises(ValueError, match="Unsupported scalar"):
        compare({"D0": 0}, {"D0": {"relationship": "D1"}})

def test_actual_engine_blocks_unsupported_instructions_and_addresses(tmp_path):
    result = engine_gate(tmp_path)
    assert result["status"] == "PASS", result
    assert len(result["fixtures"]) == 4
    assert not list(tmp_path.iterdir())

def test_legacy_numeric_schema_keeps_scalar_simulation_path(tmp_path):
    import json
    from plcweave.testing import digest, simulate
    suite = {"schema_version": 1, "suite_version": "legacy", "scan_ms": 10,
             "watch": ["M0"], "global_invariants": {"M0": 1},
             "cases": [{"id": "legacy", "initial_words": {}, "steps": [
                 {"write": {}, "duration_ms": 20, "invariant": {}, "expect": {"M0": 1}}]}]}
    (tmp_path/"test_cases.json").write_text(json.dumps(suite))
    (tmp_path/"source.fxil").write_text("#instructions\nLD M8000\nOUT M0\nEND\n")
    (tmp_path/"s1-freeze.json").write_text(json.dumps({"test_cases.json": digest(tmp_path/"test_cases.json")}))
    report = simulate(tmp_path)
    assert report["status"] == "SIM_PASS"
    assert "relationships" not in report["cases"][0]
    assert (tmp_path/"candidate/V001/simulation_trace.csv").is_file()
