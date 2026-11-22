"""Run a user Python test in a child process and publish actual PLC transactions."""
from __future__ import annotations

import argparse
import contextlib
import json
import runpy
import sys
import time
import traceback
import threading
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "PLCWEAVE_SCRIPT_EVENT "


class EventWriter:
    def __init__(self, stream, path: Path) -> None:
        self.stream = stream
        self.file = path.open("x", encoding="utf-8")
        self.sequence = 0
        self.clients = []
        self.lock = threading.Lock()

    def emit(self, kind: str, **values) -> None:
        with self.lock:
            self.sequence += 1
            event = {"kind": kind, "sequence": self.sequence,
                     "wall": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
                     "monotonic_s": time.monotonic(), **values}
            payload = json.dumps(event, ensure_ascii=False)
            self.file.write(payload + "\n")
            self.file.flush()
            self.stream.write(PREFIX + payload + "\n")
            self.stream.flush()

    def close_clients(self) -> list[str]:
        errors = []
        for client in self.clients:
            try:
                client.close()
            except Exception as exc:
                errors.append(str(exc))
        return errors


class ScriptOutput:
    """Capture script print output inside the child without redirecting the GUI."""
    encoding = "utf-8"

    def __init__(self, events: EventWriter, source: str) -> None:
        self.events = events
        self.source = source
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text
        while "\n" in self.pending or len(self.pending) >= 8192:
            length = self.pending.find("\n")
            length = length if 0 <= length < 8192 else 8192
            line, self.pending = self.pending[:length], self.pending[length:]
            self.pending = self.pending.removeprefix("\n")
            self.events.emit("output", source=self.source, text=line)
        return len(text)

    def flush(self) -> None:
        if self.pending:
            self.events.emit("output", source=self.source, text=self.pending)
            self.pending = ""

    def isatty(self) -> bool:
        return False


def observe_client(inner, events: EventWriter, *, connection: dict, family: str):
    """Proxy the original return values and errors, including failed transactions."""
    events.clients.append(inner)
    methods = {
        "read_holding_registers": ("read", "D", False),
        "read_input_registers": ("read", "input_register", False),
        "read_coils": ("read", "coil", True),
        "read_discrete_inputs": ("read", "input", True),
        "write_register": ("write", "D", False),
        "write_registers": ("write", "D", False),
        "write_coil": ("write", "coil", True),
        "write_coils": ("write", "coil", True),
        "read_words": ("read", "D", False),
        "read_bits": ("read", "coil", True),
        "write_word": ("write", "D", False),
        "write_words": ("write", "D", False),
    }

    def wrap_method(name, original, specification):
        operation, initial_area, bits = specification

        def transact(*args, **kwargs):
            area = initial_area
            position = 0
            if name == "read_bits":
                function = args[0] if args else kwargs["function"]
                area = "input" if function == 2 else "coil"
                position = 1
            address = args[position] if len(args) > position else kwargs["address"]
            count = kwargs.get("count", args[position + 1] if len(args) > position + 1 else 1)
            values = None
            if operation == "write":
                value = args[1] if len(args) > 1 else kwargs.get("value", kwargs.get("values"))
                values = list(value) if isinstance(value, (list, tuple)) else [int(value)]
                count = len(values)
            station = getattr(inner, "station", connection.get("station", 1))
            endpoint = {**connection, "station": kwargs.get("device_id", kwargs.get("slave", station))}
            detail = {"operation": operation, "method": name, "area": area,
                      "address": address, "count": count, "values": values,
                      "connection": endpoint}
            events.emit("request", **detail)
            started = time.monotonic()
            try:
                result = original(*args, **kwargs)
            except BaseException as exc:
                events.emit("response", **detail, success=False, error=str(exc),
                            duration_ms=(time.monotonic() - started) * 1000)
                raise
            success = not result.isError() if hasattr(result, "isError") else True
            observed = None
            if success and operation == "read":
                observed = list(result) if family == "rtu" else list(
                    getattr(result, "bits" if bits else "registers", []))[:count]
            events.emit("response", **{**detail, "values": observed if operation == "read" else values},
                        success=success, error=None if success else str(result),
                        duration_ms=(time.monotonic() - started) * 1000)
            return result
        return transact

    for name, specification in methods.items():
        if hasattr(inner, name):
            setattr(inner, name, wrap_method(name, getattr(inner, name), specification))
    if hasattr(inner, "connect"):
        original_connect = inner.connect

        def connect(*args, **kwargs):
            result = original_connect(*args, **kwargs)
            events.emit("connection", **connection, connected=bool(result))
            return result
        inner.connect = connect
    return inner


