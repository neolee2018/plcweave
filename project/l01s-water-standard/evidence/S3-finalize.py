"""Bind final independent validation evidence; no PLC/device operations."""
import json
from datetime import datetime, timezone
from pathlib import Path
from plcweave.testing import digest, frozen_suite
from plcweave.validation import independent_fingerprint

root = Path(__file__).resolve().parents[1]
workspace = root.parents[1]
evidence = root/"evidence"
suite = frozen_suite(root)
report_path = evidence/"simulation/latest/simulation_report.json"
report = json.loads(report_path.read_text())
review = json.loads((evidence/"S3-full-trace-review.json").read_text())
mutations = json.loads((evidence/"S3-semantic-mutations.json").read_text())
identity = json.loads((root/"build_identity.json").read_text())
fingerprint = independent_fingerprint(root/"source.fxil")
source_hash, test_hash = digest(root/"source.fxil"), digest(root/"test_cases.json")
validator_hash = digest(workspace/"src/plcweave/validation.py")
assert report["status"] == "SIM_PASS" and len(report["cases"]) == 55
assert all(case["status"] == "PASS" for case in report["cases"])
assert report["source_sha256"] == review["source_sha256"] == mutations["source_sha256"] == identity["source_sha256"] == source_hash
assert report["test_sha256"] == review["test_sha256"] == mutations["test_sha256"] == test_hash
assert report["comparator_sha256"] == validator_hash
assert fingerprint["canonical_sha256"] == identity["canonical_sha256"]
assert fingerprint["fingerprint_words"] == identity["fingerprint_words"]
assert (identity["program_version"], identity["edition"], identity["suite_version_word"]) == (2, 31, 2)
assert review["status"] == "PASS" and review["total_rows"] == 92996
assert review["trace_sha256"] == digest(evidence/"simulation/latest/simulation_trace.csv")
assert mutations["status"] == "PASS" and mutations["mutation_count"] == 7
for mutant in mutations["mutations"]:
    mutation_report = json.loads((root/mutant["report"]).read_text())
    assert mutation_report["comparator_sha256"] == validator_hash
    assert mutant["status"] == "PROGRAM_FAIL" and mutant["fingerprint_status"] == "PASS"
    assert mutant["target_violation_count"] > 0 and mutant["test_sha256"] == test_hash
assert "40 passed" in (evidence/"S3-infrastructure-tests.txt").read_text()
assert "[SUCCESS]" in (evidence/"S3-platformio-simulate.txt").read_text()
assert not (evidence/"s3-pytest-tmp").exists()
artifacts = [report_path, evidence/"simulation/latest/simulation_trace.csv",
    evidence/"S3-full-trace-review.json", evidence/"S3-semantic-mutations.json",
    evidence/"S3-infrastructure-tests.txt", evidence/"S3-final-cli.txt",
    evidence/"S3-platformio-simulate.txt", evidence/"S3-static-validation.txt",
    evidence/"S3-validation-review.md", evidence/"S3-verify.py"]
result = {
    "status": "PASS", "task_id": "PW-20261022-STANDARD-REDO", "owner": "/root/s3_verifier",
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "program_version": "V002", "suite_version": suite["suite_version"],
    "source_sha256": source_hash, "test_sha256": test_hash,
    "requirements_sha256": digest(root/"requirements.md"),
    "validator_sha256": validator_hash,
    "runner_sha256": digest(workspace/"src/plcweave/testing.py"),
    "engine_binary_sha256": report["engine_binary_sha256"],
    "independence": "S3 separate verifier; S1 frozen before S2; historical program/tests excluded; no frozen expected results changed",
    "levels": {"static": "STATIC_PASS", "simulation": "SIM_PASS", "gx": "NOT_EXECUTED", "hardware": "NOT_EXECUTED"},
    "static": {"main_errors": 0, "main_warnings": 0, "comment_errors": 0,
        "comment_nonblocking_advisories": 1, "advisory_reason": "Seven implicit arithmetic result words and three intentionally unused ADC channels retain comments"},
    "simulation": {"must_cases": 55, "passed_cases": 55, "postscan_rows": 92996,
        "independent_full_csv_replay": "PASS", "relationship_kind_count": 10,
        "relationship_coverage": report["relationship_coverage"],
        "first_full_frequency_ms": report["cases"][28]["metrics"]["first_full_frequency_elapsed_ms"]},
    "fingerprint": {"status": "PASS", **fingerprint, "manifest_independently_matched": True},
    "execution_tool_negative_gates": report["engine_gate"],
    "semantic_mutations": {"status": "PASS", "rejected": 7, "identity_passed_for_all": True,
        "oracles": [{"name": m["mutation"], "target": m["target_semantic_oracle"], "violations": m["target_violation_count"]} for m in mutations["mutations"]]},
    "repository_regression": {"passed": 40, "failed": 0, "legacy_schema_simulation_covered": True},
    "upstream_baseline": {"status": "KNOWN_BASELINE_FAILURES_NOT_CLAIMED_GREEN", "failed": 5, "passed": 92, "skipped": 2,
        "evidence": "evidence/baseline-full-regression.txt", "expectations_modified": False,
        "scope": "Legacy parser/render/diff unsupported-form assumptions, supported instruction count and words/get_word stub mismatch"},
    "limits": ["No GX manufacturer validation", "No electrical AO/pressure dynamics validation",
        "No physical peripheral protocol validation", "No power-loss retention validation",
        "Rich-suite S6 adapter remains unqualified; legacy endpoint runner rejects this schema",
        "A new manual download must bind this source/suite/identity before authorized bench replay"],
    "cleanup": {"pytest_temporary_directory": "removed_and_absence_verified", "subprocesses": "all_bounded_and_completed",
        "serial_connections_opened": 0, "gui_sessions_created": 0, "persistent_helpers_created": 0,
        "retained": "Business evidence and intentional mutation fixtures"},
    "artifacts": {str(path.relative_to(root)): digest(path) for path in artifacts},
}
(evidence/"S3-final-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"status": result["status"], "source_sha256": source_hash, "test_sha256": test_hash, "cases": 55, "rows": 92996, "semantic_mutants_rejected": 7}))
