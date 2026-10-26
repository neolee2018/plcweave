import gxwlib
import json
import zipfile
from pathlib import Path

import pytest

from plcweave.demo import (confirm_bench, confirm_flash, deliver_demo, demo_status,
                           inspect_demo, serial_format, start_demo)
from plcweave.hil import Bench, load_bench_settings
from plcweave.markdown_suite import freeze_markdown
from plcweave.projects import create_project
from plcweave.testing import digest, frozen_suite, simulate


SETTINGS = {"port": "COM7", "baud": 9600, "parity": "N", "station": 1}


def ready_demo(tmp_path):
    project = start_demo("demo-test", workspace=tmp_path, settings=SETTINGS)["project"]
    report = simulate(project)
    assert report["status"] == "SIM_PASS"
    return project


def test_l01s_serial_format_matches_manual_examples():
    assert serial_format(baud=9600, parity="N") == 0xE081
    assert serial_format(baud=115200, parity="N") == 0xE0D1
    assert serial_format(baud=9600, parity="E") == 0xE087
    assert serial_format(baud=4800, parity="O", data_bits=7, stop_bits=2) == 0xE07A


def test_demo_start_freezes_markdown_before_source_and_builds_identity(tmp_path):
    result = start_demo("demo-custom", workspace=tmp_path,
                        settings={"port": "COM3", "baud": 19200, "parity": "E", "station": 7},
                        plc_connected=False)
    project = result["project"]
    assert (project / "s1-freeze.md").is_file()
    assert "MOV HE097 D8120" in (project / "source.fxil").read_text(encoding="utf-8")
    assert "MOV K7 D8121" in (project / "source.fxil").read_text(encoding="utf-8")
    suite = frozen_suite(project)
    assert suite["suite_version"] == "DEMO-V001"
    assert suite["cases"][0]["steps"][0]["expect"]["D8120"] == -8041
    identity = json.loads((project / "build_identity.json").read_text(encoding="utf-8"))
    assert identity["source_sha256"] == digest(project / "source.fxil")
    state = json.loads((project / "demo.json").read_text(encoding="utf-8"))
    assert state["plc_connected"] is False
    assert state["settings"]["station"] == 7
    assert not (project / "candidate/V001/MAIN.csv").exists()


def test_demo_start_rejects_invalid_bench_settings(tmp_path):
    for settings in ({"baud": 12345}, {"parity": "X"}, {"station": 0},
                     {"station": 248}, {"port": "COM0"}, {"port": "ttyS0"},
                     {"unknown": 1}):
        with pytest.raises(ValueError):
            start_demo("demo-bad", workspace=tmp_path, settings=settings)


def test_demo_start_refuses_reuse_and_leaves_no_partial_folder(tmp_path):
    start_demo("demo-once", workspace=tmp_path)
    with pytest.raises(FileExistsError):
        start_demo("demo-once", workspace=tmp_path)


def test_bench_config_is_validated_and_used_by_hil(tmp_path):
    project = create_project("bench-cfg", workspace=tmp_path)
    (project / "bench_config.json").write_text(json.dumps(
        {"port": "COM5", "baud": 19200, "parity": "E", "bytesize": 8,
         "stopbits": 1, "station": 5}), encoding="utf-8")
    settings = load_bench_settings(project)
    assert settings["station"] == 5 and settings["baud"] == 19200

    class Client:
        def __init__(self):
            self.device_ids = []

        def write_register(self, address, value, device_id):
            self.device_ids.append(device_id)
            class Reply:
                def isError(self):
                    return False
            return Reply()

        def close(self):
            pass

    client = Client()
    bench = Bench(client=client, settings=settings)
    bench.verified = True
    bench.write("D194", 7)
    assert client.device_ids == [5]

    (project / "bench_config.json").write_text(
        json.dumps({"port": "COM5", "baud": 12345, "parity": "E", "bytesize": 8,
                    "stopbits": 1, "station": 5}), encoding="utf-8")
    with pytest.raises(ValueError, match="baud"):
        load_bench_settings(project)


def test_confirm_flash_binds_hashes_and_requires_operator(tmp_path):
    project = ready_demo(tmp_path)
    with pytest.raises(ValueError):
        confirm_flash(project, operator=" ", software="GX Works2", compile_status="零错误",
                      run_state="RUN", workspace=tmp_path)
    record = confirm_flash(project, operator="测试员", software="GX Works2 1.77F",
                           compile_status="零错误", run_state="RUN",
                           note="隔离空机", workspace=tmp_path)
    stored = json.loads((project / "manual_download.json").read_text(encoding="utf-8"))
    assert stored == record
    assert record["source_sha256"] == digest(project / "source.fxil")
    assert record["test_sha256"] == digest(project / "test_cases.md")
    assert record["confirmed_by"] == "测试员"
    assert record["compile_status"] == "零错误"
    assert record["program_version"] == 1 and record["edition"] == 41
    with pytest.raises(FileExistsError):
        confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                      run_state="RUN", workspace=tmp_path)
    (project / "test_cases.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen"):
        confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                      run_state="RUN", force=True, workspace=tmp_path)


