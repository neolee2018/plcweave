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


def prepared(tmp_path, *, suite=SUITE):
    case = init_workflow("synthetic", workspace=tmp_path)
    (case / "requirements.md").write_text("# 需求\n启动保持，停止优先。", encoding="utf-8")
    (case / "design.md").write_text(DESIGN, encoding="utf-8")
    (case / "test_cases.md").write_text(suite, encoding="utf-8")
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


@pytest.mark.parametrize('mutation',[lambda s:s.replace('OR M0\n',''),lambda s:s.replace('ANI M101','AND M101')])
def test_failed_control_regression_is_never_delivered(tmp_path, mutation):
    case = prepared(tmp_path)
    (case / "source.fxil").write_text(mutation(CORE),encoding='utf-8')
    assert build_workflow(case, "B001", workspace=tmp_path)["status"] == "LOCAL_FAIL"
    with pytest.raises(ValueError, match="SIM_PASS"):
        deliver_workflow(case, "B001", "V001", workspace=tmp_path)


def test_nonzero_reset_is_shared_by_both_local_variants(tmp_path):
    case=prepared(tmp_path,suite=SUITE.replace('D1000=1;D1001=0','D1000=1',1))
    result=build_workflow(case,'B001',workspace=tmp_path)
    assert result['status']=='LOCAL_FAIL'
    assert result['variants']=={'hil':'PROGRAM_FAIL','production':'PROGRAM_FAIL'}


def test_changed_frozen_suite_changes_plc_fingerprint_with_same_core(tmp_path):
    one=prepared(tmp_path/'first')
    two=prepared(tmp_path/'second',suite=SUITE.replace('| 20 |','| 30 |'))
    build_workflow(one,'B001',workspace=tmp_path/'first')
    build_workflow(two,'B001',workspace=tmp_path/'second')
    first=json.loads((one/'build/B001/hil/identity.json').read_text(encoding='utf-8'))
    second=json.loads((two/'build/B001/hil/identity.json').read_text(encoding='utf-8'))
    assert first['canonical_sha256']==second['canonical_sha256']
    assert first['contract_sha256']!=second['contract_sha256']
    assert first['fingerprint_words']!=second['fingerprint_words']


def test_old_frozen_content_survives_user_edit_before_first_delivery(tmp_path):
    case=built(tmp_path)
    original=(case/'requirements.md').read_bytes()
    (case/'requirements.md').write_text('# 新需求\n增加LED。',encoding='utf-8')
    revision=revise_workflow(case,'V002',reason='LED',workspace=tmp_path)
    assert (case/'baseline/s1/requirements.md').read_bytes()==original
    assert (revision/'previous/requirements.md').read_bytes()==original
    diff=(revision/'requirement-diff.md').read_text(encoding='utf-8')
    assert '-启动保持，停止优先。' in diff and '+增加LED。' in diff
    assert (case/'build/B001/inputs/requirements.md').read_bytes()==original


def test_init_failure_removes_only_its_new_owned_project(tmp_path,monkeypatch):
    previous=init_workflow('existing',workspace=tmp_path)
    original=Path.write_text
    def fail(self,*args,**kwargs):
        if self.name=='design.md':raise OSError('synthetic disk failure')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',fail)
    with pytest.raises(OSError):init_workflow('new',workspace=tmp_path)
    assert not (tmp_path/'project/new').exists()
    assert previous.exists()


def test_hil_cancellation_saves_report_and_cleanup_before_reraising(tmp_path,monkeypatch):
    case=downloaded(tmp_path)
    class Interrupted(DummyBench):
        def sample(self,watch):
            self.calls=getattr(self,'calls',0)+1
            if self.calls==2:raise KeyboardInterrupt()
            return super().sample(watch)
    monkeypatch.setattr('plcweave.workflow.Bench',Interrupted)
    with pytest.raises(KeyboardInterrupt):run_test(case,tmp_path)
    report=json.loads((case/'evidence/hil/B001/T001/report.json').read_text(encoding='utf-8'))
    assert report['status']=='TEST_INFRA_ERROR' and report['error_type']=='KeyboardInterrupt'
    assert report['serial_closed'] is True and report['cleanup']=='CONFIRMED'
    assert report['trace_sha256']==digest(case/'evidence/hil/B001/T001/trace.jsonl')


def test_final_settled_read_crossing_deadline_cannot_pass(tmp_path,monkeypatch):
    case=downloaded(tmp_path)
    clock=[0.0]
    monkeypatch.setattr('plcweave.workflow.time.monotonic',lambda:clock[0])
    monkeypatch.setattr('plcweave.workflow.time.sleep',lambda duration:clock.__setitem__(0,clock[0]+duration))
    class SlowFinal(DummyBench):
        def sample(self,watch):
            self.calls=getattr(self,'calls',0)+1
            # reset + (during, settled) * five steps: last settled is read 11
            if self.calls==11:clock[0]+=1.0
            return super().sample(watch)
    monkeypatch.setattr('plcweave.workflow.Bench',SlowFinal)
    report=run_test(case,tmp_path,timeout_s=0.5)
    assert report['status']=='TEST_INFRA_ERROR' and report['error_type']=='TimeoutError'
    assert report['cleanup']=='CONFIRMED' and report['serial_closed']


