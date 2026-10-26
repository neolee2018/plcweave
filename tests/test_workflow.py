"""Synthetic engineering fixtures; never represent real PLC/reviewer evidence."""
import json
import zipfile
from pathlib import Path

import pytest

from plcweave.testing import digest
from plcweave.workflow import (INPUT_FILES, _hashes, build_workflow, confirm_download,
                               deliver_workflow, freeze_workflow, init_workflow,
                               revise_workflow, run_hil, status_workflow, validate_build)

DESIGN = """# 控制设计

## PLCWeave
| key | value |
| --- | --- |
| target | l01s |
| protocol | l01s-modbus-rtu |
| program_version | 1 |
| edition | 51 |
| suite_word | 1 |
| reset_ms | 10 |

## Inputs
| logical | physical | injection |
| --- | --- | --- |
| M100 | X0 | D1000 |
| M101 | X1 | D1001 |

## Outputs
| logical | physical |
| --- | --- |
| M0 | Y0 |

## HIL reset
| device | value |
| --- | --- |
| D1000 | 0 |
| D1001 | 1 |

## Reset expectations
| device | value |
| --- | --- |
| M0 | 0 |

## HIL cleanup
| device | value |
| --- | --- |
| D1000 | 0 |
| D1001 | 1 |

## Cleanup expectations
| device | value |
| --- | --- |
| M0 | 0 |
"""

SUITE = """# 独立预期

## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0 |

## Invariants
| device | expected |
| --- | --- |

## TC-001: 启停
### Metadata
| key | value |
| --- | --- |
| hardware_scope | steady_state |
### Initial
| device | value |
| --- | --- |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | D1000=1;D1001=0 | - | M0=1 | 启动 |
| 20 | D1000=0;D1001=0 | - | M0=1 | 释放启动后保持 |
| 20 | D1000=1;D1001=1 | - | M0=0 | 同时按下停止优先 |
| 20 | D1000=0;D1001=1 | - | M0=0 | 停止 |
| 20 | D1000=0;D1001=0 | - | M0=0 | 保持停止 |
"""

CORE = """#meta
project: synthetic-start-stop
#instructions
LD M100
OR M0
ANI M101
OUT M0
END
#comments
M0 Run latch
"""


def reviews(case, node, bindings, *, count=4):
    """Synthetic records solely to exercise tool gates inside pytest fixtures."""
    folder = case / f"reviews/{node}"
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (folder / f"{index}.json").write_text(json.dumps({
            "reviewer_id": f"pytest-synthetic-reviewer-{index}", "independent": True,
            "verdict": "PASS", "checks": ["Synthetic fixture; not an actual independent review"],
            "input_sha256": bindings, "blocking_findings": [],
        }), encoding="utf-8")


def prepared(tmp_path):
    case = init_workflow("synthetic", workspace=tmp_path)
    (case / "requirements.md").write_text("# 需求\n启动保持，停止优先。", encoding="utf-8")
    (case / "design.md").write_text(DESIGN, encoding="utf-8")
    (case / "test_cases.md").write_text(SUITE, encoding="utf-8")
    reviews(case, "S1", _hashes(case, ("requirements.md", "test_cases.md", "design.md")))
    freeze_workflow(case, workspace=tmp_path)
    (case / "source.fxil").write_text(CORE, encoding="utf-8")
    return case


def built(tmp_path):
    case = prepared(tmp_path)
    result = build_workflow(case, "B001", workspace=tmp_path)
    assert result["status"] == "LOCAL_PASS"
    return case


def downloaded(tmp_path):
    case = built(tmp_path)
    confirm_download(case, "B001", operator="pytest fixture", software="GX Works2 fixture",
                     compiled=True, running=True, workspace=tmp_path)
    return case


