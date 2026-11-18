"""Child-process script execution and protocol telemetry for the desktop window."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from .script_host import PREFIX
from .process_tree import ProcessTree
from .script_projects import project_adapter, prepare_arguments


class ScriptProcess:
    def __init__(self, script: Path, args: list[str], events_path: Path, *, demo: bool):
        self.script = script.resolve(strict=True)
        if self.script.suffix.lower() != ".py":
            raise ValueError("请选择 Python .py 测试脚本")
        self.events: queue.Queue = queue.Queue()
        self.cancelled = False
        command = [sys.executable, "-u", "-m", "plcweave.bench.script_host",
                   "--events", str(events_path.resolve()), "--wait-start"]
        if demo:
            command.append("--demo")
        command.extend([str(self.script), *args])
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        source = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [source, env.get("PYTHONPATH")]))
        self.tree = ProcessTree()
        try:
            self.process = subprocess.Popen(
                command, cwd=self.script.parent, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.tree.assign(self.process)
            self.process.stdin.write("START\n")
            self.process.stdin.close()
        except BaseException:
            if hasattr(self, "process"):
                self.process.kill()
                self.process.wait(timeout=3)
            self.tree.close()
            raise
        self.reader = threading.Thread(target=self._read, name="bench-script-output", daemon=True)
        self.reader.start()
        self.watcher = threading.Thread(target=self._wait, name="bench-script-owner", daemon=True)
        self.watcher.start()

    def _read(self):
        try:
            with self.process.stdout as stream:
                for line in stream:
                    if line.startswith(PREFIX):
                        try:
                            event = json.loads(line[len(PREFIX):])
                        except json.JSONDecodeError:
                            event = {"kind": "output", "source": "host", "text": line.rstrip()}
                    else:
                        event = {"kind": "output", "source": "host", "text": line.rstrip()}
                    self.events.put(event)
        except OSError as exc:
            self.events.put({"kind": "output", "source": "host", "text": str(exc)})

    def _wait(self):
        code = self.process.wait()
        # A child may have inherited stdout or kept a serial port open. Terminate the
        # owned tree before awaiting EOF, then publish the only completion event.
        try:
            self.tree.terminate()
            self.tree.wait_empty()
            self.tree.close()
            self.reader.join(timeout=3)
            if self.reader.is_alive():
                raise RuntimeError("脚本输出线程未退出，禁止手动接管")
        except (OSError, RuntimeError) as exc:
            self.events.put({"kind": "cleanup_failed", "error": str(exc)})
            return
        self.events.put({"kind": "process_exit", "exit_code": code, "cancelled": self.cancelled})

    def close(self):
        if self.process.poll() is None:
            self.cancelled = True
            self.tree.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.watcher.join(timeout=5)
        self.tree.terminate()
        self.tree.wait_empty()
        self.tree.close()
        self.reader.join(timeout=3)
        if self.watcher.is_alive() or self.reader.is_alive():
            raise RuntimeError("脚本及其子进程仍未释放")


def input_mapping(script: Path) -> list[dict]:
    """Read a generated workflow's original input table when available."""
    from ..variants import read_design

    adapter = project_adapter(script)
    if adapter:
        return adapter["inputs"]

    candidates = (script.parent / "design.md", script.parent.parent.parent / "design.md")
    for path in candidates:
        if path.is_file():
            try:
                return read_design(path)["inputs"]
            except (ValueError, OSError):
                continue
    return []


def device_values(area: str, address: int, values: list) -> dict[str, int]:
    if area == "D":
        return {f"D{address + index}": int(value) for index, value in enumerate(values)}
    if area == "input":
        return {f"X{address + index - 0x3400:o}": int(value)
                for index, value in enumerate(values) if 0x3400 <= address + index <= 0x347F}
    if area == "coil":
        result = {}
        for index, value in enumerate(values):
            word = address + index
            if 0x3300 <= word <= 0x337F:
                result[f"Y{word - 0x3300:o}"] = int(value)
            elif 0 <= word <= 7679:
                result[f"M{word}"] = int(value)
            elif 0x1E00 <= word <= 0x1FFF:
                result[f"M{8000 + word - 0x1E00}"] = int(value)
        return result
    return {}


