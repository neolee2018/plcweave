"""Independent S6 qualification fixtures. No serial ports or PLC source used.

These tests freeze evidence semantics before the sampled adapter is implemented.
They are not a hardware PASS and do not replace the frozen S1 suite.
"""
from copy import deepcopy

import pytest

from plcweave.sampled import evaluate_checkpoint, evaluate_timing_interval
from plcweave.validation import TraceOracle


@pytest.fixture
def quality():
    return {
        "transport_ok": True,
        "identity_ok": True,
        "applied_inputs_verified": True,
        "settled_after_ms": 20,
        "checkpoint_window_ms": [80, 100],
    }


def sample(start, end, **values):
    return {"start_ms": start, "end_ms": end, "values": values}


def verdicts(expectation, observations, quality, *, stable=(), phase=()):
    result = evaluate_checkpoint(
        expectation, observations, quality=quality,
        stable_devices=stable, phase_sensitive_devices=phase,
    )
    assert len(result) == len(expectation)
    assert {r["device"] for r in result} == set(expectation)
    assert all(r.get("reason") for r in result)
    return {r["device"]: r["status"] for r in result}


def test_two_bounded_stable_samples_qualify_exact_scalar(quality):
    observations = [sample(80, 85, D100=50), sample(90, 95, D100=50)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "PASS"}


