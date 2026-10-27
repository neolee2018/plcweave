"""Two-phase engineering, immutable builds, human download and sampled HIL.

AI authors design, cases and the control core. This module supplies deterministic
gates and evidence; it neither invents requirements nor downloads a PLC program.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .demo import serial_format
from .hil import Bench, DEFAULT_BENCH, validate_bench_settings
from .markdown_suite import freeze_markdown, parse_markdown, read_freeze
from .projects import _location, _name, _publish, create_project, package_delivery
from .testing import compare, digest, frozen_suite, simulate
from .validation import independent_fingerprint
from .variants import DESIGN_DRAFT, _internal, read_design, render_variant

BASELINE_FILES = tuple(f"baseline/s1/{name}" for name in ("requirements.md", "test_cases.md", "design.md"))
INPUT_FILES = ("requirements.md", "test_cases.md", "design.md", "source.fxil",
               "s1-freeze.md", "design-freeze.md", *BASELINE_FILES)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _case(directory, workspace=None):
    case = _location(directory, workspace or Path.cwd())
    if not case.is_dir():
        raise ValueError("Project does not exist")
    return case


def _child(case, relative):
    path = case / relative
    resolved = path.resolve()
    if not resolved.is_relative_to(case) or resolved != path.absolute():
        raise ValueError(f"Project path redirects or escapes: {relative}")
    return path


def _hashes(case, names):
    return {str(name): digest(_child(case, name)) for name in names}


def require_reviews(case, node, bindings):
    """Validate four independently attributed records, not the reviewers' work.

    Actual independent contexts and checks remain the orchestrating agent's duty.
    Records are execution metadata, never a second requirements/test source.
    """
    folder = _child(case, f"reviews/{node}")
    reviewers, records = set(), {}
    for path in sorted(folder.glob("*.json")):
        _child(case, path.relative_to(case))
        value = _json(path)
        reviewer = value.get("reviewer_id")
        if not isinstance(reviewer, str) or not reviewer.strip() or reviewer in {"main", "/root"}:
            raise ValueError("Independent reviewer_id required")
        if reviewer in reviewers:
            raise ValueError("Four different reviewers required")
        if (value.get("independent") is not True or value.get("verdict") != "PASS"
                or not isinstance(value.get("checks"), list) or not value["checks"]
                or not all(isinstance(x, str) and x.strip() for x in value["checks"])
                or value.get("blocking_findings", []) != []):
            raise ValueError(f"Review is incomplete or has blocking findings: {path.name}")
        if any(value.get("input_sha256", {}).get(k) != v for k, v in bindings.items()):
            raise ValueError(f"Stale review inputs: {path.name}")
        reviewers.add(reviewer)
        records[path.relative_to(case).as_posix()] = digest(path)
    if len(reviewers) != 4:
        raise ValueError(f"{node} requires four independent review records; found {len(reviewers)}")
    return records


def init_workflow(name, *, workspace=None, directory=None):
    case = create_project(name, workspace=workspace, directory=directory)
    try:
        (case / "design.md").write_text(DESIGN_DRAFT, encoding="utf-8")
        (case / "README.md").write_text(
            f"# {name}\n\n用户只修改requirements.md；AI维护design.md、test_cases.md与source.fxil。\n"
            "先独立复核并workflow freeze，再编写共用控制程序及workflow build。\n"
            "第一阶段交付需求、设计、用例和HIL/正式版两份指令表。\n"
            "第二阶段用户编译下载HIL版、确认RUN，AI运行本项目测试脚本。\n"
            "每轮修复新建build版本、重新下载；需求变化用workflow revise保留旧版本。\n",
            encoding="utf-8")
    except BaseException:
        if case.resolve() == case:
            shutil.rmtree(case)  # create_project succeeded, so this invocation owns it
        raise
    return case


def freeze_workflow(directory, *, workspace=None):
    case = _case(directory, workspace)
    read_design(_child(case, "design.md"))
    parse_markdown(_child(case, "test_cases.md"))
    target = _child(case, "design-freeze.md")
    if target.exists():
        raise FileExistsError("Design freeze exists; create a new revision")
    bindings = _hashes(case, ("requirements.md", "test_cases.md", "design.md"))
    require_reviews(case, "S1", bindings)
    baseline = _child(case, "baseline/s1")
    baseline.mkdir(parents=True, exist_ok=False)
    freeze = None
    target_created = False
    try:
        for name in bindings:
            shutil.copy2(_child(case, name), baseline / name)
            if digest(baseline/name) != bindings[name]:
                raise ValueError("Inputs changed during freeze")
        freeze = freeze_markdown(case)
        with target.open('x',encoding='utf-8') as stream:
            target_created = True
            stream.write(f"# Design freeze\n\nSHA256: {bindings['design.md']}\n")
    except BaseException:
        if target_created:
            target.unlink(missing_ok=True)
        if freeze is not None:
            freeze.unlink()  # only the file just created by this invocation
        if baseline.resolve() == baseline:
            shutil.rmtree(baseline)
        raise
    return freeze


def _frozen_design(case):
    suite = frozen_suite(case)
    design_hash = digest(_child(case, "design.md"))
    frozen = _child(case, "design-freeze.md").read_text(encoding="utf-8")
    if frozen != f"# Design freeze\n\nSHA256: {design_hash}\n":
        raise ValueError("Frozen design changed; create a reviewed revision")
    for name,sha in {**read_freeze(case),"design.md":design_hash}.items():
        if digest(_child(case,f"baseline/s1/{name}")) != sha:
            raise ValueError("Frozen original Markdown snapshot changed")
    return suite, read_design(case / "design.md")


def _script(build):
    return f'''"""Project HIL runner: explicit download, connection and bench gates apply."""
import sys
from pathlib import Path
from plcweave.workflow import main

if __name__ == "__main__":
    raise SystemExit(main(["test", str(Path(__file__).resolve().parents[2]),
                          "--build", {build!r}, *sys.argv[1:]]))
'''


def build_workflow(directory, version, *, settings=None, workspace=None):
    case = _case(directory, workspace)
    _name(version)
    suite, design = _frozen_design(case)
    if suite.get("relationship_invariants"):
        raise ValueError("UNSUPPORTED: legacy relationship suite needs its qualified adapter")
    bindings = _hashes(case, INPUT_FILES)
    review_hashes = require_reviews(case, "S1", {k: bindings[k] for k in ("requirements.md", "test_cases.md", "design.md")})
    settings = validate_bench_settings({**DEFAULT_BENCH, **(settings or {})})
    # L01S RTU is the one implemented profile, not every FX-compatible CPU.
    if settings["bytesize"] != 8:
        raise ValueError("L01S Modbus RTU workflow requires 8 data bits")
    injections = {row["injection"]: row for row in design["inputs"]}
    bit_inputs = {key for key, row in injections.items() if row["logical"].startswith("M")}
    for device in suite["watch"]:
        _internal(device)
        if device in injections:
            raise ValueError("Observe the control image, not injection registers")
    for test in suite["cases"]:
        writes = [test["initial_words"], *(step["write"] for step in test["steps"])]
        for values in writes:
            if not set(values) <= set(injections):
                raise ValueError("Tests may only inject declared input registers")
            for key, value in values.items():
                if not -32768 <= value <= 32767 or key in bit_inputs and value not in {0, 1}:
                    raise ValueError("Input value outside declared word/bit range")
    builds = _child(case, "build")
    builds.mkdir(exist_ok=True)
    target = _child(case, f"build/{version}")
    if target.exists():
        raise FileExistsError("Build version exists; choose a new version")
    with tempfile.TemporaryDirectory(prefix=".build-", dir=builds) as temporary:
        stage = Path(temporary)
        reports = {}
        serial_word = serial_format(baud=settings["baud"], parity=settings["parity"],
                                    data_bits=settings["bytesize"], stop_bits=settings["stopbits"])
        for variant in ("hil", "production"):
            folder = stage / variant
            folder.mkdir()
            source = folder / "source.fxil"
            source.write_text(render_variant(case / "source.fxil", design, variant,
                                            serial_word=serial_word, station=settings["station"]), encoding="utf-8")
            if variant == "hil":
                fingerprint = independent_fingerprint(source)
                # Bind the PLC-side fingerprint to the frozen contract as well
                # as instructions; a changed suite cannot reuse the old identity.
                contract = hashlib.sha256(json.dumps(
                    {"canonical_sha256":fingerprint["canonical_sha256"],"inputs":bindings},
                    sort_keys=True).encode("utf-8")).digest()
                fingerprint["canonical_fingerprint_words"] = fingerprint.pop("fingerprint_words")
                fingerprint["contract_sha256"] = contract.hex()
                fingerprint["fingerprint_words"] = [int.from_bytes(contract[i:i+2],"little",signed=True) for i in (0,2)]
                source.write_text(render_variant(case / "source.fxil", design, variant,
                                                serial_word=serial_word, station=settings["station"],
                                                fingerprint=fingerprint["fingerprint_words"]), encoding="utf-8")
                identity = {**design["settings"], **fingerprint, "source_sha256": digest(source)}
                _write_json(folder / "identity.json", identity)
            mapping = {key: row["physical"] for key, row in injections.items()} if variant == "production" else {}
            routing = {row["physical"]:row["logical"] for row in design["outputs"]} if variant == "production" else {}
            reports[variant] = simulate(case, output=folder, source=source, input_map=mapping, routing_map=routing,
                                        reset_inputs=design["HIL reset"],reset_ms=design["settings"]["reset_ms"],
                                        reset_expectations=design["Reset expectations"])
            (folder / "instruction_list.md").write_text(
                f"# {variant} 指令表\n\n构建：{version}；共用核心SHA256：{bindings['source.fxil']}\n\n"
                + "```text\n" + source.read_text(encoding="utf-8") + "```\n", encoding="utf-8")
        (stage / "run_hil.py").write_text(_script(version), encoding="utf-8")
        for name in INPUT_FILES:
            saved = stage / "inputs" / name
            saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(_child(case,name),saved)
        status = "LOCAL_PASS" if all(r["status"] == "SIM_PASS" for r in reports.values()) else "LOCAL_FAIL"
        manifest = {"schema": "plcweave-two-phase-v1", "build": version, "created_at": _now(),
                    "input_sha256": bindings, "s1_reviews": review_hashes, "settings": settings,
                    "status": status, "variants": {k: v["status"] for k, v in reports.items()},
                    "tool_sha256": _tool_hashes(),
                    "files": {str(p.relative_to(stage)).replace("\\", "/"): digest(p)
                              for p in stage.rglob("*") if p.is_file()}}
        _frozen_design(case)
        if _hashes(case, INPUT_FILES) != bindings:
            raise ValueError("Inputs changed during build")
        _write_json(stage / "BUILD.json", manifest)
        # Publish only a complete, immutable build; TemporaryDirectory owns leftovers.
        _publish(stage,target)
    return {"build": target, "status": status, "variants": manifest["variants"]}


def _tool_hashes():
    from gxwlib import _core
    return {**{name: digest(Path(__file__).with_name(name))
               for name in ("workflow.py", "variants.py", "fx.py", "testing.py", "validation.py", "hil.py", "demo.py", "projects.py", "markdown_suite.py")},
            "engine_binary":digest(_core.__file__)}


def validate_build(directory, version, *, workspace=None):
    case = _case(directory, workspace)
    _name(version)
    build = _child(case, f"build/{version}")
    manifest = _json(_child(case, f"build/{version}/BUILD.json"))
    _frozen_design(case)
    if manifest.get("schema") != "plcweave-two-phase-v1" or manifest.get("build") != version:
        raise ValueError("Invalid build manifest")
    if manifest.get("input_sha256") != _hashes(case, INPUT_FILES):
        raise ValueError("Stale build: requirements, design, tests or program changed")
    if manifest.get("tool_sha256") != _tool_hashes():
        raise ValueError("Build tools changed; build a new candidate")
    if manifest.get("s1_reviews") != require_reviews(case, "S1", {k:manifest["input_sha256"][k] for k in ("requirements.md", "test_cases.md", "design.md")}):
        raise ValueError("S1 review evidence changed")
    files = manifest.get("files")
    required = {f"{v}/{name}" for v in ("hil", "production")
                for name in ("source.fxil", "MAIN.csv", "COMMENT.csv", "instruction_list.md", "simulation_report.json", "simulation_trace.csv")}
    if not isinstance(files, dict) or not required | {"run_hil.py", "hil/identity.json"} <= set(files):
        raise ValueError("Incomplete build manifest")
    for relative, sha in files.items():
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Invalid build member")
        if digest(_child(case, f"build/{version}/{relative}")) != sha:
            raise ValueError(f"Build artifact changed: {relative}")
    return case, build, manifest


def _local_pass(case, build, manifest):
    expected = {item["id"] for item in frozen_suite(case)["cases"]}
    if manifest.get("status") != "LOCAL_PASS":
        raise ValueError("Both variants require SIM_PASS before proceeding")
    for variant in ("hil", "production"):
        report = _json(build / variant / "simulation_report.json")
        cases = report.get("cases", [])
        if (report.get("status") != "SIM_PASS" or len(cases) != len(expected)
                or {c.get("id") for c in cases} != expected
                or any(c.get("status") != "PASS" for c in cases)
                or report.get("source_sha256") != digest(build / variant / "source.fxil")
                or report.get("test_sha256") != digest(case / "test_cases.md")):
            raise ValueError("Incomplete or stale local regression")


def confirm_download(directory, version, *, operator, software, compiled, running, workspace=None):
    case, build, manifest = validate_build(directory, version, workspace=workspace)
    _local_pass(case, build, manifest)
    if not operator.strip() or not software.strip() or compiled is not True or running is not True:
        raise ValueError("Operator, software version, successful compile and RUN confirmation required")
    folder = _child(case, "evidence/downloads")
    folder.mkdir(parents=True, exist_ok=True)
    record = {"build": version, "build_sha256": digest(build / "BUILD.json"),
              "variant": "hil", "source_sha256": digest(build / "hil/source.fxil"),
              "main_sha256": digest(build / "hil/MAIN.csv"), "operator": operator.strip(),
              "software": software.strip(), "compiled": True, "running": True, "timestamp": _now(),
              "basis": "operator confirmation; no automatic download or vendor compiler claimed"}
    _write_json(folder / f"{version}.json", record)
    return record


def _download(case, build, version):
    record = _json(_child(case, f"evidence/downloads/{version}.json"))
    if (record.get("build_sha256") != digest(build / "BUILD.json") or record.get("variant") != "hil"
            or record.get("source_sha256") != digest(build / "hil/source.fxil")
            or record.get("main_sha256") != digest(build / "hil/MAIN.csv")
            or not record.get("operator") or not record.get("software")
            or record.get("compiled") is not True or record.get("running") is not True):
        raise ValueError("Download confirmation is stale or incomplete; recompile and download this HIL build")
    return record


def run_hil(directory, version, batch, *, port, isolated_bench=False, connected=False, running=False,
            workspace=None, timeout_s=600):
    case, build, manifest = validate_build(directory, version, workspace=workspace)
    _local_pass(case, build, manifest)
    receipt = _download(case, build, version)
    suite, design = _frozen_design(case)
    if design["settings"]["target"] != "l01s":
        raise ValueError("UNSUPPORTED HIL mapping for this target; only the L01S profile is verified in this runner")
    if not (isolated_bench and connected and running):
        raise ValueError("Confirm isolated bench, connection and PLC RUN before any serial access")
    if type(timeout_s) not in {int, float} or not 0 < timeout_s <= 3600:
        raise ValueError("Batch timeout must be 0..3600 seconds")
    _name(batch)
    settings = validate_bench_settings({**manifest["settings"], "port": port})
    identity = _json(build / "hil/identity.json")
    folder = _child(case, f"evidence/hil/{version}/{batch}")
    folder.mkdir(parents=True, exist_ok=False)
    report = {"build": version, "batch": batch, "timestamp": _now(), "environment": "hardware_sampled",
              "build_sha256": digest(build / "BUILD.json"), "download": receipt,
              "settings": settings, "cases": [], "status": "UNVERIFIED", "serial_closed": False,
              "scope": "Declared steady-state scalar checks only; no physical I/O, load or scan-exact timing certification"}
    bench = None
    cancelled = None
    applied = dict(design["HIL reset"])
    logical_inputs = {row["logical"]:row["injection"] for row in design["inputs"]}
    deadline = time.monotonic() + timeout_s
    trace_path = folder / "trace.jsonl"
    with trace_path.open("x", encoding="utf-8") as trace:
        def emit(kind, **values):
            trace.write(json.dumps({"timestamp": _now(), "monotonic_s": time.monotonic(),
                                    "kind": kind, **values}, ensure_ascii=False) + "\n")
            trace.flush()

        def check_time():
            if time.monotonic() > deadline:
                raise TimeoutError("HIL batch timeout")

        def apply(values):
            for device, value in values.items():
                check_time()
                bench.write(device, value)
                applied[device] = value
                emit("input", device=device, value=value)

        def sample(watch, **context):
            check_time()
            before = time.monotonic()
            result = bench.sample(watch)
            emit("sample", values=result, span_ms=(time.monotonic()-before)*1000, **context)
            check_time()
            return result

        try:
            bench = Bench(settings=settings,
                          expected_identity=(identity["program_version"], identity["edition"]),
                          expected_fingerprint=identity["fingerprint_words"], expected_suite=identity["suite_word"],
                          allowed_writes={int(row["injection"][1:]) for row in design["inputs"]})
            report["identity"] = bench.verify()
            # The identity check itself may take time; recheck before the first write.
            validate_build(case, version, workspace=workspace)
            for test in suite["cases"]:
                apply(design["HIL reset"])
                time.sleep(min(design["settings"]["reset_ms"]/1000, max(0, deadline-time.monotonic())))
                if compare(sample(list(design["Reset expectations"]), case=test["id"], phase="reset"), design["Reset expectations"]):
                    raise ValueError("Reset did not establish the specified initial control state")
                apply(test["initial_words"])
                failures = []
                missing = False
                for index, step in enumerate(test["steps"]):
                    apply(step["write"])
                    settle = time.monotonic() + step["duration_ms"]/1000
                    while time.monotonic() < settle:
                        check_time()
                        observed = sample(suite["watch"], case=test["id"], step=index, phase="during")
                        errors = compare(observed, suite["global_invariants"]) + compare(observed, step["invariant"])
                        missing |= any(x["kind"] == "UNVERIFIED" for x in errors)
                        failures += [x for x in errors if x["kind"] == "PROGRAM_FAIL"]
                        time.sleep(min(0.05, max(0, settle-time.monotonic())))
                    observed = sample(list(dict.fromkeys([*suite["watch"], *logical_inputs])), case=test["id"], step=index, phase="settled")
                    if compare(observed, {logical:applied[injection] for logical,injection in logical_inputs.items()}):
                        raise ValueError("PLC input image did not consume the applied injection")
                    errors = compare(observed, step["expect"]) + compare(observed, suite["global_invariants"]) + compare(observed, step["invariant"])
                    missing |= any(x["kind"] == "UNVERIFIED" for x in errors)
                    failures += [x for x in errors if x["kind"] == "PROGRAM_FAIL"]
                qualified = (test.get("hardware_scope") == "steady_state" and not suite["global_invariants"]
                             and not any(step["invariant"] for step in test["steps"]))
                status = "PROGRAM_FAIL" if failures else "PASS" if qualified and not missing else "UNVERIFIED"
                report["cases"].append({"id": test["id"], "status": status, "failures": failures[:12],
                                        "reason": "steady-state only" if qualified else "Polling cannot certify undeclared scope or continuous/scan-level invariants"})
            validate_build(case, version, workspace=workspace)
            check_time()
            statuses = {item["status"] for item in report["cases"]}
            report["status"] = "PROGRAM_FAIL" if "PROGRAM_FAIL" in statuses else "UNVERIFIED" if "UNVERIFIED" in statuses else "PASS"
        except BaseException as exc:
            report.update(status="TEST_INFRA_ERROR", error=str(exc),error_type=type(exc).__name__)
            if not isinstance(exc,Exception):
                cancelled=exc
            emit("error", error=str(exc))
        finally:
            if bench is not None:
                if bench.verified:
                    try:
                        # Cleanup uses the bounded serial timeout even after batch timeout.
                        for device, value in design["HIL cleanup"].items():
                            bench.write(device, value)
                            emit("cleanup_input", device=device, value=value)
                        time.sleep(design["settings"]["reset_ms"]/1000)
                        report["exit_state"] = bench.sample(list(design["Cleanup expectations"]))
                        emit("cleanup_sample", values=report["exit_state"])
                        if compare(report["exit_state"], design["Cleanup expectations"]):
                            raise ValueError("Cleanup state not confirmed")
                        report["cleanup"] = "CONFIRMED"
                    except BaseException as exc:
                        report.update(status="TEST_INFRA_ERROR", cleanup="UNCONFIRMED", cleanup_error=str(exc))
                        if not isinstance(exc,Exception):cancelled=exc
                else:
                    report["cleanup"] = "NO_WRITES_IDENTITY_UNVERIFIED"
                try:
                    bench.close()
                    report["serial_closed"] = True
                except BaseException as exc:
                    report.update(status="TEST_INFRA_ERROR", close_error=str(exc))
                    if not isinstance(exc,Exception):cancelled=exc
            else:
                report["cleanup"] = "NO_CLIENT_CREATED"
                report["serial_closed"] = True
    report["trace_sha256"] = digest(trace_path)
    report["next_action"] = next_action(report["status"])
    _write_json(folder / "report.json", report)
    if cancelled is not None:
        raise cancelled
    return report


def next_action(status):
    return {"PASS": "Review results and package stage 2; production physical I/O remains separately verified",
            "PROGRAM_FAIL": "AI fixes the common core, builds both variants under a new build ID; user recompiles and downloads before retest",
            "TEST_INFRA_ERROR": "Repair communication, script, reset, identity or collection; preserve frozen expectations",
            "UNVERIFIED": "Add the missing observation capability; do not count unverified cases as passed"}.get(status, "Inspect current inputs and local regression")


def _hardware_pass(case, build, version, batch):
    _name(batch)
    relative = f"evidence/hil/{version}/{batch}"
    folder = _child(case, relative)
    report = _json(folder / "report.json")
    expected = {item["id"] for item in frozen_suite(case)["cases"]}
    cases = report.get("cases", [])
    _download(case, build, version)
    if (report.get("build_sha256") != digest(build / "BUILD.json") or report.get("status") != "PASS"
            or len(cases) != len(expected) or {c.get("id") for c in cases} != expected
            or any(c.get("status") != "PASS" for c in cases)
            or report.get("cleanup") != "CONFIRMED" or report.get("serial_closed") is not True
            or report.get("trace_sha256") != digest(_child(case, f"{relative}/trace.jsonl"))):
        raise ValueError("Complete, current HIL PASS and confirmed cleanup required")
    return folder


def deliver_workflow(directory, version, delivery_version, *, stage=1, batch=None, workspace=None):
    case, build, manifest = validate_build(directory, version, workspace=workspace)
    _local_pass(case, build, manifest)
    if stage not in {1, 2}:
        raise ValueError("Delivery stage must be 1 or 2")
    bindings = {**manifest["input_sha256"], f"build/{version}/BUILD.json": digest(build / "BUILD.json")}
    hardware = None
    if stage == 2:
        if not batch:
            raise ValueError("Select a single final HIL batch")
        hardware = _hardware_pass(case, build, version, batch)
        for filename in ("report.json", "trace.jsonl"):
            bindings[(hardware / filename).relative_to(case).as_posix()] = digest(hardware / filename)
    reviews = require_reviews(case, f"stage{stage}-{version}", bindings)
    files = {name: case / name for name in INPUT_FILES}
    files["BUILD.json"] = build / "BUILD.json"
    files[f"build/{version}/BUILD.json"] = files.pop("BUILD.json")
    files[f"build/{version}/run_hil.py"] = build / "run_hil.py"
    for variant in ("hil", "production"):
        for filename in ("source.fxil", "MAIN.csv", "COMMENT.csv", "instruction_list.md", "simulation_report.json", "simulation_trace.csv"):
            files[f"build/{version}/{variant}/{filename}"] = build / variant / filename
    # Include all hash-bound artifacts, including runtime CSVs, for re-checking
    # an extracted delivery as a self-contained project with the installed tools.
    for filename in manifest["files"]:
        files[f"build/{version}/{filename}"] = build / filename
    if hardware:
        for filename in ("report.json", "trace.jsonl"):
            files[(hardware/filename).relative_to(case).as_posix()] = hardware / filename
        files[f"evidence/downloads/{version}.json"] = case / f"evidence/downloads/{version}.json"
    for name in {**manifest["s1_reviews"], **reviews}:
        files[Path(name).as_posix()] = case / name
    with tempfile.TemporaryDirectory(prefix=".delivery-", dir=case) as temporary:
        summary = Path(temporary) / "SUMMARY.md"
        summary.write_text(
            f"# 第一阶段交付\n\n" if stage == 1 else "# 第二阶段交付\n\n", encoding="utf-8")
        with summary.open("a", encoding="utf-8") as stream:
            stream.write(f"构建：{version}；需求SHA256：{manifest['input_sha256']['requirements.md']}\n\n"
                         "HIL版和正式版：本地语法/受支持指令执行及冻结用例回归通过。\n\n"
                         + (f"HIL：批次{batch}规定的稳态用例通过，采样范围见报告。\n\n" if hardware else "HIL：本阶段未执行。厂家编译下载：由用户在下一阶段完成。\n\n")
                         + "正式版物理I/O、电气及带载：UNVERIFIED，不能由测试版软件寄存器结果代替。\n\n"
                         f"程序：build/{version}/hil/MAIN.csv、build/{version}/production/MAIN.csv；各自COMMENT.csv和instruction_list.md同目录。\n\n"
                         f"使用已安装的同版PLCWeave运行build/{version}/run_hil.py，须先记录本项目的编译下载并提供连接及隔离确认。\n")
        files["SUMMARY.md"] = summary
        result = package_delivery(case, delivery_version, files, workspace=workspace)
    return {**result, "stage": stage, "hardware": "PASS (HIL scope only)" if hardware else "NOT_EXECUTED",
            "production_hardware": "UNVERIFIED"}


def revise_workflow(directory, version, *, reason, workspace=None):
    case = _case(directory, workspace)
    _name(version)
    if not reason.strip():
        raise ValueError("Revision reason required")
    previous = read_freeze(case)
    frozen_design = _child(case,'design-freeze.md').read_text(encoding='utf-8')
    design_match = re.fullmatch(r'# Design freeze\n\nSHA256: ([0-9a-f]{64})\n',frozen_design)
    if design_match is None:
        raise ValueError('Invalid previous design freeze')
    old_hashes = {**previous,'design.md':design_match[1]}
    for name,sha in old_hashes.items():
        if digest(_child(case,f'baseline/s1/{name}')) != sha:
            raise ValueError(f'Old frozen snapshot missing or changed: {name}')
    original = _child(case,"baseline/s1/requirements.md")
    folder = _child(case, "revisions")
    folder.mkdir(exist_ok=True)
    target = _child(case, f"revisions/{version}")
    result = init_workflow(version, workspace=workspace, directory=target)
    try:
        shutil.copy2(_child(case, "requirements.md"), result / "requirements.md")
        shutil.copy2(_child(case, "baseline/s1/test_cases.md"), result / "test_cases.md")
        shutil.copy2(_child(case, "baseline/s1/design.md"), result / "design.md")
        old = result / "previous"
        old.mkdir()
        for name in ("requirements.md","test_cases.md","design.md"):
            shutil.copy2(_child(case,f"baseline/s1/{name}"),old/name)
            if digest(old/name) != old_hashes[name]:
                raise ValueError('Old snapshot changed while copying revision')
        changes = ''.join(difflib.unified_diff([line+'\n' for line in original.read_text(encoding='utf-8-sig').splitlines()],
                                              [line+'\n' for line in (result/'requirements.md').read_text(encoding='utf-8-sig').splitlines()],
                                              fromfile='previous/requirements.md',tofile='requirements.md'))
        (result / "revision.md").write_text(
            f"# 需求修订 {version}\n\n原因：{reason.strip()}\n\n"
            f"原冻结需求SHA256：{previous['requirements.md']}\n"
            f"当前需求SHA256：{digest(result/'requirements.md')}\n\n"
            "AI须依据需求修订设计、资源与用例，完成四人独立S1复核后重新冻结。\n"
            "复制的用例仅为待审草稿，不继承旧冻结/通过结论；程序须在新冻结后编写。\n",
            encoding="utf-8")
        (result/'requirement-diff.md').write_text('# 需求版本差异\n\n```diff\n'+changes+'\n```\n',encoding='utf-8')
    except BaseException:
        if result.resolve() == result and result.is_relative_to(case):
            shutil.rmtree(result)
        raise
    return result


def status_workflow(directory, version=None, *, workspace=None):
    case = _case(directory, workspace)
    if not (case / "s1-freeze.md").is_file():
        return {"state": "AUTHOR_DESIGN_AND_TESTS", "next_action": "AI authors design/cases, obtains four independent S1 reviews, then freezes before source"}
    try:
        _frozen_design(case)
    except (ValueError, OSError) as exc:
        return {"state": "NEEDS_REVISION", "reason": str(exc), "next_action": "AI creates a reviewed revision from changed requirements"}
    if version is None:
        return {"state": "SELECT_BUILD", "next_action": "Build a new immutable candidate or select --build"}
    try:
        _, build, manifest = validate_build(case, version, workspace=workspace)
        _local_pass(case, build, manifest)
        _download(case, build, version)
    except (ValueError, OSError) as exc:
        return {"state": "BUILD_OR_DOWNLOAD_REQUIRED", "reason": str(exc),
                "next_action": "AI builds both variants; user compiles/downloads HIL and confirms the exact build"}
    batches = sorted(_child(case, f"evidence/hil/{version}").glob("*/report.json"), key=lambda p:p.stat().st_mtime)
    if batches:
        latest = batches[-1]
        _child(case, latest.relative_to(case))
        report = _json(latest)
        status = report.get("status", "UNVERIFIED")
        if status == "PASS":
            try:
                _hardware_pass(case, build, version, latest.parent.name)
            except (ValueError, OSError):
                status = "UNVERIFIED"
        return {"state": status, "batch": latest.parent.name, "next_action": next_action(status)}
    return {"state": "READY_FOR_HIL", "next_action": "Provide port and explicit connected/RUN/isolated-bench confirmations to run the project script"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="PLCWeave two-phase engineering workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("project"); p.add_argument("--directory")
    for command in ("freeze", "build", "status", "deliver", "confirm-download", "test", "revise"):
        p = sub.add_parser(command); p.add_argument("project")
        if command in {"status", "deliver", "confirm-download", "test"}:
            p.add_argument("--build", required=command != "status")
        if command in {"build", "deliver", "revise"}:
            p.add_argument("--version", required=True)
        if command == "build":
            for key, default in DEFAULT_BENCH.items():
                p.add_argument(f"--{key}", default=default, type=type(default))
        if command == "deliver":
            p.add_argument("--stage", type=int, choices=[1, 2], default=1); p.add_argument("--batch")
        if command == "confirm-download":
            p.add_argument("--operator", required=True); p.add_argument("--software", required=True)
            p.add_argument("--compiled", action="store_true"); p.add_argument("--running", action="store_true")
        if command == "test":
            p.add_argument("--batch", required=True); p.add_argument("--port", required=True)
            for flag in ("isolated-bench", "connected", "running"):
                p.add_argument(f"--{flag}", action="store_true")
        if command == "revise":
            p.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init": result = init_workflow(args.project, directory=args.directory)
        elif args.command == "freeze": result = freeze_workflow(args.project)
        elif args.command == "build": result = build_workflow(args.project, args.version, settings={k: getattr(args, k) for k in DEFAULT_BENCH})
        elif args.command == "status": result = status_workflow(args.project, args.build)
        elif args.command == "deliver": result = deliver_workflow(args.project, args.build, args.version, stage=args.stage, batch=args.batch)
        elif args.command == "confirm-download": result = confirm_download(args.project, args.build, operator=args.operator, software=args.software, compiled=args.compiled, running=args.running)
        elif args.command == "test": result = run_hil(args.project, args.build, args.batch, port=args.port, isolated_bench=args.isolated_bench, connected=args.connected, running=args.running)
        else: result = revise_workflow(args.project, args.version, reason=args.reason)
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 1 if isinstance(result, dict) and result.get("status") in {"LOCAL_FAIL", "PROGRAM_FAIL", "TEST_INFRA_ERROR", "UNVERIFIED"} else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