def test_offline_delivery_marks_s6_untested_and_packages_six_items(tmp_path):
    project = ready_demo(tmp_path)
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 60.0
    assert result["demo_ok"] is False
    names = zipfile.ZipFile(result["archive"]).namelist()
    for required in ("requirements.md", "test_cases.md", "MAIN.csv", "COMMENT.csv",
                     "HIL-REPORT.md", "SUMMARY.md", "MANIFEST.md"):
        assert any(name.endswith("/" + required) for name in names)
    hil = (result["folder"] / "HIL-REPORT.md").read_text(encoding="utf-8")
    assert "未执行" in hil
    summary = (result["folder"] / "SUMMARY.md").read_text(encoding="utf-8")
    assert "项目完成度：60.0%" in summary
    assert "未达到" in summary
    assert "R08" in summary and "未覆盖" not in summary
    with zipfile.ZipFile(result["archive"]) as archive:
        assert archive.testzip() is None


def test_delivery_with_sampled_hil_reports_demo_pass_but_not_formal(tmp_path):
    project = ready_demo(tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                  plc_running=True, workspace=tmp_path)
    suite = frozen_suite(project)
    identity = json.loads((project / "build_identity.json").read_text(encoding="utf-8"))
    cases = [{"id": case["id"], "status": "UNVERIFIED", "sampled_checks": "PASS",
              "reason": "polling"} for case in suite["cases"]]
    (project / "evidence").mkdir()
    (project / "evidence/hardware_report.json").write_text(json.dumps({
        "environment": "hardware_sampled", "status": "UNVERIFIED",
        "source_sha256": digest(project / "source.fxil"),
        "test_sha256": digest(project / "test_cases.md"),
        "identity": {"version": identity["program_version"], "edition": identity["edition"],
                     "fingerprint_words": identity["fingerprint_words"],
                     "suite": identity["suite_version_word"],
                     "heartbeat_before": 10, "heartbeat_after": 11},
        "cases": cases, "exit_state": {"M0": 0, "D154": 0, "D8050": 0, "D8051": 0},
        "cleanup": "stopped_output_disabled_and_read_back_zero", "serial_closed": True,
    }), encoding="utf-8")
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 100.0
    assert result["demo_ok"] is True
    assert result["formal_ok"] is False
    summary = (result["folder"] / "SUMMARY.md").read_text(encoding="utf-8")
    assert "达到演示验收要求" in summary
    assert "正式验收：**未评估**" in summary
    hil = (result["folder"] / "HIL-REPORT.md").read_text(encoding="utf-8")
    assert "抽样检查通过不等于正式 PASS" in hil


