"""Guided, one-prompt demo from requirements to a checked delivery ZIP.

The demo is deliberately small: it proves the workflow, not a production control
function. Hardware access stays gated by an explicit operator flash confirmation,
and the S6 report keeps polling limits as UNVERIFIED.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .fx import parse_fxil
from .hil import DEFAULT_BENCH, load_bench_settings, validate_bench_settings
from .markdown_suite import freeze_markdown
from .projects import _location, create_project, package_delivery
from .testing import digest, frozen_suite, suite_path
from .validation import independent_fingerprint, signed16

SCENARIO_VERSION = "DEMO-V001"
BAUD_CODES = {600: 4, 1200: 5, 2400: 6, 4800: 7, 9600: 8, 19200: 9, 38400: 10, 57600: 11, 115200: 13}
PARITY_CODES = {"N": 0, "O": 1, "E": 3}
MUST = "MUST"


def scenario_directory():
    root = Path(__file__).resolve().parents[2]
    path = root / "demo" / "scenario"
    if not path.is_dir():
        raise ValueError("Demo scenario is missing; run from a complete source checkout")
    return path


def serial_format(*, baud, parity, data_bits=8, stop_bits=1, ascii_mode=False):
    """L01S D8120 image for Modbus RTU/ASCII (manual 8.2.3)."""
    if type(baud) is not int or baud not in BAUD_CODES:
        raise ValueError(f"Unsupported baud rate: {baud}")
    parity = str(parity).upper()
    if parity not in PARITY_CODES:
        raise ValueError("Parity must be N, E or O")
    if data_bits not in {7, 8}:
        raise ValueError("Data bits must be 7 or 8")
    if stop_bits not in {1, 2}:
        raise ValueError("Stop bits must be 1 or 2")
    return (0xE000 | (0x1000 if ascii_mode else 0) | (BAUD_CODES[baud] << 4)
            | (8 if stop_bits == 2 else 0) | (PARITY_CODES[parity] << 1)
            | (1 if data_bits == 8 else 0))


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _readable_time():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _render(text, values):
    def replace(match):
        key = match.group(1)
        if key not in values:
            raise ValueError(f"Unknown demo placeholder: {key}")
        return str(values[key])
    rendered = re.sub(r"\{\{([A-Z0-9_]+)\}\}", replace, text)
    if "{{" in rendered:
        raise ValueError("Unresolved demo placeholder")
    return rendered


def _update_state(case, stage, **extra):
    path = case / "demo.json"
    if not path.exists():
        return
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        state.setdefault("stages", {})[stage] = _timestamp()
        state.update(extra)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        # State is advisory; never turn a completed package into a failure.
        return


def start_demo(name, *, workspace=None, directory=None, settings=None, plc_connected=True):
    """Create a frozen demo project, then add source and build identity."""
    workspace = Path(workspace or Path.cwd()).resolve()
    settings = validate_bench_settings({**DEFAULT_BENCH, **(settings or {})})
    scenario = scenario_directory()
    path = create_project(name, workspace=workspace, directory=directory)
    try:
        d8120 = serial_format(baud=settings["baud"], parity=settings["parity"],
                              data_bits=settings["bytesize"], stop_bits=settings["stopbits"])
        values = {
            "PROJECT_NAME": name,
            "PORT": settings["port"],
            "BAUD": settings["baud"],
            "PARITY": settings["parity"],
            "DATA_BITS": settings["bytesize"],
            "STOP_BITS": settings["stopbits"],
            "STATION": settings["station"],
            "D8120_HEX": f"H{d8120:04X}",
            "D8120_SIGNED": signed16(d8120),
        }
        for filename in ("requirements.md", "test_cases.md"):
            (path / filename).write_text(
                _render((scenario / filename).read_text(encoding="utf-8"), values),
                encoding="utf-8")
        # Initial freeze must precede the PLC source, exactly as in a customer project.
        freeze_markdown(path)
        source = _render((scenario / "source.fxil.template").read_text(encoding="utf-8"), values)
        (path / "source.fxil").write_text(source, encoding="utf-8", newline="\n")
        fingerprint = independent_fingerprint(path / "source.fxil")
        for address, word in zip((200, 201), fingerprint["fingerprint_words"]):
            source, count = re.subn(rf"(?m)^MOV K-?\d+ D{address}$", f"MOV K{word} D{address}", source)
            if count != 1:
                raise ValueError(f"Demo template must contain one identity MOV for D{address}")
        (path / "source.fxil").write_text(source, encoding="utf-8", newline="\n")
        fingerprint = independent_fingerprint(path / "source.fxil")
        identity = {
            "source_sha256": digest(path / "source.fxil"),
            "program_version": 1,
            "edition": 41,
            "suite_version_word": 1,
            "demo": True,
            "fingerprint_words": fingerprint["fingerprint_words"],
            "canonical_sha256": fingerprint["canonical_sha256"],
        }
        (path / "build_identity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
        (path / "bench_config.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        state = {
            "scenario": "start-stop-delay",
            "scenario_version": SCENARIO_VERSION,
            "project": name,
            "created_at": _timestamp(),
            "plc_connected": bool(plc_connected),
            "settings": settings,
            "d8120": d8120,
            "stages": {"D2_program_ready": _timestamp()},
        }
        (path / "demo.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (path / "README.md").write_text(
            f"""# {name}

PLCWeave 演示项目（{SCENARIO_VERSION}）：L01S 启停 + 3 秒延时输出。

- 需求：`requirements.md`；冻结用例：`test_cases.md` / `s1-freeze.md`
- 程序：`source.fxil`；台架参数：`bench_config.json`
- 下一步：`./tools/plcweave.ps1 simulate <本目录>`
- 完整流程：仓库 `demo/START-HERE.md`

