"""Reproduce independent S3 CSV review and semantic mutation experiments.

Run with workspace .venv Python and PYTHONPATH=src. No serial/GX operations.
Every mutant keeps the exact frozen suite and obtains its own valid identity.
"""
import argparse
import csv
import json
import re
import shutil
from pathlib import Path

from plcweave.testing import digest, frozen_suite, simulate
from plcweave.validation import INPUTS, InputImage, TraceOracle, independent_fingerprint

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"

def replay():
    suite = frozen_suite(ROOT)
    report = json.loads((EVIDENCE/"simulation/latest/simulation_report.json").read_text())
    fingerprint = independent_fingerprint(ROOT/"source.fxil")
    assert report["source_sha256"] == digest(ROOT/"source.fxil")
    assert report["test_sha256"] == digest(ROOT/"test_cases.json")
    oracles = {case["id"]: TraceOracle(suite, case,
        capabilities={"full_scan_trace": True, "verified_applied_inputs": True},
        context={**fingerprint, "engine_gate_pass": report["engine_gate"]["status"] == "PASS"}) for case in suite["cases"]}
    cases = {case["id"]: case for case in suite["cases"]}
    images = {case["id"]: InputImage(case["initial_words"]) for case in suite["cases"]}
    step_indices = dict.fromkeys(cases, -1)
    row_counts = dict.fromkeys(cases, 0)
    trace = EVIDENCE/"simulation/latest/simulation_trace.csv"
    with trace.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            case_id, step = row["case_id"], int(row["step"])
            image = images[case_id]
            if step != step_indices[case_id]:
                assert step == step_indices[case_id] + 1
                image.apply(cases[case_id]["steps"][step]["write"])
                step_indices[case_id] = step
            # Audit the raw applied inputs independently against frozen scripts.
            assert all(int(row["applied_"+name]) == image.values[name] for name in INPUTS)
            observed = {name: int(row[name]) for name in suite["watch"]}
            oracles[case_id].consume(observed, image.next_scan(), int(row["time_ms"]))
            row_counts[case_id] += 1
    results = [{"id": case_id, "rows": row_counts[case_id], "relationships": oracle.finish(), "metrics": oracle.metrics()}
               for case_id, oracle in oracles.items()]
    assert all(r["status"] == "PASS" for c in results for r in c["relationships"])
    result = {"status": "PASS", "source_sha256": digest(ROOT/"source.fxil"),
        "test_sha256": digest(ROOT/"test_cases.json"), "trace_sha256": digest(trace),
        "total_rows": sum(row_counts.values()), "cases": results}
    (EVIDENCE/"S3-full-trace-review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Full CSV replay PASS", result["total_rows"], flush=True)
    return result

MUTATIONS = [
    ("missing_stop_priority", "AND= D192 K1", "AND= D192 K-1234", "command_state_oracle"),
    ("incorrect_enable_gate", "AND= D193 K1", "AND>= D193 K0", "physical_routing"),
    ("incorrect_pi_divisor", "DIV D120 K10 D124", "DIV D120 K9 D124", "independent_pi_recurrence"),
    ("pi_every_scan", "AND M2\n", "AND M8000\n", "independent_pi_recurrence"),
    ("timer_runs_across_gaps", "LD M10\nOUT T0 K50", "LD M0\nOUT T0 K50", "continuous_timers"),
    ("wrong_adc_channel", "MOV D8030 D110", "MOV D8031 D110", "scaling_settings"),
    ("one_scan_ao_spike", "\nEND\n", "\nLD M8000\nAND= D199 K100\nMOV K4000 D8050\nEND\n", "physical_routing"),
]

def mutations():
    frozen_suite(ROOT)
    original = (ROOT/"source.fxil").read_text(encoding="utf-8")
    summaries = []
    for name, old, new, target in MUTATIONS:
        folder = EVIDENCE/"S3-mutations"/name
        folder.mkdir(parents=True, exist_ok=True)
        for file in ("requirements.md", "test_cases.json", "s1-freeze.json"):
            shutil.copyfile(ROOT/file, folder/file)
        assert old in original
        mutated = original.replace(old, new)
        source = folder/"source.fxil"
        source.write_text(mutated, encoding="utf-8")
        identity = independent_fingerprint(source)
        for device, word in zip(("D200", "D201"), identity["fingerprint_words"]):
            mutated, count = re.subn(rf"MOV K-?\d+ {device}\b", f"MOV K{word} {device}", mutated)
            assert count == 1
        source.write_text(mutated, encoding="utf-8")
        report = simulate(folder, output=folder/"run")
        assert report["status"] == "PROGRAM_FAIL", (name, report["status"])
        assert report["relationship_coverage"]["independent_fingerprint"]["statuses"] == ["PASS"], name
        assert report["relationship_coverage"][target]["violation_count"] > 0, name
        failing = [{"id": case["id"], "failures": [r for r in case["relationships"] if r["kind"] == target and r["status"] == "PROGRAM_FAIL"]}
                   for case in report["cases"] if any(r["kind"] == target and r["status"] == "PROGRAM_FAIL" for r in case["relationships"])]
        summaries.append({"mutation": name, "source_sha256": report["source_sha256"], "status": report["status"],
            "target_semantic_oracle": target, "target_violation_count": report["relationship_coverage"][target]["violation_count"],
            "fingerprint_status": "PASS", "test_sha256": report["test_sha256"], "failing_cases": failing,
            "report": str((folder/"run/simulation_report.json").relative_to(ROOT)),
            "trace_sha256": digest(folder/"run/simulation_trace.csv")})
        print("SEMANTIC MUTANT REJECTED", name, target, flush=True)
    result = {"status": "PASS", "mutation_count": len(summaries), "mutations": summaries,
        "source_sha256": digest(ROOT/"source.fxil"), "test_sha256": digest(ROOT/"test_cases.json"),
        "policy": "Exact frozen suite reused; each mutant re-fingerprinted independently; target semantic oracle required to fail while fingerprint passes."}
    (EVIDENCE/"S3-semantic-mutations.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("replay", "mutations", "all"), default="all", nargs="?")
    args = parser.parse_args()
    if args.mode in ("all", "replay"):
        replay()
    if args.mode in ("all", "mutations"):
        mutations()