def test_init_is_md_only_and_source_waits_for_freeze(tmp_path):
    case = init_workflow("draft", workspace=tmp_path)
    assert {p.suffix for p in case.iterdir()} == {".md"}
    with pytest.raises(ValueError):
        freeze_workflow(case, workspace=tmp_path)
    assert not (case / "source.fxil").exists()
    assert not (case / "s1-freeze.md").exists()


def test_two_actual_programs_share_core_and_formal_program_has_no_test_interface(tmp_path):
    case = built(tmp_path)
    hil = (case / "build/B001/hil/source.fxil").read_text(encoding="utf-8")
    production = (case / "build/B001/production/source.fxil").read_text(encoding="utf-8")
    core = lambda value: value.split("// BEGIN_CONTROL_CORE\n")[1].split("// END_CONTROL_CORE")[0]
    assert core(hil) == core(production)
    assert "D1000" in hil and "D196" in hil and "D8120" in hil
    assert "D1000" not in production and "D196" not in production and "D8120" not in production
    assert "LD X0" in production and "OUT Y0" in production
    assert "OUT Y0" not in hil
    for variant in ("hil", "production"):
        report = json.loads((case / f"build/B001/{variant}/simulation_report.json").read_text())
        assert report["status"] == "SIM_PASS"
        assert report["cases"][0]["status"] == "PASS"
    with pytest.raises(FileExistsError):
        build_workflow(case, "B001", workspace=tmp_path)


@pytest.mark.parametrize("name", ["requirements.md", "design.md", "test_cases.md", "source.fxil"])
def test_changed_input_invalidates_old_build_and_cannot_unlock_serial(tmp_path, monkeypatch, name):
    case = downloaded(tmp_path)
    with (case / name).open("a", encoding="utf-8") as stream:
        stream.write("\n// changed\n")
    monkeypatch.setattr("plcweave.workflow.Bench", lambda **kw: pytest.fail("Opened serial"))
    with pytest.raises(ValueError):
        run_hil(case, "B001", "T001", port="COM1", isolated_bench=True, running=True, connected=True, workspace=tmp_path)


def test_build_blocks_hardware_outputs_in_common_core_and_unknown_targets(tmp_path):
    case = prepared(tmp_path)
    (case / "source.fxil").write_text(CORE.replace("OUT M0", "OUT Y0"))
    with pytest.raises(ValueError):
        build_workflow(case, "B001", workspace=tmp_path)
    assert not (case / "build/B001").exists()
    assert not list((case / "build").glob(".build-*"))
    from plcweave.variants import read_design
    (case / "design.md").write_text(DESIGN.replace("l01s |", "delta |"), encoding="utf-8")
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        read_design(case / "design.md")


def test_four_distinct_version_bound_reviewers_are_required(tmp_path):
    case = init_workflow("review", workspace=tmp_path)
    (case / "design.md").write_text(DESIGN, encoding="utf-8")
    (case / "test_cases.md").write_text(SUITE, encoding="utf-8")
    bindings = _hashes(case, ("requirements.md", "test_cases.md", "design.md"))
    reviews(case, "S1", bindings, count=3)
    with pytest.raises(ValueError, match="four"):
        freeze_workflow(case, workspace=tmp_path)
    assert not (case / "s1-freeze.md").exists()
    reviews(case, "S1", bindings)
    (case / "requirements.md").write_text("changed")
    with pytest.raises(ValueError, match="Stale"):
        freeze_workflow(case, workspace=tmp_path)


def test_both_versions_receive_control_fix_and_old_download_does_not_transfer(tmp_path):
    case = downloaded(tmp_path)
    with (case / "source.fxil").open("a", encoding="utf-8") as stream:
        stream.write("M1 new comment\n")
    build_workflow(case, "B002", workspace=tmp_path)
    with pytest.raises(FileNotFoundError):
        run_hil(case, "B002", "T001", port="COM1", workspace=tmp_path)
    assert (case / "build/B001/hil/MAIN.csv").is_file()


