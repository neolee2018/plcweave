from pathlib import Path
import pytest
from plcweave.testing import frozen_suite
from plcweave.validation import TraceOracle

def test_sampled_oracle_keeps_all_original_relationships_unverified():
    directory = Path(__file__).resolve().parents[1]
    if not directory.exists():
        pytest.skip("Private S1 suite is not distributed with portable installs")
    suite = frozen_suite(directory)
    assert len(suite["cases"]) == 55
    assert sum(c["hardware_scope"] == "bench" for c in suite["cases"]) == 52
    case = suite["cases"][0]
    oracle = TraceOracle(suite, case, capabilities={"full_scan_trace": False, "verified_applied_inputs": False})
    oracle.consume({}, {}, 440)
    results = oracle.finish()
    assert {r["id"] for r in results} == {r["id"] for r in suite["relationship_invariants"] if "case_ids" not in r or case["id"] in r["case_ids"]}
    assert {r["status"] for r in results} == {"UNVERIFIED"}
    assert all(r["evaluated_scans"] == 0 for r in results)