台架：{settings['port']} / {settings['baud']} / {settings['bytesize']}{settings['parity']}{settings['stopbits']} / 站号 {settings['station']}。
D8120={values['D8120_HEX']}。仅隔离空机；未确认烧录前不得打开串口写设备。
""", encoding="utf-8")
        return {"project": path, "settings": settings, "d8120": d8120}
    except BaseException:
        # This invocation just created the directory; never delete an existing project.
        if path.is_dir():
            shutil.rmtree(path)
        raise


def _project(directory, workspace):
    workspace = Path(workspace or Path.cwd()).resolve()
    case = _location(directory, workspace)
    if not case.is_dir():
        raise ValueError("Project does not exist")
    return case


def inspect_demo(directory, *, workspace=None):
    case = _project(directory, workspace)
    def exists(rel):
        return (case / rel).is_file()
    frozen_valid = exists("s1-freeze.md")
    if frozen_valid:
        try:
            frozen_suite(case)
        except (ValueError, FileNotFoundError):
            frozen_valid = False
    simulation = None
    if exists("candidate/V001/simulation_report.json"):
        try:
            simulation = json.loads((case / "candidate/V001/simulation_report.json").read_text(encoding="utf-8"))
            if simulation.get("source_sha256") != digest(case / "source.fxil") or \
                    simulation.get("test_sha256") != digest(suite_path(case)):
                simulation["status"] = "STALE"
        except (json.JSONDecodeError, OSError):
            simulation = {"status": "INVALID"}
    hardware = None
    if exists("evidence/hardware_report.json"):
        try:
            hardware = json.loads((case / "evidence/hardware_report.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            hardware = {"status": "INVALID"}
    flashed = False
    if exists("manual_download.json"):
        try:
            manual = json.loads((case / "manual_download.json").read_text(encoding="utf-8"))
            flashed = (manual.get("source_sha256") == digest(case / "source.fxil")
                       and manual.get("test_sha256") == digest(suite_path(case))
                       and manual.get("main_sha256") == digest(case / "candidate/V001/MAIN.csv")
                       and manual.get("comment_sha256") == digest(case / "candidate/V001/COMMENT.csv")
                       and bool(manual.get("compile_status")) and bool(manual.get("run_state")))
        except (json.JSONDecodeError, OSError):
            flashed = False
    bench_ready = False
    if exists("bench_ready.json"):
        try:
            ready = json.loads((case / "bench_ready.json").read_text(encoding="utf-8"))
            bench_ready = (ready.get("source_sha256") == digest(case / "source.fxil")
                           and ready.get("test_sha256") == digest(suite_path(case))
                           and ready.get("isolated_bench") is True
                           and ready.get("rs485_connected") is True
                           and ready.get("plc_running") is True)
        except (json.JSONDecodeError, OSError):
            bench_ready = False
    deliveries = sorted(p.name for p in (case / "delivery").glob("*.zip")) if (case / "delivery").is_dir() else []
    return {
        "project": case,
        "requirements": exists("requirements.md"),
        "test_cases": exists("test_cases.md"),
        "frozen": frozen_valid,
        "source": exists("source.fxil"),
        "instruction_csv": exists("candidate/V001/MAIN.csv"),
        "comment_csv": exists("candidate/V001/COMMENT.csv"),
        "simulation": simulation,
        "flashed": flashed,
        "bench_ready": bench_ready,
        "hardware": hardware,
        "deliveries": deliveries,
    }


def demo_status(directory, *, workspace=None):
    info = inspect_demo(directory, workspace=workspace)
    sim = info["simulation"]
    sim_status = sim.get("status", "未运行") if isinstance(sim, dict) else "未运行"
    sim_text = sim_status
    if isinstance(sim, dict) and sim.get("cases"):
        passed = sum(1 for case in sim["cases"] if case.get("status") == "PASS")
        sim_text += f"（用例 PASS {passed}/{len(sim['cases'])}）"
    hardware = info["hardware"]
    hil_text = "未执行"
    if isinstance(hardware, dict):
        hil_text = hardware.get("status", "已执行")
        if hardware.get("cases"):
            sampled = sum(1 for case in hardware["cases"]
                          if case.get("status") == "PASS" or case.get("sampled_checks") == "PASS")
            hil_text += f" (抽样通过 {sampled}/{len(hardware['cases'])})"
    lines = [
        f"项目：{info['project']}",
        f"D1 需求：{'OK' if info['requirements'] else '缺失'}；用例：{'OK' if info['test_cases'] else '缺失'}；冻结：{'OK' if info['frozen'] else '缺失'}",
        f"D2 程序：{'OK' if info['source'] else '缺失'}；指令表：{'OK' if info['instruction_csv'] else '缺失'}；注释：{'OK' if info['comment_csv'] else '缺失'}",
        f"D3 仿真：{sim_text}",
        f"D4 烧录确认：{'已记录' if info['flashed'] else '未记录'}",
        f"D5 S6：{hil_text}",
        f"D6 交付：{', '.join(info['deliveries']) if info['deliveries'] else '未打包'}",
    ]
    if not info["source"]:
        lines.append("下一步：先生成 source.fxil（demo start 应已生成）；不要烧录或进入 S6。")
    elif sim_status == "未运行":
        lines.append("下一步：运行 simulate 验证冻结用例。")
    elif sim_status != "SIM_PASS":
        lines.append("下一步：先修复仿真失败/UNVERIFIED；仿真通过前不要烧录或进入 S6。")
    elif info["deliveries"]:
        lines.append("下一步：已生成交付 ZIP；核对 MANIFEST.md 与 SUMMARY.md 后交付客户。"
                     "如后续补做 S6，可接硬件继续 D4/D5 后重新打包新版本。")
    elif not info["instruction_csv"]:
        lines.append("下一步：运行 simulate 生成候选 CSV。")
    elif not info["flashed"]:
        lines.append("下一步：让客户按 README 烧录；客户明确确认后运行 demo confirm-flash。")
    elif not info["bench_ready"]:
        lines.append("下一步：确认 PLC 已 RUN、485 已接、现场为隔离空机，然后运行 demo confirm-bench。")
    elif not isinstance(hardware, dict):
        lines.append("下一步：运行 preflight 和 hil --isolated-bench。")
    elif hardware.get("status") not in {"UNVERIFIED", "PASS"}:
        lines.append(f"下一步：S6 状态为 {hardware.get('status')}，检查后重新 preflight/hil；不要交付为通过。")
    elif not _hil_cleanup_ok(hardware):
        lines.append("下一步：S6 退出状态/清理未确认，恢复停止态并回读后再交付。")
    else:
        lines.append("下一步：运行 demo deliver 打包六项交付物。")
    print("\n".join(lines))
    return info


def confirm_flash(directory, *, operator, software, compile_status, run_state,
                  note="", force=False, workspace=None):
    case = _project(directory, workspace)
    operator = (operator or "").strip()
    software = (software or "").strip()
    compile_status = (compile_status or "").strip()
    run_state = (run_state or "").strip()
    if not operator or not software or not compile_status or not run_state:
        raise ValueError("Operator, GX Works2 version, compile status and RUN state are required")
    target = case / "manual_download.json"
    if target.exists() and not force:
        raise FileExistsError("Flash confirmation already exists; pass --force only for a deliberate re-confirmation")
    for filename in ("source.fxil", "test_cases.md", "candidate/V001/MAIN.csv",
                     "candidate/V001/COMMENT.csv"):
        if not (case / filename).is_file():
            raise ValueError(f"Missing {filename}; run simulate before confirming a download")
    frozen_suite(case)  # reject a post-freeze edit before recording any confirmation
    identity_path = case / "build_identity.json"
    if not identity_path.is_file():
        raise ValueError("Missing build_identity.json; rebuild the candidate before confirmation")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("source_sha256") != digest(case / "source.fxil"):
        raise ValueError("Build identity is stale for the current source")
    metadata, _, _ = parse_fxil(case / "source.fxil")
    record = {
        "source_sha256": digest(case / "source.fxil"),
        "test_sha256": digest(suite_path(case)),
        "main_sha256": digest(case / "candidate/V001/MAIN.csv"),
        "comment_sha256": digest(case / "candidate/V001/COMMENT.csv"),
        "confirmed_by": operator,
        "downloaded_at": _timestamp(),
        "software": software,
        "fxil_version": metadata.get("version", ""),
        "program_version": identity.get("program_version"),
        "edition": identity.get("edition"),
        "compile_status": compile_status,
        "run_state": run_state,
        "note": (note or "").strip(),
        "customer_confirmation": "客户明确确认已烧录；编译/RUN 状态由客户报告，本工具不独立验证",
    }
    (case / "manual_download.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_state(case, "D4_flash_confirmed", flashed=True)
    return record


def confirm_bench(directory, *, operator, isolated_bench, rs485_connected, plc_running,
                  note="", force=False, workspace=None):
    case = _project(directory, workspace)
    operator = (operator or "").strip()
    if not operator:
        raise ValueError("Bench operator is required")
    if not (isolated_bench and rs485_connected and plc_running):
        raise ValueError("Confirm isolated bench, RS485 wiring and PLC RUN before S6")
    target = case / "bench_ready.json"
    if target.exists() and not force:
        raise FileExistsError("Bench confirmation already exists; pass --force only for a deliberate re-confirmation")
    manual_path = case / "manual_download.json"
    if not manual_path.is_file():
        raise ValueError("Flash confirmation is missing; run demo confirm-flash first")
    frozen_suite(case)  # the bench confirmation must bind the same frozen suite
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    if manual.get("source_sha256") != digest(case / "source.fxil") or \
            manual.get("test_sha256") != digest(suite_path(case)):
        raise ValueError("Flash confirmation is stale for the current source/test")
    record = {
        "source_sha256": digest(case / "source.fxil"),
        "test_sha256": digest(suite_path(case)),
        "confirmed_by": operator,
        "confirmed_at": _timestamp(),
        "isolated_bench": True,
        "rs485_connected": True,
        "plc_running": True,
        "note": (note or "").strip(),
        "customer_confirmation": "客户明确确认：隔离空机、PLC 已 RUN、USB-RS485 已接 Modbus 口",
    }
    (case / "bench_ready.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_state(case, "D5_bench_ready", bench_ready=True)
    return record


def _requirements(case):
    value = case.get("requirements", [])
    if isinstance(value, str):
        value = re.split(r"[\s,;]+", value)
    return {str(item).strip() for item in value if str(item).strip()}


def _hil_case(hil, case_id):
    if not isinstance(hil, dict):
        return None
    for item in hil.get("cases", []):
        if item.get("id") == case_id:
            return item
    return None


def _hil_sampled(hil, case_id):
    item = _hil_case(hil, case_id)
    if item is None:
        return "未执行"
    if item.get("status") == "PROGRAM_FAIL" or item.get("sampled_checks") == "FAIL":
        return "FAIL"
    if item.get("status") == "PASS" or item.get("sampled_checks") == "PASS":
        return "PASS"
    return "UNVERIFIED"


def _hil_formal(hil, case_id):
    item = _hil_case(hil, case_id)
    if item is None:
        return "未执行"
    return "PASS" if item.get("status") == "PASS" else "UNVERIFIED"


def _hil_cleanup_ok(hil):
    if not isinstance(hil, dict):
        return False
    if hil.get("cleanup") != "stopped_output_disabled_and_read_back_zero":
        return False
    exit_state = hil.get("exit_state")
    if not isinstance(exit_state, dict) or not exit_state:
        return False
    return all(exit_state.get(name) == 0 for name in ("M0", "D154", "D8050", "D8051"))


def _assess(case, suite, simulation, hardware, flashed, wired):
    must = [item for item in suite["cases"] if item.get("priority", MUST) == MUST]
    total = len(must) or 1
    sim_map = {item.get("id"): item for item in (simulation or {}).get("cases", [])} if isinstance(simulation, dict) else {}
    sim_count = Counter((sim_map.get(item["id"]) or {}).get("status", "MISSING") for item in must)
    sim_passed = sum(1 for item in must if (sim_map.get(item["id"]) or {}).get("status") == "PASS")
    hil_executed = (isinstance(hardware, dict) and bool(hardware.get("cases"))
                    and hardware.get("status") in {"UNVERIFIED", "PASS"}
                    and flashed and wired and _hil_cleanup_ok(hardware))
    hil_passed = sum(1 for item in must if _hil_sampled(hardware, item["id"]) == "PASS") if hil_executed else 0
    defined = sorted(set(re.findall(r"(?<![A-Za-z0-9])R\d{1,3}(?![0-9])",
                                    (case / "requirements.md").read_text(encoding="utf-8-sig"))))
    covered = set()
    for item in must:
        covered.update(_requirements(item))
    missing_requirements = [name for name in defined if name not in covered]
    coverage = (len(defined) - len(missing_requirements)) / len(defined) if defined else 0.0
    completion = 20.0 * coverage
    completion += 30.0 * sim_passed / total
    completion += 40.0 * hil_passed / total if hil_executed else 0.0
    completion += 10.0
    all_sim = sim_passed == len(must) and len(must) > 0
    all_hil_sampled = hil_executed and hil_passed == len(must)
    demo_ok = all_sim and all_hil_sampled and bool(flashed) and not missing_requirements and coverage == 1.0
    # The demo tool does not certify formal/electrical/load acceptance, even if an
    # imported report claims PASS. Keep the verdict honest and non-forgeable.
    formal_ok = False
    rows = []
    for item in must:
        sim = sim_map.get(item["id"])
        rows.append({
            "id": item["id"],
            "title": item.get("title", ""),
            "requirements": sorted(_requirements(item)),
            "sim": (sim or {}).get("status", "MISSING"),
            "hil_sampled": _hil_sampled(hardware, item["id"]),
            "hil_formal": _hil_formal(hardware, item["id"]),
        })
    requirement_rows = []
    for name in defined:
        related = [item for item in must if name in _requirements(item)]
        if not related:
            verdict = "未覆盖"
        elif all((sim_map.get(item["id"]) or {}).get("status") == "PASS" for item in related):
            verdict = "演示级通过" if hil_executed and all(
                _hil_sampled(hardware, item["id"]) == "PASS" for item in related) else "仿真通过，S6 未完成"
        else:
            verdict = "未通过"
        requirement_rows.append({"id": name, "cases": [item["id"] for item in related], "verdict": verdict})
    return {
        "must": must,
        "total": total,
        "coverage": coverage,
        "covered_count": len(defined) - len(missing_requirements),
        "rows": rows,
        "requirement_rows": requirement_rows,
        "defined_requirements": defined,
        "missing_requirements": missing_requirements,
        "sim_counts": dict(sim_count),
        "sim_passed": sim_passed,
        "hil_executed": hil_executed,
        "hil_passed": hil_passed,
        "completion": round(completion, 1),
        "all_sim": all_sim,
        "all_hil_sampled": all_hil_sampled,
        "demo_ok": demo_ok,
        "formal_ok": formal_ok,
    }


def _hil_report(case, version, hardware, settings, assessment, check):
    lines = [
        "# 硬件在环（S6）测试报告",
        "",
        f"- 项目：{case.name}",
        f"- 交付版本：{version}",
        f"- 生成时间：{_readable_time()}",
        f"- 台架：{settings['port']} / {settings['baud']} / {settings['bytesize']}{settings['parity']}{settings['stopbits']} / 站号 {settings['station']}",
        "",
    ]
    if not isinstance(hardware, dict):
        lines += [
            "## 结论",
            "",
            "**未执行。** 客户未确认 PLC 与 485 连接，或尚未完成烧录确认；本次不得写成 PASS。",
            "",
            "## 用例状态",
            "",
            "| 用例 | 抽样检查 | 报告原始判定 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
        for item in assessment["must"]:
            lines.append(f"| {item['id']} | 未执行 | 未执行 | 无实机证据 |")
        lines += [
            "",
            "## 未测试范围",
            "",
            "- 全部 S6 用例；程序仅完成本地仿真。",
            "- 轮询可证明的稳态标量、逐扫描时序、端子电气与带载行为均未测试。",
            "",
        ]
        return "\n".join(lines)
    status = hardware.get("status", "UNVERIFIED")
    identity = hardware.get("identity") or {}
    executed = ("报告存在但无有效用例结果，未计入"
                if not hardware.get("cases")
                else ("已执行" if assessment["hil_executed"]
                      else "报告存在但未计入（缺少烧录/台架/清理或整体状态无效）"))
    lines += [
        "## 结论",
        "",
        f"**{executed}：{status}。** 抽样检查通过不等于正式 PASS；轮询无法证明逐扫描时序、单扫描脉冲、"
        "端子电气或真实负载性能，相关缺口保留为 UNVERIFIED。",
        "",
        f"- 错误信息：{hardware.get('error', '-')}",
        "",
        "## 台架与身份",
        "",
        f"- 程序版本/版次：{identity.get('version', '-')} / {identity.get('edition', '-')}",
        f"- 指纹字：{identity.get('fingerprint_words', '-')}；用例身份字：{identity.get('suite', '-')}",
        f"- 心跳：{identity.get('heartbeat_before', '-')} → {identity.get('heartbeat_after', '-')}",
        f"- 烧录确认：{'已记录' if check['flashed'] else '未记录'}",
        f"- 退出状态：{hardware.get('exit_state', '-')}；串口关闭：{hardware.get('serial_closed', '-')}",
        f"- 清理结果：{hardware.get('cleanup', '未确认')}；清理错误：{hardware.get('cleanup_error', '-')}",
        "",
        "## 用例结果",
        "",
        "| 用例 | 抽样检查 | 报告原始判定 | 说明 |",
        "| --- | --- | --- | --- |",
    ]
    for item in assessment["must"]:
        record = _hil_case(hardware, item["id"]) or {}
        reason = record.get("reason") or ("抽样检查通过；轮询不能升级为正式 PASS"
                                          if _hil_sampled(hardware, item["id"]) == "PASS" else "无实机证据")
        sampled = _hil_sampled(hardware, item["id"])
        if not assessment["hil_executed"] and sampled == "PASS":
            sampled = "PASS（未计入）"
        lines.append(f"| {item['id']} | {sampled} | "
                     f"{_hil_formal(hardware, item['id'])} | {reason} |")
    if not assessment["hil_executed"]:
        lines += [
            "",
            "> 本报告未计入演示通过：缺少烧录/台架/清理确认，或整体状态不是 UNVERIFIED/PASS。",
            "",
        ]
    lines += [
        "",
        "## 已完成 / 未测试",
        "",
        f"- 抽样检查 PASS：{assessment['hil_passed']} / {assessment['total']}。",
        f"- 报告原始 PASS（未评估，仅作证据）：{sum(1 for item in assessment['must'] if _hil_formal(hardware, item['id']) == 'PASS')} / {assessment['total']}。",
        "- 未测试：逐扫描轨迹、100 ms 级抖动、单扫描脉冲、端子电压/电流、带载闭环、掉电保持。",
        "- 演示用例为 9600 轮询留了时间余量；这不等于扫描级时序验证。",
        "- 原始证据：`hardware_report.json` 随包；`evidence/hardware_trace.jsonl` 保留在项目内，未随包。",
        "",
        "## 边界",
        "",
        "- 仅隔离空机，未接传感器、执行器或负载。",
        "- 只写白名单注入寄存器；写前做身份校验。批次结束必须恢复停止态并回读为零；"
        "`cleanup` 未确认时本报告不作为演示通过证据。",
        "- 本报告不能替代电气、带载或安全回路验收。",
        "",
    ]
    return "\n".join(lines)


def _summary(case, version, simulation, hardware, settings, assessment, check, display, connected):
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    replay_name = case.name + "-replay"
    replay_path = quote("project/" + replay_name)
    sim_status = (simulation or {}).get("status", "未运行") if isinstance(simulation, dict) else "未运行"
    completion = assessment["completion"]
    if assessment["demo_ok"]:
        demo_text = "**达到**（全部 MUST 用例仿真通过，S6 抽样通过，烧录/台架已确认，清理已回读）"
    else:
        demo_text = "**未达到**"
    if assessment["formal_ok"]:
        formal_text = "**达到（仅依据导入的 S6 报告字段）**"
    else:
        formal_text = "**未评估**（演示工具只做抽样，不判定正式验收）"
    if assessment["demo_ok"]:
        verdict = "达到演示验收要求；正式验收需另行提供合格采样/电气/带载证据"
    else:
        verdict = "未达到演示验收要求"
    lines = [
        "# 项目总结报告",
        "",
        f"- 项目：{case.name}",
        f"- 交付版本：{version}",
        f"- 生成时间：{_readable_time()}",
        f"- 需求文档 SHA256：{digest(case / 'requirements.md')}",
        f"- 测试文档 SHA256：{digest(case / 'test_cases.md')}",
        f"- 程序 SHA256：{digest(case / 'source.fxil')}",
        "- 候选目录：candidate/V001（程序版本 DEMO-V001）",
        f"- 台架：{settings['port']} / {settings['baud']} / {settings['bytesize']}{settings['parity']}{settings['stopbits']} / 站号 {settings['station']}",
        f"- 烧录确认：{'已记录' if check['flashed'] else '未记录'}",
        "",
        "## 1. 结论",
        "",
        f"- **项目完成度：{completion}%**（演示口径；正式验收另见结论）",
        f"- 演示验收：{demo_text}",
        f"- 正式验收：{formal_text}",
        f"- 演示要求：{verdict}。",
        "",
        "## 2. 验证结果",
        "",
        "| 层级 | 结果 |",
        "| --- | --- |",
        f"| S1 冻结 | {'已完成' if check['frozen'] else '未完成'} |",
        f"| S3 本地仿真 | {sim_status}；MUST 通过 {assessment['sim_passed']} / {assessment['total']} |",
        f"| S6 抽样 | {'已执行' if assessment['hil_executed'] else '未执行'}；抽样 PASS {assessment['hil_passed']} / {assessment['total']} |",
        f"| 烧录确认 | {'已记录' if check['flashed'] else '未记录'} |",
        f"| 台架就绪（RUN/485/隔离空机） | {'已确认' if check['wired'] else '未确认'} |",
        "",
        "## 3. 完成度构成",
        "",
        "| 项目 | 权重 | 本次得分 | 说明 |",
        "| --- | --- | --- | --- |",
        f"| 需求与冻结用例 | 20 | {round(20 * assessment['coverage'], 1)} | 需求覆盖 {assessment['covered_count']} / {len(assessment['defined_requirements'])} |",
        f"| 本地仿真 | 30 | {round(30 * assessment['sim_passed'] / assessment['total'], 1)} | 按 MUST 用例 PASS 比例 |",
        f"| S6 抽样 | 40 | {round(40 * assessment['hil_passed'] / assessment['total'], 1) if assessment['hil_executed'] else 0.0} | 按抽样 PASS 比例；未执行记 0 |",
        "| 交付包装 | 10 | 10 | 六项交付物与清单齐全 |",
        f"| **合计** | **100** | **{completion}** | |",
        "",
        "## 4. 需求与用例矩阵",
        "",
        "| 需求 | 覆盖用例 | 结论 |",
        "| --- | --- | --- |",
    ]
    for row in assessment["requirement_rows"]:
        lines.append(f"| {row['id']} | {', '.join(row['cases']) or '无'} | {row['verdict']} |")
    lines += [
        "",
        "> 需求覆盖按用例 Metadata 的 `requirements` 引用统计，不表示每条子句都有独立断言；"
        "X0/X1 等现场项未进入 watch，不能算已实测。",
        "",
        "## 5. 用例明细",
        "",
        "| 用例 | 需求 | 仿真 | S6 抽样 | S6 报告原始判定 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in assessment["rows"]:
        lines.append(f"| {row['id']} | {', '.join(row['requirements']) or '-'} | {row['sim']} | "
                     f"{row['hil_sampled']} | {row['hil_formal']} |")
    lines += [
        "",
        "## 6. 未完成与未测试",
        "",
    ]
    gaps = []
    if assessment["missing_requirements"]:
        gaps.append("需求未被用例覆盖：" + ", ".join(assessment["missing_requirements"]))
    if not assessment["all_sim"]:
        failed = [row["id"] for row in assessment["rows"] if row["sim"] != "PASS"]
        gaps.append("仿真未全部通过：" + ", ".join(failed))
    if not assessment["hil_executed"]:
        gaps.append("S6 未执行（未确认烧录或未连接 PLC/485）")
    elif not assessment["all_hil_sampled"]:
        failed = [row["id"] for row in assessment["rows"] if row["hil_sampled"] != "PASS"]
        gaps.append("S6 抽样未全部通过：" + ", ".join(failed))
    if isinstance(hardware, dict) and not _hil_cleanup_ok(hardware):
        gaps.append("S6 退出状态/清理未确认（必须回读 M0=0、D154=0、D8050=0、D8051=0）")
    if isinstance(hardware, dict) and not assessment["hil_executed"]:
        gaps.append("存在 S6 报告，但缺少烧录/台架确认或清理未确认，未计入演示通过")
    if not check["flashed"]:
        gaps.append("缺少客户烧录确认记录")
    if isinstance(hardware, dict) and hardware.get("status") == "PASS":
        gaps.append("S6 报告判定为 PASS；演示工具仍不认证正式验收，需合格采样/电气/带载证据")
    else:
        gaps.append("S6 报告判定仍为 UNVERIFIED：轮询不能证明逐扫描时序、单扫描脉冲或端子电气")
    gaps.append("未做端子电气、带载闭环、掉电保持与安全回路验证")
    lines += [f"- {gap}" for gap in gaps]
    lines += [
        "",
        "## 7. 交付物",
        "",
        "| 文件 | 说明 |",
        "| --- | --- |",
        "| requirements.md | 需求文档（演示场景 S0） |",
        "| test_cases.md | 测试用例文档（S1 冻结源） |",
        "| MAIN.csv | 程序指令表（CSV，GX Works2 列表导出方言） |",
        "| COMMENT.csv | 寄存器/软元件注释（CSV） |",
        "| HIL-REPORT.md | S6 硬件在环测试报告（完成/未测试） |",
        "| SUMMARY.md | 本总结报告（完成度与演示要求达成情况） |",
        "| MANIFEST.md | 交付文件 SHA256 清单 |",
        "| source.fxil | 程序源（便于追溯，不替代指令表） |",
        "| s1-freeze.md | S1 冻结哈希（需求/用例） |",
        "| build_identity.json | 程序身份与指纹 |",
        "| simulation_report.json | 本地仿真证据 |",
        "| manual_download.json | 客户烧录确认（如已记录） |",
        "| bench_ready.json | 台架/485/RUN 确认（如已记录） |",
        "| hardware_report.json | S6 抽样证据（如已执行） |",
        "",
        "## 8. 复现",
        "",
        "从仓库根目录创建新的无硬件演示工程；若名称已存在，统一换一个新名称，不覆盖原工程。",
        "",
        "```powershell",
        f"./tools/plcweave.ps1 demo start {quote(replay_name)} --port {quote(settings['port'])} --baud {settings['baud']} --parity {settings['parity']} --station {settings['station']} --data-bits {settings['bytesize']} --stop-bits {settings['stopbits']} --not-connected",
        f"./tools/plcweave.ps1 simulate {replay_path}",
        f"./tools/plcweave.ps1 demo deliver {replay_path} --version V001",
        "```",
        "",
        "只有客户实际成功编译下载该新工程、确认RUN和隔离台架后，才按下面继续；姓名和软件版本替换为现场实值。",
        "",
        "```powershell",
        f"./tools/plcweave.ps1 demo confirm-flash {replay_path} --operator '<姓名>' --software 'GX Works2 <现场版本>' --compile-status '客户确认零错误' --run-state RUN",
        f"./tools/plcweave.ps1 demo confirm-bench {replay_path} --operator '<姓名>' --isolated-bench --rs485-connected --plc-running",
        f"./tools/plcweave.ps1 preflight {replay_path}",
        f"./tools/plcweave.ps1 hil {replay_path} --isolated-bench",
        f"./tools/plcweave.ps1 demo deliver {replay_path} --version V002",
        "```",
        "",
        "## 9. 说明",
        "",
        "本报告由 `plcweave demo deliver` 依据冻结用例、仿真报告、烧录确认和 S6 报告生成；",
        "没有实机证据的项目不会被写成 PASS。演示程序只覆盖软元件与隔离输出，不构成生产验收。",
        "正式验收结论仅依据导入的 S6 报告字段；本工具不独立验证电气、带载或安全回路证据。",
        "",
    ]
    return "\n".join(lines)


def deliver_demo(directory, version="V001", *, workspace=None, hil_report=None):
    workspace = Path(workspace or Path.cwd()).resolve()
    case = _project(directory, workspace)
    required = ["requirements.md", "test_cases.md", "s1-freeze.md", "source.fxil",
                "build_identity.json", "candidate/V001/MAIN.csv", "candidate/V001/COMMENT.csv",
                "candidate/V001/simulation_report.json"]
    missing = [name for name in required if not (case / name).is_file()]
    if missing:
        raise ValueError("Missing delivery inputs: " + ", ".join(missing))
    simulation = json.loads((case / "candidate/V001/simulation_report.json").read_text(encoding="utf-8"))
    suite = frozen_suite(case)
    source_sha = digest(case / "source.fxil")
    test_sha = digest(suite_path(case))
    if simulation.get("status") != "SIM_PASS":
        raise ValueError(f"Simulation is {simulation.get('status')}; delivery requires SIM_PASS")
    if simulation.get("source_sha256") != source_sha:
        raise ValueError("Simulation report is stale for the current source")
    if simulation.get("test_sha256") != test_sha:
        raise ValueError("Simulation report is stale for the current test suite")
    if simulation.get("suite_version") != suite["suite_version"]:
        raise ValueError("Simulation report and frozen suite versions differ")
    if {item.get("id") for item in simulation.get("cases", [])} != {item["id"] for item in suite["cases"]}:
        raise ValueError("Simulation report does not cover exactly the frozen cases")
    identity = json.loads((case / "build_identity.json").read_text(encoding="utf-8"))
    if identity.get("source_sha256") != source_sha:
        raise ValueError("Build identity is stale for the current source")
    if hil_report is not None:
        hil_path = Path(hil_report)
        if not hil_path.is_absolute():
            hil_path = case / hil_path
        hil_path = hil_path.resolve()
        if not hil_path.is_relative_to(case) or not hil_path.is_file():
            raise ValueError("HIL report must be a file inside this project")
    else:
        hil_path = case / "evidence/hardware_report.json"
    hardware = json.loads(hil_path.read_text(encoding="utf-8")) if hil_path.is_file() else None
    if hardware is not None:
        if hardware.get("environment") != "hardware_sampled":
            raise ValueError("HIL report must be hardware_sampled evidence")
        if hardware.get("source_sha256") != source_sha:
            raise ValueError("HIL report does not bind the current source")
        if hardware.get("test_sha256") != test_sha:
            raise ValueError("HIL report does not bind the current test suite")
        if not isinstance(hardware.get("cases"), list):
            raise ValueError("HIL report cases must be a list")
        if hardware["cases"]:
            if hardware.get("serial_closed") is not True:
                raise ValueError("HIL report does not confirm the serial port was closed")
            report_identity = hardware.get("identity") or {}
            if (report_identity.get("version") != identity.get("program_version")
                    or report_identity.get("edition") != identity.get("edition")
                    or report_identity.get("fingerprint_words") != identity.get("fingerprint_words")
                    or report_identity.get("suite") != identity.get("suite_version_word")):
                raise ValueError("HIL report program identity does not match build_identity.json")
    if isinstance(hardware, dict) and isinstance(hardware.get("bench"), dict):
        settings = validate_bench_settings(hardware["bench"])
    else:
        settings = load_bench_settings(case)
    flashed = False
    manual_path = case / "manual_download.json"
    if manual_path.is_file():
        try:
            manual = json.loads(manual_path.read_text(encoding="utf-8"))
            flashed = (manual.get("source_sha256") == digest(case / "source.fxil")
                       and manual.get("test_sha256") == digest(suite_path(case))
                       and manual.get("main_sha256") == digest(case / "candidate/V001/MAIN.csv")
                       and manual.get("comment_sha256") == digest(case / "candidate/V001/COMMENT.csv")
                       and bool(manual.get("confirmed_by"))
                       and bool(manual.get("compile_status"))
                       and bool(manual.get("run_state")))
        except json.JSONDecodeError:
            flashed = False
    wired = False
    ready_path = case / "bench_ready.json"
    if ready_path.is_file():
        try:
            ready = json.loads(ready_path.read_text(encoding="utf-8"))
            wired = (ready.get("source_sha256") == digest(case / "source.fxil")
                     and ready.get("test_sha256") == digest(suite_path(case))
                     and ready.get("isolated_bench") is True
                     and ready.get("rs485_connected") is True
                     and ready.get("plc_running") is True)
        except json.JSONDecodeError:
            wired = False
    assessment = _assess(case, suite, simulation, hardware, flashed, wired)
    check = {"flashed": flashed, "wired": wired, "frozen": (case / "s1-freeze.md").is_file()}
    state = {}
    try:
        if (case / "demo.json").is_file():
            state = json.loads((case / "demo.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = {}
    try:
        display = case.relative_to(workspace).as_posix()
    except ValueError:
        display = case.name
    connected = bool(state.get("plc_connected", True))
    hil_text = _hil_report(case, version, hardware, settings, assessment, check)
    summary_text = _summary(case, version, simulation, hardware, settings, assessment,
                            check, display, connected)

    delivery = case / "delivery"
    delivery.mkdir(exist_ok=True)
    stage = delivery / f".demo-stage-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        (stage / "HIL-REPORT.md").write_text(hil_text, encoding="utf-8", newline="\n")
        (stage / "SUMMARY.md").write_text(summary_text, encoding="utf-8", newline="\n")
        files = [
            case / "requirements.md",
            case / "test_cases.md",
            case / "candidate/V001/MAIN.csv",
            case / "candidate/V001/COMMENT.csv",
            stage / "HIL-REPORT.md",
            stage / "SUMMARY.md",
            case / "source.fxil",
            case / "s1-freeze.md",
            case / "build_identity.json",
            case / "candidate/V001/simulation_report.json",
        ]
        if flashed:
            files.append(case / "manual_download.json")
        if wired:
            files.append(case / "bench_ready.json")
        if hardware is not None:
            files.append(hil_path)
        result = package_delivery(case, version, [str(path) for path in files], workspace=workspace)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    _update_state(case, "D6_delivered", delivered=version)
    return {**result, "completion": assessment["completion"], "demo_ok": assessment["demo_ok"],
            "formal_ok": assessment["formal_ok"]}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="plcweave demo", description="Guided PLCWeave demo")
    sub = parser.add_subparsers(dest="action", required=True)

    start = sub.add_parser("start", help="Create a frozen demo project and its source")
    start.add_argument("name")
    start.add_argument("--directory", help="Explicit external project directory")
    start.add_argument("--port", default=DEFAULT_BENCH["port"])
    start.add_argument("--baud", type=int, default=DEFAULT_BENCH["baud"])
    start.add_argument("--parity", default=DEFAULT_BENCH["parity"])
    start.add_argument("--station", type=int, default=DEFAULT_BENCH["station"])
    start.add_argument("--data-bits", type=int, default=8, choices=[7, 8])
    start.add_argument("--stop-bits", type=int, default=1, choices=[1, 2])
    start.add_argument("--not-connected", action="store_true", help="No PLC is connected; S6 will remain untested")

    status = sub.add_parser("status", help="Show demo progress and the next step")
    status.add_argument("directory")

    confirm = sub.add_parser("confirm-flash", help="Record the operator's explicit download confirmation")
    confirm.add_argument("directory")
    confirm.add_argument("--operator", required=True)
    confirm.add_argument("--software", required=True, help="GX Works2 version used for the download")
    confirm.add_argument("--compile-status", required=True)
    confirm.add_argument("--run-state", required=True)
    confirm.add_argument("--note", default="")
    confirm.add_argument("--force", action="store_true", help="Overwrite an existing confirmation")

    bench = sub.add_parser("confirm-bench", help="Record isolated bench, RS485 and RUN readiness before S6")
    bench.add_argument("directory")
    bench.add_argument("--operator", required=True)
    bench.add_argument("--isolated-bench", action="store_true")
    bench.add_argument("--rs485-connected", action="store_true")
    bench.add_argument("--plc-running", action="store_true")
    bench.add_argument("--note", default="")
    bench.add_argument("--force", action="store_true", help="Overwrite an existing bench confirmation")

    deliver = sub.add_parser("deliver", help="Build the six-item delivery folder and ZIP")
    deliver.add_argument("directory")
    deliver.add_argument("--version", default="V001", help="Delivery label; the demo candidate itself is V001")
    deliver.add_argument("--hil-report", help="Project-relative S6 report; defaults to evidence/hardware_report.json")

    args = parser.parse_args(argv)
    try:
        if args.action == "start":
            settings = {"port": args.port, "baud": args.baud, "parity": args.parity,
                        "bytesize": args.data_bits, "stopbits": args.stop_bits, "station": args.station}
            result = start_demo(args.name, directory=args.directory, settings=settings,
                                plc_connected=not args.not_connected)
            print(json.dumps({"project": str(result["project"]), "d8120": f"0x{result['d8120']:04X}",
                              "settings": result["settings"]}, ensure_ascii=False))
            return 0
        if args.action == "status":
            demo_status(args.directory)
            return 0
        if args.action == "confirm-flash":
            record = confirm_flash(args.directory, operator=args.operator, software=args.software,
                                   compile_status=args.compile_status, run_state=args.run_state,
                                   note=args.note, force=args.force)
            print(json.dumps(record, ensure_ascii=False))
            return 0
        if args.action == "confirm-bench":
            record = confirm_bench(args.directory, operator=args.operator,
                                   isolated_bench=args.isolated_bench,
                                   rs485_connected=args.rs485_connected,
                                   plc_running=args.plc_running, note=args.note,
                                   force=args.force)
            print(json.dumps(record, ensure_ascii=False))
            return 0
        result = deliver_demo(args.directory, args.version, hil_report=args.hil_report)
        payload = {key: str(value) if isinstance(value, Path) else value
                   for key, value in result.items()}
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(f"plcweave demo {args.action}: {exc}", file=sys.stderr)
        return 2
