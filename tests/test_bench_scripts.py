"""Real child-process telemetry, completion acknowledgement and manual ownership."""
import io
import json
import time
from pathlib import Path

import pytest

from plcweave.bench.app import BenchWorker
from plcweave.bench.contract import DEFAULT_DEMO_PROFILE
from plcweave.bench.engine import BenchEngine, State
from plcweave.bench.rtu import LoopbackTransport
from plcweave.bench.script_bridge import ScriptController, ScriptProcess, device_values
from plcweave.bench.script_host import EventWriter, observe_client
from plcweave.bench.store import SessionStore
from plcweave.bench.virtual import VirtualPLC
from plcweave.bench.script_projects import project_adapter, prepare_arguments


DEMO = Path(__file__).resolve().parents[1] / "demo/bench-script-demo.py"
# Prefer the private customer project when present; a fresh public clone falls back to the
# public copy shipped in demo/ so these tests never depend on ignored project/ contents.
_PRIVATE_PRIORITY = DEMO.parent.parent / "project/l01s-water-standard/run_hil_v3.py"
_PUBLIC_PRIORITY = DEMO.parent / "water-supply-standard/l01s-water-standard/run_hil_v3.py"
PRIORITY = _PRIVATE_PRIORITY if _PRIVATE_PRIORITY.exists() else _PUBLIC_PRIORITY


def process_events(process, timeout=15):
    events = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        event = process.events.get(timeout=timeout)
        events.append(event)
        if event["kind"] == "process_exit":
            return events
    raise AssertionError("script did not exit")


def test_original_script_commands_and_actual_readbacks_are_observed(tmp_path):
    process = ScriptProcess(DEMO, [], tmp_path / "transactions.jsonl", demo=True)
    try:
        events = process_events(process)
        assert events[-1]["exit_code"] == 0
        assert any(event.get("kind") == "request" and event.get("address") == 260
                   and event["values"] == [88] for event in events)
        assert any(event.get("kind") == "response" and event.get("address") == 8050
                   and event["values"] == [3000, 1500] for event in events)
        assert any(event.get("kind") == "output" and "断言全部通过" in event["text"] for event in events)
        assert events[-2]["kind"] == "finished"
        disk = [json.loads(line) for line in (tmp_path / "transactions.jsonl").read_text(encoding="utf-8").splitlines()]
        assert disk[-1]["kind"] == "finished"
    finally:
        process.close()
    assert not process.reader.is_alive()


@pytest.mark.parametrize("body,code", [("raise RuntimeError('失败证据')", 1), ("raise SystemExit(7)", 7)])
def test_script_errors_preserve_exit_status(tmp_path, body, code):
    script = tmp_path / "test.py"
    script.write_text(body, encoding="utf-8")
    process = ScriptProcess(script, [], tmp_path / "events.jsonl", demo=True)
    try:
        events = process_events(process)
        assert events[-1]["exit_code"] == code
        if code == 1:
            assert any("失败证据" in event.get("text", "") for event in events)
    finally:
        process.close()


def test_completion_waits_for_ack_then_manual_commands_work(tmp_path):
    profile = DEFAULT_DEMO_PROFILE
    device = VirtualPLC(profile)
    engine = BenchEngine(profile=profile, transport=LoopbackTransport(device))
    engine.apply_settings(demo=True, version_address=300)
    store = SessionStore(tmp_path / "sessions")
    worker = BenchWorker(engine, store)
    controller = worker.scripts
    controller.start(DEMO, [])
    try:
        assert engine.state == State.SCRIPT_RUNNING
        with pytest.raises(PermissionError):
            engine.connect()
        deadline = time.monotonic() + 15
        snapshots = []
        while engine.state != State.SCRIPT_CONFIRM and time.monotonic() < deadline:
            controller.poll()
            snapshots.append(tuple(engine.da_raw))
            time.sleep(0.02)
        assert engine.state == State.SCRIPT_CONFIRM
        assert (3000, 1500) in snapshots
        assert controller.process is None
        assert store.current_id is None
        assert engine.set_x(0, 1)["result"] == "拒绝"
        generation = controller.generation
        controller.acknowledge(generation)
        assert engine.state == State.SIMULATING
        assert engine.set_x(0, 1)["result"] == "已生效"
        engine.poll()
        assert engine.y_bits[0] == 1
        engine.stop_simulation()
        engine.disconnect()
    finally:
        controller.close()
    assert store.list_sessions()