def test_requirements_revision_preserves_old_delivery_and_starts_unfrozen(tmp_path):
    case = built(tmp_path)
    before = (case / "build/B001/BUILD.json").read_bytes()
    with (case / "requirements.md").open("a", encoding="utf-8") as stream:
        stream.write("\n增加运行LED。")
    assert status_workflow(case, "B001", workspace=tmp_path)["state"] == "NEEDS_REVISION"
    revision = revise_workflow(case, "V002", reason="增加LED", workspace=tmp_path)
    assert "LED" in (revision / "requirements.md").read_text(encoding="utf-8")
    assert not (revision / "source.fxil").exists()
    assert not (revision / "s1-freeze.md").exists()
    assert (case / "build/B001/BUILD.json").read_bytes() == before
    with pytest.raises(FileExistsError):
        revise_workflow(case, "V002", reason="retry", workspace=tmp_path)


def stage_reviews(case, stage, batch=None):
    bindings = _hashes(case, INPUT_FILES)
    bindings["build/B001/BUILD.json"] = digest(case / "build/B001/BUILD.json")
    if batch:
        for filename in ("report.json", "trace.jsonl"):
            name = f"evidence/hil/B001/{batch}/{filename}"
            bindings[name] = digest(case / name)
    reviews(case, f"stage{stage}-B001", bindings)


def test_stage_one_zip_contains_four_categories_two_programs_and_no_hardware_claim(tmp_path):
    case = built(tmp_path)
    stage_reviews(case, 1)
    result = deliver_workflow(case, "B001", "V001-stage1", workspace=tmp_path)
    assert result["hardware"] == "NOT_EXECUTED"
    assert result["production_hardware"] == "UNVERIFIED"
    with zipfile.ZipFile(result["archive"]) as archive:
        names = {"/".join(Path(n).parts[1:]) for n in archive.namelist()}
        assert {"requirements.md", "design.md", "test_cases.md", "build/B001/hil/MAIN.csv", "build/B001/production/MAIN.csv",
                "build/B001/hil/instruction_list.md", "build/B001/production/instruction_list.md", "SUMMARY.md", "MANIFEST.md"} <= names
        assert archive.testzip() is None
        extracted = tmp_path / "project/extracted"
        archive.extractall(extracted)
    validate_build(next(extracted.iterdir()), "B001", workspace=tmp_path)
    with pytest.raises(FileExistsError):
        deliver_workflow(case, "B001", "V001-stage1", workspace=tmp_path)


class DummyBench:
    """Tiny synthetic latch used only to exercise the real HIL orchestrator."""
    instances = []
    mode = "good"

    def __init__(self, **kwargs):
        self.values = {"D1000": 0, "D1001": 1}
        self.state = 0
        self.closed = False
        self.verified = False
        self.writes = []
        self.instances.append(self)

    def verify(self):
        if self.mode == "identity_error":
            raise ValueError("Wrong identity")
        self.verified = True
        return {"version": 1}

    def write(self, key, value):
        self.values[key] = value
        self.writes.append((key, value))

    def sample(self, watch):
        start, stop = self.values["D1000"], self.values["D1001"]
        self.state = int(bool(start or self.state) and not stop)
        if self.mode == "comms_error":
            raise ConnectionError("Missing response")
        if self.mode == "bad_program" and start and not stop:
            self.state = 0
        values = {"M0": self.state, "M100": start, "M101": stop}
        return {key: values.get(key, 0) for key in watch}

    def close(self):
        self.closed = True


def dummy(monkeypatch, mode="good"):
    DummyBench.instances = []
    monkeypatch.setattr(DummyBench, "mode", mode)
    monkeypatch.setattr("plcweave.workflow.Bench", DummyBench)


def run_test(case, tmp_path, **kwargs):
    return run_hil(case, "B001", "T001", port="COM1", isolated_bench=True,
                   running=True, connected=True, workspace=tmp_path, **kwargs)