def test_hil_evidence_must_be_bound_and_hardware_shaped(tmp_path):
    project = ready_demo(tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                  plc_running=True, workspace=tmp_path)
    sim_report = project / "candidate/V001/simulation_report.json"
    with pytest.raises(ValueError, match="hardware_sampled"):
        deliver_demo(project, "V001", workspace=tmp_path, hil_report=sim_report)
    unbound = project / "evidence/unbound.json"
    unbound.parent.mkdir(exist_ok=True)
    unbound.write_text(json.dumps({"environment": "hardware_sampled", "cases": [
        {"id": "TC-001", "status": "PASS"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="bind"):
        deliver_demo(project, "V001", workspace=tmp_path, hil_report=unbound)


def test_empty_hil_error_report_does_not_block_offline_delivery(tmp_path):
    project = ready_demo(tmp_path)
    (project / "evidence").mkdir()
    (project / "evidence/hardware_report.json").write_text(json.dumps({
        "environment": "hardware_sampled", "status": "TEST_INFRA_ERROR",
        "source_sha256": digest(project / "source.fxil"),
        "test_sha256": digest(project / "test_cases.md"),
        "cases": [], "error": "port unavailable",
    }), encoding="utf-8")
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 60.0
    hil = (result["folder"] / "HIL-REPORT.md").read_text(encoding="utf-8")
    assert "无有效用例结果" in hil and "port unavailable" in hil


def test_unconfirmed_cleanup_blocks_demo_acceptance(tmp_path):
    project = ready_demo(tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                  plc_running=True, workspace=tmp_path)
    suite = frozen_suite(project)
    identity = json.loads((project / "build_identity.json").read_text(encoding="utf-8"))
    cases = [{"id": case["id"], "status": "UNVERIFIED", "sampled_checks": "PASS"}
             for case in suite["cases"]]
    (project / "evidence").mkdir()
    (project / "evidence/hardware_report.json").write_text(json.dumps({
        "environment": "hardware_sampled", "status": "UNVERIFIED",
        "source_sha256": digest(project / "source.fxil"),
        "test_sha256": digest(project / "test_cases.md"),
        "identity": {"version": identity["program_version"], "edition": identity["edition"],
                     "fingerprint_words": identity["fingerprint_words"],
                     "suite": identity["suite_version_word"]},
        "cases": cases, "exit_state": {"M0": 1, "D154": 1000, "D8050": 0, "D8051": 0},
        "cleanup": "restore_unconfirmed", "cleanup_error": "readback failed",
        "serial_closed": True,
    }), encoding="utf-8")
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 60.0
    assert result["demo_ok"] is False
    summary = (result["folder"] / "SUMMARY.md").read_text(encoding="utf-8")
    assert "清理未确认" in summary
    hil = (result["folder"] / "HIL-REPORT.md").read_text(encoding="utf-8")
    assert "restore_unconfirmed" in hil


def test_non_default_data_and_stop_bits_are_rendered_everywhere(tmp_path):
    project = start_demo("demo-72", workspace=tmp_path,
                         settings={"port": "COM3", "baud": 4800, "parity": "E",
                                   "bytesize": 7, "stopbits": 2, "station": 2})["project"]
    assert "7 数据位/2 停止位" in (project / "requirements.md").read_text(encoding="utf-8")
    assert "4800/7/E/2" in (project / "source.fxil").read_text(encoding="utf-8")


def test_status_after_offline_delivery_does_not_push_flashing(tmp_path, capsys):
    project = ready_demo(tmp_path)
    deliver_demo(project, "V001", workspace=tmp_path)
    demo_status(project, workspace=tmp_path)
    output = capsys.readouterr().out
    assert "已生成交付 ZIP" in output
    assert "demo confirm-flash" not in output


def test_demo_cases_have_no_hil_skip_initial_words(tmp_path):
    project = ready_demo(tmp_path)
    suite = frozen_suite(project)
    assert all(case["initial_words"] == {} for case in suite["cases"])


def test_hil_demo_cases_are_executed_with_a_dummy_bench(tmp_path, monkeypatch):
    from plcweave import hil
    project = ready_demo(tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                  plc_running=True, workspace=tmp_path)

    class Dummy:
        def __init__(self):
            self.writes = []
            self.verified = True

        def verify(self):
            return {"version": 1, "edition": 41}

        def write(self, name, value):
            self.writes.append((name, value))

        def sample(self, watch):
            return {name: 0 for name in watch}

        def close(self):
            pass

    dummy = Dummy()
    clock = [0.0]

    def tick():
        clock[0] += 0.25
        return clock[0]

    monkeypatch.setattr(hil, "candidate_bench", lambda directory: dummy)
    monkeypatch.setattr(hil.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(hil.time, "monotonic", tick)
    report = hil.run(project, isolated_bench=True)
    assert len(report["cases"]) == 8
    assert all(case.get("sampled_checks") in {"PASS", "FAIL"} for case in report["cases"])
    assert dummy.writes


def test_hil_demo_gate_requires_bench_readiness(tmp_path):
    from plcweave.hil import run
    project = ready_demo(tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    with pytest.raises(ValueError, match="bench_ready"):
        run(project, isolated_bench=True)


def test_status_blocks_flash_after_failed_simulation(tmp_path, capsys):
    project = ready_demo(tmp_path)
    report_path = project / "candidate/V001/simulation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "PROGRAM_FAIL"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    demo_status(project, workspace=tmp_path)
    output = capsys.readouterr().out
    assert "SIM" in output or "PROGRAM_FAIL" in output
    assert "不要烧录" in output
    assert "demo confirm-flash" not in output


def _write_hil(project, *, status="UNVERIFIED", cases=None, cleanup="stopped_output_disabled_and_read_back_zero",
               exit_state=None, serial_closed=True, identity=None):
    from plcweave.testing import frozen_suite as _suite
    suite = _suite(project)
    identity = identity or json.loads((project / "build_identity.json").read_text(encoding="utf-8"))
    cases = cases if cases is not None else [
        {"id": case["id"], "status": "UNVERIFIED", "sampled_checks": "PASS"} for case in suite["cases"]]
    (project / "evidence").mkdir(exist_ok=True)
    (project / "evidence/hardware_report.json").write_text(json.dumps({
        "environment": "hardware_sampled", "status": status,
        "source_sha256": digest(project / "source.fxil"),
        "test_sha256": digest(project / "test_cases.md"),
        "identity": {"version": identity["program_version"], "edition": identity["edition"],
                     "fingerprint_words": identity["fingerprint_words"],
                     "suite": identity["suite_version_word"]},
        "cases": cases,
        "exit_state": exit_state or {"M0": 0, "D154": 0, "D8050": 0, "D8051": 0},
        "cleanup": cleanup, "serial_closed": serial_closed,
    }), encoding="utf-8")


def _confirmed(project, tmp_path):
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                  plc_running=True, workspace=tmp_path)


def test_test_infra_error_with_pass_cases_is_not_acceptance(tmp_path):
    project = ready_demo(tmp_path)
    _confirmed(project, tmp_path)
    _write_hil(project, status="TEST_INFRA_ERROR")
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 60.0
    assert result["demo_ok"] is False
    hil = (result["folder"] / "HIL-REPORT.md").read_text(encoding="utf-8")
    assert "报告存在但未计入" in hil


def test_tampered_main_csv_after_confirmation_is_not_counted(tmp_path):
    project = ready_demo(tmp_path)
    _confirmed(project, tmp_path)
    (project / "candidate/V001/MAIN.csv").write_bytes(b"tampered")
    result = deliver_demo(project, "V001", workspace=tmp_path)
    assert result["completion"] == 60.0
    assert result["demo_ok"] is False
    summary = (result["folder"] / "SUMMARY.md").read_text(encoding="utf-8")
    assert "烧录确认：未记录" in summary


def test_generated_csv_uses_gx_works2_list_dialect(tmp_path):
    project = ready_demo(tmp_path)
    program = gxwlib.load_csv(project / "candidate/V001/MAIN.csv", device_profile="fx")
    assert program.instructions
    assert b"\r\x00\n\x00" in (project / "candidate/V001/MAIN.csv").read_bytes()
    assert b"\r\x00\n\x00" in (project / "candidate/V001/COMMENT.csv").read_bytes()


def test_candidate_bench_binds_demo_identity_and_bench_settings(tmp_path, monkeypatch):
    from plcweave import hil
    project = start_demo("demo-bench", workspace=tmp_path,
                         settings={"port": "COM4", "baud": 9600, "parity": "N", "station": 3})["project"]
    captured = {}

    class Dummy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(hil, "Bench", Dummy)
    hil.candidate_bench(project)
    assert captured["settings"]["station"] == 3
    assert captured["expected_identity"] == (1, 41)
    assert captured["expected_suite"] == 1
    assert len(captured["expected_fingerprint"]) == 2


def test_delivery_rejects_hil_report_outside_project(tmp_path):
    project = ready_demo(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"status": "UNVERIFIED", "cases": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="inside this project"):
        deliver_demo(project, "V001", workspace=tmp_path, hil_report=outside)


def test_delivery_refuses_non_pass_simulation_and_existing_version(tmp_path):
    project = ready_demo(tmp_path)
    report_path = project / "candidate/V001/simulation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "PROGRAM_FAIL"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="SIM_PASS"):
        deliver_demo(project, "V001", workspace=tmp_path)
    report["status"] = "SIM_PASS"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    deliver_demo(project, "V001", workspace=tmp_path)
    with pytest.raises(FileExistsError):
        deliver_demo(project, "V001", workspace=tmp_path)


def test_inspection_tracks_the_demo_gates(tmp_path):
    project = ready_demo(tmp_path)
    info = inspect_demo(project, workspace=tmp_path)
    assert info["frozen"] and info["source"] and info["instruction_csv"]
    assert info["simulation"]["status"] == "SIM_PASS"
    assert info["flashed"] is False
    assert info["bench_ready"] is False
    assert info["hardware"] is None
    assert info["deliveries"] == []


def test_confirm_bench_requires_flash_and_explicit_wiring(tmp_path):
    project = ready_demo(tmp_path)
    with pytest.raises(ValueError, match="Flash"):
        confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                      plc_running=True, workspace=tmp_path)
    confirm_flash(project, operator="测试员", software="GX Works2", compile_status="零错误",
                  run_state="RUN", workspace=tmp_path)
    with pytest.raises(ValueError, match="isolated bench"):
        confirm_bench(project, operator="测试员", isolated_bench=False, rs485_connected=True,
                      plc_running=True, workspace=tmp_path)
    record = confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                           plc_running=True, workspace=tmp_path)
    assert record["rs485_connected"] is True and record["plc_running"] is True
    assert json.loads((project / "bench_ready.json").read_text(encoding="utf-8")) == record
    with pytest.raises(FileExistsError):
        confirm_bench(project, operator="测试员", isolated_bench=True, rs485_connected=True,
                      plc_running=True, workspace=tmp_path)


def test_demo_requires_freeze_before_source(tmp_path):
    project = create_project("late", workspace=tmp_path)
    (project / "source.fxil").write_text("END\n", encoding="utf-8")
    (project / "test_cases.md").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        freeze_markdown(project)