def test_observer_preserves_response_and_records_before_write(tmp_path):
    events = EventWriter(io.StringIO(), tmp_path / "events.jsonl")
    response = object()

    class Client:
        def write_register(self, address, value, **kwargs):
            entries = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            assert entries[-1]["kind"] == "request"
            return response

        def close(self):
            pass

    observed = observe_client(Client(), events, connection={"port": "fake"}, family="pymodbus")
    try:
        assert observed.write_register(260, 88, device_id=1) is response
    finally:
        events.file.close()


def test_address_spaces_keep_coils_separate_from_words():
    assert device_values("coil", 0x3300, [1, 0]) == {"Y0": 1, "Y1": 0}
    assert device_values("input", 0x3400, [0, 1]) == {"X0": 0, "X1": 1}
    assert device_values("D", 0x3300, [7]) == {"D13056": 7}


def test_user_closes_a_running_script_and_its_reader(tmp_path):
    script = tmp_path / "waiting.py"
    script.write_text("import time\nprint('running', flush=True)\ntime.sleep(60)", encoding="utf-8")
    process = ScriptProcess(script, [], tmp_path / "events.jsonl", demo=True)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        event = process.events.get(timeout=8)
        if event.get("kind") == "output":
            break
    process.close()
    assert process.process.poll() is not None and not process.reader.is_alive()


def test_real_manual_register_handoff_uses_connection_without_hil_session(tmp_path):
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE,
                         transport=LoopbackTransport(VirtualPLC(DEFAULT_DEMO_PROFILE)))
    engine.apply_settings(version_address=196)
    store = SessionStore(tmp_path / "sessions")
    worker = BenchWorker(engine, store)
    engine.set_customer_watch(260, "手动参数", "读写", 0, 100)
    engine.start_manual_test()
    assert engine.state == State.MANUAL and not engine.session_active
    result = engine.write_customer_register(260, "77", session_token=engine.session_token)
    assert result["result"] == "已读回" and result["effective"] == 77
    worker.scripts.close()  # Closing an idle script controller preserves this manual record.
    assert store.current_id is not None and engine._recording
    engine.disconnect()
    assert store.current_id is None


def test_legacy_priority_mapping_matches_frozen_source_and_uses_unique_output():
    adapter = project_adapter(PRIORITY)
    assert adapter["inputs"] == [
        {"physical": "D8030", "logical": "D110", "injection": "D330"},
        {"physical": "X0", "logical": "D320", "injection": "D320"},
        {"physical": "X1", "logical": "D321", "injection": "D321"},
    ]
    assert {row[0]: row[2] for row in adapter["watches"]}[309] == "只读"
    first, second = prepare_arguments(PRIORITY, []), prepare_arguments(PRIORITY, [])
    assert first[0] == "--output" and first[1] != second[1]
    assert not (PRIORITY.parent / "evidence/s6-v3" / first[1]).exists()
    assert prepare_arguments(PRIORITY, ["--output=custom"]) == ["--output=custom"]


def test_priority_adapter_ships_english_labels_for_every_watch():
    # 英文界面用适配器的 watch_names_en / watch_notes_en 替换 Name 与单位列；
    # 少一条就会在英文界面露出中文，所以按地址逐条核对（含中文原文仍存在）。
    adapter = project_adapter(PRIORITY)
    watches = {row[0]: row[1] for row in adapter["watches"]}
    assert watches[300] == "程序版本"                 # 中文仍是权威文本
    assert adapter["watch_names_en"][300] == "Program version"
    assert adapter["watch_notes_en"][308] == "bar · 0–16.0"
    missing_names = set(watches) - set(adapter["watch_names_en"])
    missing_notes = set(watches) - set(adapter["watch_notes_en"])
    assert not missing_names and not missing_notes
    assert all(adapter["watch_names_en"][addr].strip() for addr in watches)
    assert all(adapter["watch_notes_en"][addr].strip() for addr in watches)


def test_failed_station_probe_does_not_lock_live_values_or_handoff(tmp_path):
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE)
    store = SessionStore(tmp_path)
    controller = BenchWorker(engine, store).scripts
    engine.state = State.SCRIPT_RUNNING
    engine.settings["version_address"] = 500
    endpoint = {"port": "fake", "baud": 19200, "bytesize": 8, "parity": "N", "stopbits": 2}
    request = {"kind": "request", "operation": "read", "area": "D", "address": 8050,
               "count": 2, "values": None, "connection": {**endpoint, "station": 1}}
    controller._consume(request)
    controller._consume({**request, "kind": "response", "success": False})
    assert controller.connection is None
    controller._consume({**request, "connection": {**endpoint, "station": 2}})
    controller._consume({**request, "kind": "response", "success": True,
                         "values": [1234, 2345], "connection": {**endpoint, "station": 2}})
    assert controller.connection["station"] == 2 and engine.da_raw == [1234, 2345]
    controller._observed({"D196": 999}, None)
    assert engine.version_value is None  # no universal D196 guess
    controller._observed({"D500": 42}, None)
    assert (engine.version_address, engine.version_value) == (500, 42)
    assert controller.command_count == 2