def test_hil_requires_manual_download_and_explicit_bench_conditions(tmp_path, monkeypatch):
    case = built(tmp_path)
    monkeypatch.setattr("plcweave.workflow.Bench", lambda **kw: pytest.fail("Opened serial"))
    with pytest.raises(FileNotFoundError):
        run_test(case, tmp_path)
    with pytest.raises(ValueError):
        confirm_download(case, "B001", operator="name", software="GX Works2", compiled=False, running=True, workspace=tmp_path)
    confirm_download(case, "B001", operator="name", software="GX Works2", compiled=True, running=True, workspace=tmp_path)
    with pytest.raises(ValueError, match="isolated"):
        run_hil(case, "B001", "T001", port="COM1", workspace=tmp_path)


@pytest.mark.parametrize("mode, expected", [("good", "PASS"), ("bad_program", "PROGRAM_FAIL"),
                                          ("comms_error", "TEST_INFRA_ERROR"), ("identity_error", "TEST_INFRA_ERROR")])
def test_hil_collects_raw_values_compares_and_always_closes(tmp_path, monkeypatch, mode, expected):
    case = downloaded(tmp_path)
    dummy(monkeypatch, mode)
    result = run_test(case, tmp_path)
    assert result["status"] == expected
    assert result["serial_closed"] is True and DummyBench.instances[0].closed
    trace = case / "evidence/hil/B001/T001/trace.jsonl"
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    assert rows
    if mode == "identity_error":
        assert not DummyBench.instances[0].writes
    if mode == "good":
        assert any(row["kind"] == "sample" and row["values"]["M0"] == 1 for row in rows)
        stage_reviews(case, 2, "T001")
        result = deliver_workflow(case, "B001", "V001-stage2", stage=2, batch="T001", workspace=tmp_path)
        assert result["hardware"].startswith("PASS")
        assert result["production_hardware"] == "UNVERIFIED"
    else:
        with pytest.raises(ValueError):
            deliver_workflow(case, "B001", "V001-stage2", stage=2, batch="T001", workspace=tmp_path)


def test_polling_does_not_upgrade_continuous_invariants(tmp_path, monkeypatch):
    case = init_workflow("continuous", workspace=tmp_path)
    (case / "requirements.md").write_text("steady and continuous invariant", encoding="utf-8")
    (case / "design.md").write_text(DESIGN, encoding="utf-8")
    (case / "test_cases.md").write_text(SUITE.replace("| - | M0=1 |", "| M0=0..1 | M0=1 |"), encoding="utf-8")
    reviews(case, "S1", _hashes(case, ("requirements.md", "test_cases.md", "design.md")))
    freeze_workflow(case, workspace=tmp_path)
    (case / "source.fxil").write_text(CORE)
    assert build_workflow(case, "B001", workspace=tmp_path)["status"] == "LOCAL_PASS"
    confirm_download(case, "B001", operator="pytest", software="fixture", compiled=True, running=True, workspace=tmp_path)
    dummy(monkeypatch)
    assert run_test(case, tmp_path)["status"] == "UNVERIFIED"


def test_tampered_artifact_is_blocked_before_download(tmp_path):
    case = built(tmp_path)
    (case / "build/B001/hil/MAIN.csv").write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact changed"):
        validate_build(case, "B001", workspace=tmp_path)


def test_failed_control_regression_is_never_delivered(tmp_path):
    case = prepared(tmp_path)
    (case / "source.fxil").write_text(CORE.replace("OR M0\n", ""))
    # A pure start/stop fixture does not test hold yet: add a deliberate wrong output.
    (case / "source.fxil").write_text(CORE.replace("ANI M101", "AND M101"))
    assert build_workflow(case, "B001", workspace=tmp_path)["status"] == "LOCAL_FAIL"
    with pytest.raises(ValueError, match="SIM_PASS"):
        deliver_workflow(case, "B001", "V001", workspace=tmp_path)