@pytest.mark.parametrize('mode',['missing_input_echo','cleanup_failure','close_failure'])
def test_hil_cannot_pass_missing_consumption_or_unconfirmed_cleanup(tmp_path,monkeypatch,mode):
    case=downloaded(tmp_path)
    class Broken(DummyBench):
        def sample(self,watch):
            values=super().sample(watch)
            if mode=='missing_input_echo' and 'M100' in watch:values.pop('M100')
            if mode=='cleanup_failure' and len(self.writes)>=14:values['M0']=1
            return values
        def close(self):
            if mode=='close_failure':raise OSError('synthetic close failure')
            super().close()
    monkeypatch.setattr('plcweave.workflow.Bench',Broken)
    report=run_test(case,tmp_path)
    assert report['status']=='TEST_INFRA_ERROR'
    if mode=='close_failure':assert report['serial_closed'] is False
    else:assert report['serial_closed'] is True


def test_delivery_manifest_distinguishes_both_main_files(tmp_path):
    case=built(tmp_path)
    stage_reviews(case,1)
    result=deliver_workflow(case,'B001','V001',workspace=tmp_path)
    manifest=(result['folder']/'MANIFEST.md').read_text(encoding='utf-8')
    for variant in ('hil','production'):
        name=f'build/B001/{variant}/MAIN.csv'
        assert f'| {name} | {digest(result["folder"]/name)} |' in manifest


def test_publish_retries_transient_lock_without_overwriting(tmp_path,monkeypatch):
    from plcweave.projects import _publish
    source=tmp_path/'owned';source.mkdir()
    target=tmp_path/'version'
    original=Path.rename
    attempts=[]
    def locked(self,destination):
        attempts.append(self)
        if len(attempts)==1:raise PermissionError('synthetic transient file lock')
        return original(self,destination)
    monkeypatch.setattr(Path,'rename',locked)
    _publish(source,target)
    assert len(attempts)==2 and target.is_dir() and not source.exists()
    another=tmp_path/'another';another.mkdir()
    with pytest.raises(FileExistsError):_publish(another,target)
    assert another.is_dir() and target.is_dir()


@pytest.mark.parametrize('filename',['design-freeze.md','s1-freeze.md'])
def test_partial_freeze_failure_rolls_back_owned_files(tmp_path,monkeypatch,filename):
    case=init_workflow('freeze-error',workspace=tmp_path)
    (case/'design.md').write_text(DESIGN,encoding='utf-8')
    (case/'test_cases.md').write_text(SUITE,encoding='utf-8')
    reviews(case,'S1',_hashes(case,('requirements.md','test_cases.md','design.md')))
    original=Path.open
    class FailedWrite:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def write(self,value):
            self.stream.write(value[:10])
            raise OSError('synthetic partial freeze write')
        def __exit__(self,*args):self.stream.close()
    def fail(self,*args,**kwargs):
        stream=original(self,*args,**kwargs)
        return FailedWrite(stream) if self.name==filename and args and args[0]=='x' else stream
    monkeypatch.setattr(Path,'open',fail)
    with pytest.raises(OSError):freeze_workflow(case,workspace=tmp_path)
    assert not (case/'design-freeze.md').exists()
    assert not (case/'s1-freeze.md').exists()
    assert not (case/'baseline/s1').exists()
    assert (case/'requirements.md').exists() and (case/'reviews/S1').is_dir()


@pytest.mark.parametrize('name',['requirements.md','design.md','test_cases.md'])
def test_revision_rejects_corrupted_historical_md_before_creating_new_directory(tmp_path,name):
    case=built(tmp_path)
    (case/'requirements.md').write_text('# 用户新需求\n新增LED',encoding='utf-8')
    with (case/'baseline/s1'/name).open('a',encoding='utf-8') as stream:stream.write('\ncorrupted snapshot')
    with pytest.raises(ValueError,match='Old frozen snapshot'):
        revise_workflow(case,'V002',reason='LED',workspace=tmp_path)
    assert not (case/'revisions/V002').exists()


def test_requirement_diff_keeps_separate_lines_without_final_newline(tmp_path):
    case=built(tmp_path)
    (case/'requirements.md').write_text('# 需求\n新增LED',encoding='utf-8')
    revision=revise_workflow(case,'V002',reason='LED',workspace=tmp_path)
    diff=(revision/'requirement-diff.md').read_text(encoding='utf-8')
    assert '-启动保持，停止优先。\n+新增LED\n' in diff