def test_priority_manual_ad_uses_project_input_and_online_identity(tmp_path):
    adapter = project_adapter(PRIORITY)

    class PressureDevice(VirtualPLC):
        def run_program(self):
            self.registers[110] = self.registers.get(330, 0) if self.registers.get(322) == 1 else 0
            self.registers[8050] = self.registers[110]

    device = PressureDevice(DEFAULT_DEMO_PROFILE, version_value=5)
    device.registers.update(dict(adapter["identity"]))
    device.registers[322] = 1
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, transport=LoopbackTransport(device))
    engine.apply_settings(version_address=300)
    BenchWorker(engine, SessionStore(tmp_path))
    engine.manual_inputs = {"D8030": adapter["inputs"][0]}
    engine.manual_identity = adapter["identity"]
    engine.start_manual_test()
    assert engine.state == State.MANUAL
    result = engine.set_ad_eng(0, "5")
    assert result["result"] == "已读回"
    assert device.registers[330] == engine.effective_ad[0] == engine.da_raw[0] == 2000
    assert 8030 not in device.registers
    # V0.6.1：手动注入不做 D322 条件门禁——直接写注入寄存器，是否消费由程序决定
    device.registers[322] = 0
    result = engine.set_ad_eng(0, "6")
    assert result["result"] == "已读回" and device.registers[330] == 2400
    assert engine.state == State.MANUAL
    device.registers[301] = 32
    assert engine.set_ad_eng(0, "6")["result"] == "失败"
    engine.disconnect()


def test_priority_manual_x_terminal_drives_start_stop_commands(tmp_path):
    adapter = project_adapter(PRIORITY)

    class CommandDevice(VirtualPLC):
        def run_program(self):
            if self.registers.get(321) == 1:
                self.registers[0] = 0           # stop wins
            elif self.registers.get(320) == 1:
                self.registers[0] = 1           # start request latches run

    device = CommandDevice(DEFAULT_DEMO_PROFILE, version_value=3)
    device.registers.update(dict(adapter["identity"]))
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, transport=LoopbackTransport(device))
    engine.apply_settings(version_address=300)
    BenchWorker(engine, SessionStore(tmp_path))
    engine.manual_inputs = {row["physical"]: row for row in adapter["inputs"]
                            if row["physical"].startswith("X")}
    engine.manual_identity = adapter["identity"]
    engine.start_manual_test()
    result = engine.set_x(0, 1)
    assert result["result"] == "已读回"
    assert device.registers[320] == 1 and engine.effective_x[0] == 1
    assert device.registers[0] == 1         # program latched run
    engine.set_x(0, 0)                      # release start; run stays latched
    assert engine.effective_x[0] == 0 and device.registers[0] == 1
    engine.set_x(1, 1)                      # stop dominates
    assert device.registers[321] == 1 and engine.effective_x[1] == 1
    assert device.registers[0] == 0
    engine.disconnect()


def test_priority_project_manual_start_skips_profile_and_injects(tmp_path):
    # V006 起批量接口工程没有会话握手寄存器：开始按钮在工程脚本上必须走
    # start_project_manual（适配器映射直写），接口档案 confirmed 与与否都不拦。
    adapter = project_adapter(PRIORITY)

    class PVDevice(VirtualPLC):
        def run_program(self):
            if self.registers.get(322) == 1:
                self.registers[110] = self.registers.get(330, 0)

    device = PVDevice(DEFAULT_DEMO_PROFILE, version_value=6)
    device.registers.update(dict(adapter["identity"]))
    device.registers[322] = 1
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, transport=LoopbackTransport(device))
    engine.apply_settings(version_address=300)
    BenchWorker(engine, SessionStore(tmp_path))
    engine.start_project_manual({row["physical"]: dict(row) for row in adapter["inputs"]},
                                tuple(adapter["identity"]))
    assert engine.state == State.MANUAL
    result = engine.set_x(0, 1)
    assert result["result"] == "已读回"
    assert device.registers[320] == 1 and engine.effective_x[0] == 1
    result = engine.set_ad_eng(0, "5")        # 引擎 V10 量程：5V → raw 2000
    assert result["result"] == "已读回"
    assert device.registers[330] == 2000 and engine.effective_ad[0] == 2000
    engine.disconnect()