def install_observers(events: EventWriter, *, demo: bool) -> None:
    from . import rtu
    original_rtu = rtu.RtuClient

    class ObservedRtuClient(original_rtu):
        def __init__(self, transport, station, **kwargs):
            super().__init__(transport, station, **kwargs)
            connection = {"station": station, "port": getattr(transport, "port", "loopback"),
                          "baud": getattr(transport, "baudrate", 9600),
                          "parity": getattr(transport, "parity", "N"),
                          "stopbits": getattr(transport, "stopbits", 1),
                          "bytesize": getattr(transport, "bytesize", 8)}
            observe_client(self, events, connection=connection, family="rtu")

    rtu.RtuClient = ObservedRtuClient
    sys.modules["plcweave.bench"].RtuClient = ObservedRtuClient
    if demo:
        # Demo scripts may use LoopbackTransport, while physical serial opens fail closed.
        def reject_serial(*args, **kwargs):
            raise PermissionError("演示脚本仅允许回环通讯，请切换实机模式执行硬件脚本")
        rtu.SerialTransport = reject_serial
    else:
        try:
            import serial
        except ImportError:
            serial = None
        if serial is not None:
            original_serial = serial.Serial

            class ObservedSerial(original_serial):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    events.clients.append(self)

                def write(self, data):
                    events.emit("raw_request", port=self.port, hex=bytes(data).hex())
                    try:
                        result = super().write(data)
                    except BaseException as exc:
                        events.emit("raw_response", port=self.port, success=False, error=str(exc))
                        raise
                    events.emit("raw_response", port=self.port, success=True, sent=result)
                    return result

                def read(self, size=1):
                    data = super().read(size)
                    events.emit("raw_read", port=self.port, hex=data.hex(), count=len(data))
                    return data

            serial.Serial = ObservedSerial
    try:
        import pymodbus.client
        import pymodbus.client.serial
    except ImportError:
        return
    original_modbus = pymodbus.client.ModbusSerialClient

    class ObservedModbusClient(original_modbus):
        def __init__(self, *args, **kwargs):
            if demo:
                raise PermissionError("演示模式请选择内置脚本或使用 LoopbackTransport 的脚本")
            super().__init__(*args, **kwargs)
            connection = {"port": kwargs.get("port", args[0] if args else ""),
                          "baud": kwargs.get("baudrate", 19200), "bytesize": kwargs.get("bytesize", 8),
                          "parity": kwargs.get("parity", "N"), "stopbits": kwargs.get("stopbits", 1)}
            observe_client(self, events, connection=connection, family="pymodbus")

    pymodbus.client.ModbusSerialClient = ObservedModbusClient
    pymodbus.client.serial.ModbusSerialClient = ObservedModbusClient


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--wait-start", action="store_true")
    parser.add_argument("script", type=Path)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.wait_start and sys.stdin.readline().strip() != "START":
        return 1
    script = args.script.resolve(strict=True)
    writer = EventWriter(sys.stdout, args.events)
    out, err = ScriptOutput(writer, "stdout"), ScriptOutput(writer, "stderr")
    code = 0
    try:
        install_observers(writer, demo=args.demo)
        if args.demo:
            # Demo mode must not require the optional HIL dependency: pyserial is only used
            # here to fail physical port opens closed. Without it the import simply fails.
            try:
                import serial
            except ImportError:
                serial = None
            if serial is not None:
                def deny_serial(*args, **kwargs):
                    raise PermissionError("演示模式禁止打开物理串口")
                serial.Serial = deny_serial
        sys.argv = [str(script), *args.args]
        sys.path.insert(0, str(script.parent))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                runpy.run_path(str(script), run_name="__main__")
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0 if exc.code is None else 1
                if not isinstance(exc.code, (int, type(None))):
                    print(exc.code, file=sys.stderr)
            except BaseException:
                code = 1
                traceback.print_exc()
    except Exception:
        code = 1
        err.write(traceback.format_exc())
    finally:
        try:
            out.flush()
            err.flush()
            errors = writer.close_clients()
            code = code or (1 if errors else 0)
            writer.emit("finished", exit_code=code, cleanup_errors=errors)
        finally:
            writer.file.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