def test_actual_stable_wrong_scaling_is_program_failure(quality):
    observations = [sample(80, 85, D100=49), sample(90, 95, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "PROGRAM_FAIL"}


def test_stable_stopped_output_nonzero_is_not_masked(quality):
    observations = [sample(80, 85, D154=2000), sample(90, 95, D154=2000)]
    assert verdicts({"D154": 0}, observations, quality, stable=["D154"]) == {"D154": "PROGRAM_FAIL"}


def test_one_sample_cannot_qualify_pass_or_fail(quality):
    for actual in (50, 49):
        assert verdicts({"D100": 50}, [sample(80, 85, D100=actual)], quality,
                        stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_last_two_must_be_stable_not_an_older_matching_pair(quality):
    observations = [sample(80, 82, D100=50), sample(84, 86, D100=50), sample(90, 95, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_missing_value_does_not_become_zero_or_stability(quality):
    observations = [sample(80, 85, D8051=0), sample(90, 95)]
    assert verdicts({"D8051": 0}, observations, quality, stable=["D8051"]) == {"D8051": "UNVERIFIED"}


def test_stability_requires_contract_classification_not_just_same_values(quality):
    observations = [sample(80, 85, M11=1), sample(90, 95, M11=1)]
    assert verdicts({"M11": 0}, observations, quality) == {"M11": "UNVERIFIED"}


def test_correct_pi_with_late_sampling_never_becomes_program_failure(quality):
    # Two stable polls can still be a different legal tick from the S1 endpoint.
    observations = [sample(80, 85, D120=20, D154=2102, D8050=1681),
                    sample(90, 95, D120=20, D154=2102, D8050=1681)]
    assert set(verdicts({"D120": 10, "D154": 2101, "D8050": 1680}, observations, quality,
                        stable=["D120", "D154", "D8050"],
                        phase=["D120", "D154", "D8050"]).values()) == {"UNVERIFIED"}


def test_diagnostics_are_never_exact_endpoint_clocks(quality):
    observations = [sample(80, 85, D198=5, D199=300), sample(90, 95, D198=5, D199=300)]
    assert set(verdicts({"D198": 1, "D199": 10}, observations, quality,
                        stable=["D198", "D199"]).values()) == {"UNVERIFIED"}


def test_late_convergence_cannot_replace_original_ten_ms_checkpoint(quality):
    quality["checkpoint_window_ms"] = [0, 10]
    quality["settled_after_ms"] = 0
    observations = [sample(0, 440, D100=50), sample(441, 880, D100=50)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_nonatomic_span_crossing_window_is_not_point_timestamp(quality):
    observations = [sample(70, 85, D100=49), sample(90, 105, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_samples_before_settle_do_not_prove_mismatch(quality):
    quality["settled_after_ms"] = 96
    observations = [sample(80, 85, D100=49), sample(90, 95, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_duplicate_or_overlapping_reads_are_not_two_independent_samples(quality):
    observations = [sample(80, 95, D100=49), sample(90, 99, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_unspecified_quality_does_not_default_to_qualified(quality):
    observations = [sample(80, 85, D100=50), sample(90, 95, D100=50)]
    for required in ("transport_ok", "identity_ok", "applied_inputs_verified"):
        incomplete = {key: value for key, value in quality.items() if key != required}
        assert verdicts({"D100": 50}, observations, incomplete,
                        stable=["D100"]) == {"D100": "UNVERIFIED"}


@pytest.mark.parametrize("flag", ["transport_ok", "identity_ok"])
def test_broken_evidence_chain_is_infrastructure_error(quality, flag):
    quality[flag] = False
    observations = [sample(80, 85, D100=49), sample(90, 95, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "TEST_INFRA_ERROR"}


def test_unproven_applied_input_is_not_program_failure(quality):
    quality["applied_inputs_verified"] = False
    observations = [sample(80, 85, D100=49), sample(90, 95, D100=49)]
    assert verdicts({"D100": 50}, observations, quality, stable=["D100"]) == {"D100": "UNVERIFIED"}


def test_projection_does_not_modify_frozen_expectations_or_observations(quality):
    expectation = {"D100": 50, "D8050": {"min": 0, "max": 4000}}
    observations = [sample(80, 85, D100=50, D8050=1600), sample(90, 95, D100=50, D8050=1600)]
    before = deepcopy((expectation, observations, quality))
    verdicts(expectation, observations, quality, stable=expectation)
    assert (expectation, observations, quality) == before


@pytest.mark.parametrize("trigger,transition,expected,status", [
    ([100, 110], [5090, 5110], {"min": 4900, "max": 5100}, "PASS"),
    ([100, 110], [2990, 3010], {"min": 2900, "max": 3100}, "UNVERIFIED"),
    ([100, 110], [3090, 3110], {"min": 2900, "max": 3100}, "PASS"),
    ([100, 200], [5000, 5400], {"min": 4900, "max": 5100}, "UNVERIFIED"),
    ([100, 110], [4500, 4600], {"min": 4900, "max": 5100}, "PROGRAM_FAIL"),
    ([100, 110], [5400, 5500], {"min": 4900, "max": 5100}, "PROGRAM_FAIL"),
    ([100, 110], [5200, 5210], {"min": 4900, "max": 5100}, "UNVERIFIED"),
])
def test_event_timing_uses_interval_arithmetic_without_relaxing_tolerance(trigger, transition, expected, status):
    result = evaluate_timing_interval(trigger_ms=trigger, transition_ms=transition, expected_ms=expected)
    assert result["status"] == status
    assert result["elapsed_ms"] == [transition[0]-trigger[1], transition[1]-trigger[0]]


def test_no_observed_transition_is_unverified():
    result = evaluate_timing_interval(trigger_ms=[100, 110], transition_ms=None,
                                      expected_ms={"min": 4900, "max": 5100})
    assert result["status"] == "UNVERIFIED"


def test_sampled_oracle_keeps_scan_relationships_unverified():
    # Synthetic toolkit fixture: no customer program or frozen suite is needed.
    case = {"id": "synthetic-case"}
    suite = {"scan_ms": 10, "relationship_invariants": [
        {"id": "scan-routing", "kind": "physical_routing"},
        {"id": "scan-pi", "kind": "independent_pi_recurrence"},
    ]}
    oracle = TraceOracle(suite, case, capabilities={"full_scan_trace": False, "verified_applied_inputs": False})
    oracle.consume({}, {}, 440)
    results = oracle.finish()
    assert {r["id"] for r in results} == {"scan-routing", "scan-pi"}
    assert {r["status"] for r in results} == {"UNVERIFIED"}
    assert all(r["evaluated_scans"] == 0 for r in results)