def test_finishing_host_releases_descendant_before_completion(tmp_path):
    script = tmp_path / "spawn.py"
    marker = tmp_path / "leaked.txt"
    body = "import time; time.sleep(2); from pathlib import Path; Path('leaked.txt').write_text('leak'); time.sleep(60)"
    script.write_text("import subprocess,sys\nsubprocess.Popen([sys.executable,'-c'," + repr(body) + "])\n", encoding="utf-8")
    process = ScriptProcess(script, [], tmp_path / "events.jsonl", demo=True)
    started = time.monotonic()
    try:
        assert process_events(process)[-1]["exit_code"] == 0
        assert time.monotonic() - started < 8
        time.sleep(2.2)
        assert not marker.exists()
        assert not process.reader.is_alive() and not process.watcher.is_alive()
    finally:
        process.close()


def test_cancel_drains_all_queued_print_events_before_session_end(tmp_path):
    script = tmp_path / "burst.py"
    script.write_text("import time\nfor i in range(200): print('event-'+str(i), flush=True)\ntime.sleep(60)", encoding="utf-8")
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE)
    engine.apply_settings(demo=True)
    store = SessionStore(tmp_path / "sessions")
    controller = BenchWorker(engine, store).scripts
    controller.start(script, [])
    session_id = store.current_id
    deadline = time.monotonic() + 8
    while controller.process.events.qsize() < 200 and time.monotonic() < deadline:
        time.sleep(0.02)
    controller.close()
    assert store.current_id is None
    events = store.read_events(session_id)
    assert sum(event.get("action") == "脚本输出" for event in events) == 200
    assert engine.state == State.DISCONNECTED


def test_priority_original_script_help_runs_in_host_without_device_access(tmp_path):
    process = ScriptProcess(PRIORITY, ["--help"], tmp_path / "events.jsonl", demo=True)
    try:
        events = process_events(process)
        assert events[-1]["exit_code"] == 0
        assert any("--restart" in event.get("text", "") for event in events)
        assert not any(event["kind"] in ("request", "raw_request", "connection") for event in events)
    finally:
        process.close()


def test_cleanup_failure_still_preserves_queued_events_and_summary(tmp_path, monkeypatch):
    script = tmp_path / "one.py"
    script.write_text("print('保留本条证据', flush=True)", encoding="utf-8")
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE)
    engine.apply_settings(demo=True)
    store = SessionStore(tmp_path / "sessions")
    controller = BenchWorker(engine, store).scripts
    controller.start(script, [])
    process = controller.process
    process.watcher.join(8)
    original_close = process.close

    def injected():
        original_close()
        raise RuntimeError("injected-cleanup-error")

    monkeypatch.setattr(process, "close", injected)
    with pytest.raises(RuntimeError, match="injected-cleanup-error"):
        controller.close()
    assert controller.process is None and store.current_id is None
    summary = store.list_sessions()[0]
    assert summary["script_cleanup_error"] == "injected-cleanup-error"
    assert any(event.get("target") == "保留本条证据" for event in store.read_events(summary["session_id"]))


def test_priority_start_loads_watch_notes_and_clears_for_plain_scripts(tmp_path, monkeypatch):
    from plcweave.bench import script_bridge
    adapter = project_adapter(PRIORITY)
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE)
    engine.apply_settings(demo=True, version_address=300)
    store = SessionStore(tmp_path)
    controller = BenchWorker(engine, store).scripts
    engine.customer_notes = {999: ("旧注释", "")}   # 上一工程残留

    class FakeProcess:
        events = __import__("queue").Queue()
        tree = type("T", (), {"handle": None})()
        reader = type("R", (), {"is_alive": lambda self: False})()
        watcher = type("W", (), {"is_alive": lambda self: False})()

        def __init__(self, *args, **kwargs):
            pass
        def poll(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(script_bridge, "ScriptProcess", FakeProcess)
    controller.start(PRIORITY, [])
    try:
        assert engine.customer_notes == dict(adapter["watch_notes"])
        assert engine.customer_notes[330][1] == "pv_bar"
        assert 334 in engine.customer_watches and 335 in engine.customer_watches
    finally:
        controller.close()
    # 普通脚本（无适配器）启动时清空注释
    plain = tmp_path / "plain.py"
    plain.write_text("print('ok')", encoding="utf-8")
    controller.start(plain, [])
    try:
        assert engine.customer_notes == {}
    finally:
        controller.close()