class ScriptController:
    """Serialize script telemetry and the manual handoff on the bench worker."""
    def __init__(self, engine, store):
        self.engine = engine
        self.store = store
        self.process: ScriptProcess | None = None
        self.waiting_confirmation = False
        self.connection: dict | None = None
        self.mapping: list[dict] = []
        self.command_count = 0
        self.script_finished = False
        self.written: set[str] = set()
        self.generation = 0
        self.report_status = None
        self.adapter = {}

    def start(self, script: str | Path, args: list[str], version_address=None) -> None:
        from .engine import State
        script = Path(script).resolve(strict=True)
        if self.process is not None or self.waiting_confirmation:
            raise PermissionError("请先确认本次测试结束")
        adapter = project_adapter(script)
        args = prepare_arguments(script, args)
        self.engine.disconnect("转入脚本测试")
        self.adapter = adapter
        if adapter:
            self.engine.settings["version_address"] = adapter["version_address"]
        elif version_address is not None:
            self.engine.settings["version_address"] = version_address
        elif self.engine.settings["demo"]:
            self.engine.settings["version_address"] = 196
        self.engine.manual_identity = tuple(adapter.get("identity", ()))
        self.engine.manual_inputs = {}
        self.report_status = None
        if adapter:
            self.engine.customer_watches.clear()
            names_en = adapter.get("watch_names_en", {})
            for address, name, access, low, high in adapter["watches"]:
                self.engine.set_customer_watch(address, name, access, low, high,
                                               name_en=names_en.get(address))
        self.engine.customer_notes = dict(adapter.get("watch_notes", {}))
        self.engine.customer_notes_en = dict(adapter.get("watch_notes_en", {}))
        self.engine.io_labels = dict(adapter.get("io", {}))
        self.connection = None
        self.mapping = input_mapping(script)
        self.command_count = 0
        self.script_finished = False
        self.written.clear()
        self.generation += 1
        self.engine.record("start", {**self.engine._session_snapshot_config(),
                                     "source": "python_script", "script": str(script), "args": args,
                                     "port": None, "station": None, "baud": None, "format": None,
                                     "version_address": self.engine.settings["version_address"],
                                     "script_adapter": adapter.get("name"),
                                     "script_source_sha256": adapter.get("source_sha256")})
        self.engine._recording = True
        self.engine.log_op("user", script.name, "启动测试脚本", target=args, result="运行中")
        self.engine.state = State.SCRIPT_RUNNING
        self.engine._emit("state", state=self.engine.state)
        try:
            self.process = ScriptProcess(script, args, self.store.attachment_path("script-transactions.jsonl"),
                                         demo=self.engine.settings["demo"])
        except (OSError, ValueError) as exc:
            self.engine.log_op("system", script.name, "脚本启动失败", result="失败", reason=str(exc))
            self._finish(1, error=str(exc))

    def poll(self) -> None:
        if self.process is None:
            return
        for _ in range(64):
            try:
                event = self.process.events.get_nowait()
            except queue.Empty:
                break
            self._consume(event)
            if self.process is None:
                break

    def _consume(self, event: dict) -> None:
        from .engine import State
        engine = self.engine
        kind = event.get("kind")
        if kind == "connection" and event.get("connected"):
            engine.log_op("script", str(event.get("port")), "脚本连接", detail=event)
        elif kind == "output":
            engine.log_op("script", event.get("source", "stdout"), "脚本输出", target=event.get("text", ""))
            try:
                report = json.loads(event.get("text", ""))
                if isinstance(report, dict) and isinstance(report.get("status"), str):
                    self.report_status = report["status"]
                    engine.record("update", {"script_report": report})
            except (ValueError, TypeError):
                pass
        elif kind in ("raw_request", "raw_response", "raw_read"):
            engine.log_op("script", str(event.get("port")), "原始串口收发",
                          target=event.get("hex"), result="失败" if event.get("success") is False else "已记录",
                          reason=event.get("error"), detail=event)
        elif kind in ("request", "response"):
            area, address = event["area"], event["address"]
            count = event["count"]
            obj = f"D{address}" if area == "D" else f"{area}@{address}"
            if count > 1:
                obj += f" (+{count - 1})"
            operation = event["operation"]
            values = event.get("values") or []
            result = "已发送" if kind == "request" else "读回" if operation == "read" else "写入响应"
            if kind == "response" and not event.get("success"):
                result = "失败"
            engine.log_op("script", obj, "脚本读取" if operation == "read" else "脚本写入",
                          target=values if kind == "request" else None,
                          effective=values if kind == "response" and event.get("success") else None,
                          result=result, reason=event.get("error"), detail=event)
            if kind == "request":
                self.command_count += 1
            endpoint = event.get("connection", {})
            if self.connection and endpoint.get("port") != self.connection.get("port"):
                return
            if self.connection and self.connection.get("station") is not None and endpoint.get("station") != self.connection["station"]:
                return
            if self.connection is None:
                if kind != "response" or not event.get("success"):
                    return
                self.connection = endpoint
                engine._emit("script_connection", settings=self.connection)
                engine.record("update", {"port": endpoint.get("port"), "baud": endpoint.get("baud"),
                    "station": endpoint.get("station"),
                    "format": f"{endpoint.get('bytesize', 8)}{endpoint.get('parity', 'N')}{endpoint.get('stopbits', 1)}"})
            if kind == "request":
                if operation == "write":
                    for device, value in device_values(area, address, values).items():
                        if area == "D":
                            word = int(device[1:])
                            if word in engine.profile.x_command:
                                engine.target_x[engine.profile.x_command.index(word)] = int(bool(value))
                            if word in engine.profile.ad_command:
                                engine.target_ad_raw[engine.profile.ad_command.index(word)] = value
                        for row in self.mapping:
                            if row["injection"] == device:
                                self._input_value(row["physical"], value, target=True)
                        if area == "D" and 0 <= int(device[1:]) <= 7999 and len(engine.customer_watches) < 32:
                            if int(device[1:]) not in engine.customer_watches:
                                engine.set_customer_watch(int(device[1:]), f"脚本 {device}")
                    engine._emit("script_targets")
            elif event.get("success") and operation == "read":
                self._observed(device_values(area, address, values), event.get("wall"))
            elif event.get("success") and operation == "write":
                self.written.update(device_values(area, address, values))
        elif kind == "finished":
            self.script_finished = True
            engine.record("update", {"script_finish": event})
        elif kind == "cleanup_failed":
            engine.log_op("system", "Python", "脚本清理失败", result="失败", reason=event["error"])
            engine.record("update", {"script_cleanup_error": event["error"]})
            engine._fail(event["error"])
        elif kind == "process_exit":
            code = event["exit_code"]
            self.process.close()
            self.process = None
            self._finish(code if self.script_finished else code or 1,
                         error="用户中止" if event.get("cancelled") else None)
        if engine.state == State.SCRIPT_RUNNING:
            engine._emit("values")

    def _input_value(self, physical: str, value: int, *, target=False):
        engine = self.engine
        if physical.startswith("X"):
            index = int(physical[1:], 8)
            if index < 8:
                if target:
                    engine.target_x[index] = int(bool(value))
                else:
                    engine.effective_x[index] = int(bool(value))
        elif physical.startswith("D") and 8030 <= int(physical[1:]) <= 8033:
            index = int(physical[1:]) - 8030
            if target:
                engine.target_ad_raw[index] = value & 65535
            else:
                engine.effective_ad[index] = value & 65535

    def _observed(self, values: dict, wall):
        engine = self.engine
        now = time.time()
        for device, value in values.items():
            if device.startswith("Y"):
                index = int(device[1:], 8)
                if index < 8:
                    engine.y_bits[index] = value
                    engine.block_times["y"] = now
            if device.startswith("X"):
                index = int(device[1:], 8)
                if index < 8:
                    engine.hw_x[index] = value
            if device.startswith("D"):
                address = int(device[1:])
                raw = value & 65535
                if 8050 <= address <= 8051:
                    engine.da_raw[address - 8050] = raw
                    engine.block_times["da"] = now
                if 8030 <= address <= 8033:
                    engine.hw_ad[address - 8030] = raw
                    if not any(row["physical"] == device for row in self.mapping):
                        engine.effective_ad[address - 8030] = raw
                if address == engine.settings["version_address"]:
                    engine.version_value, engine.version_address = raw, address
                    engine.record("update", {"version_address": f"D{address}", "version_value": raw})
                    engine._emit("state", state=engine.state)
                if address in engine.customer_watches:
                    permission = engine.customer_permission(address)
                    engine.customer_samples[address] = {
                        "raw": raw, "value": permission.decode(raw) if permission else raw,
                        "wall": wall or engine._now_wall()}
                for index, word in enumerate(engine.profile.x_effective):
                    if address == word:
                        engine.effective_x[index] = int(bool(raw))
                for index, word in enumerate(engine.profile.ad_effective):
                    if address == word:
                        engine.effective_ad[index] = raw
            for row in self.mapping:
                if row["logical"] == device:
                    self._input_value(row["physical"], value)
        engine._emit_customer_values()
        engine.record("sample", engine.sample_snapshot())

    def _finish(self, code: int, *, error=None):
        from .engine import State
        self.exit_code = code
        self.engine.log_op("system", "Python", "脚本测试结束", target=code,
                           result="已结束" if code == 0 else "执行失败", reason=error)
        self.engine.record("update", {"script_exit_code": code, "command_count": self.command_count})
        failed = code != 0 or self.report_status in ("PROGRAM_FAIL", "TEST_INFRA_ERROR", "FAIL", "FAILED", "ERROR")
        self.engine.record("end", {"status": "异常中断" if failed else "正常结束",
                                   "end_reason": "脚本执行结束", "error": error})
        self.engine._recording = False
        self.waiting_confirmation = True
        self.engine.state = State.SCRIPT_CONFIRM
        self.engine._emit("state", state=self.engine.state)
        self.engine._emit("script_complete", exit_code=code, generation=self.generation,
                          command_count=self.command_count, report_status=self.report_status)

    def acknowledge(self, generation: int):
        from .engine import State
        if not self.waiting_confirmation or generation != self.generation:
            return
        self.waiting_confirmation = False
        self.engine.state = State.DISCONNECTED
        self.engine._emit("state", state=self.engine.state)
        if self.connection:
            data = self.connection
            if not self.engine.settings["demo"]:
                self.engine.apply_settings(
                    port=data["port"], baud=data.get("baud", 9600),
                    format=f"{data.get('bytesize', 8)}{data.get('parity', 'N')}{data.get('stopbits', 1)}",
                    station=data.get("station", 1))
            if self.engine.settings["demo"]:
                self.engine.start_simulation()
            else:
                self.engine.manual_inputs = {
                    row["physical"]: row for row in self.mapping
                    if row["injection"] in self.written
                    and (row["physical"] in {f"X{i}" for i in range(8)}
                         or row["physical"] in {f"D{8030+i}" for i in range(4)})}
                self.engine.start_manual_test()

    def close(self):
        from .engine import State
        owns_record = self.engine.state in (State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM)
        cleanup_error = None
        try:
            if self.process:
                process = self.process
                try:
                    process.close()
                except (OSError, RuntimeError) as exc:
                    cleanup_error = str(exc)
                    self.engine.log_op("system", "Python", "脚本清理失败", result="失败", reason=cleanup_error)
                finally:
                    while True:
                        try:
                            event = process.events.get_nowait()
                        except queue.Empty:
                            break
                        if event.get("kind") != "process_exit":
                            self._consume(event)
                    if not process.reader.is_alive() and not process.watcher.is_alive() and process.tree.handle is None:
                        self.process = None
        finally:
            if owns_record and self.engine._recording:
                self.engine.record("end", {"status": "异常中断", "end_reason": "用户关闭脚本测试",
                                           "script_cleanup_error": cleanup_error})
            if owns_record:
                self.engine._recording = False
            self.waiting_confirmation = False
            if self.engine.state in (State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM):
                self.engine.state = State.DISCONNECTED
        if cleanup_error:
            raise RuntimeError(cleanup_error)
