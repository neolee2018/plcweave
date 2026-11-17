"""仿真台核心引擎：连接/会话状态机、工程换算、组提交与操作日志。

本模块与 GUI/线程无关：所有方法同步执行，需要已就绪的传输层。
GUI 通过 worker 线程序列化调用（见 app.py）；测试直接调用方法。

状态机与 PRD §4.4 一致：
  DISCONNECTED → CONNECTING → CONNECTED → STARTING → SIMULATING → ENDING
  任何通讯故障 → FAULT（禁止发送、不重放积压，须用户重连）。

写边界：
- 仅接口档案白名单内的会话/注入寄存器可写（contract.check_write_allowed）；
- Y/X硬件/D8050 等只读地址从不写入；
- 版本地址只读；写设备前先落盘操作意图（record 钩子）。
"""
from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .contract import (
    AD_HW_BASE,
    DA_HW_BASE,
    D_MAX,
    CustomerRegister,
    InterfaceProfile,
    USER_D_MAX,
    X_INPUT_BASE,
    Y_COIL_BASE,
    group_checksum,
    validate_version_address,
)
from .rtu import ModbusError, RtuClient, SerialTransport, SlaveException

FULL_RAW = 4000          # 默认 L01S 普通模拟量定标 0–4000（PRD §6.1）
RANGE_KINDS = ("V10", "MA20")
RANGE_LABELS = {"V10": "0–10V", "MA20": "0–20mA"}
UNIT_LABELS = {"V10": "V", "MA20": "mA"}
BAUD_RATES = (600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200)
FORMAT_CHOICES = ("8N1", "8N2", "8E1", "8O1", "8E2", "8O2")

ACK_TIMEOUT_S = 2.0        # 组提交等待消费确认上限
END_TIMEOUT_S = 5.0        # 结束清理等待上限（PRD §8.3）
HEARTBEAT_PERIOD_MS = 500  # PC 心跳设计初值（PRD §8.3）
MAX_CUSTOMER_WATCHES = 40
DEMO_CUSTOMER_REGISTER = CustomerRegister(260, 0, 4000)

# 客户寄存器监控条目的权限：读 / 写 / 既读又写（用户 V0.4.2 指令）。
# “只写”= 只允许发送命令，不轮询读取；“读写”= 轮询读取 + 可发送。
CUSTOMER_ACCESS_MODES = ("只读", "只写", "读写")
_ACCESS_ALIASES = {
    "只读": "只读", "ro": "只读", "r": "只读", "read": "只读",
    "只写": "只写", "wo": "只写", "w": "只写", "write": "只写",
    "读写": "读写", "rw": "读写", "r/w": "读写", "w/r": "读写",
    "read/write": "读写", "读/写": "读写", "读,写": "读写", "写,读": "读写",
}


@dataclass(frozen=True)
class CustomerWatch:
    """监控列表条目：名称 + 权限 + 可选写入范围（CSV 可给，档案范围优先）。"""

    name: str
    access: str = "读写"
    minimum: int | None = None
    maximum: int | None = None


def normalize_customer_access(text: str) -> str | None:
    """权限列归一化；无法识别返回 None。"""
    return _ACCESS_ALIASES.get(text.strip().lower())


class RecordingError(OSError):
    """会话日志无法落盘。"""


# ---- 工程换算 --------------------------------------------------------------
def clamp_raw(raw: int) -> int:
    return max(0, min(FULL_RAW, int(raw)))


def eng_from_raw(raw: int, kind: str) -> float:
    if kind not in RANGE_KINDS:
        raise ValueError(f"未知量程类型: {kind}")
    scale = 10.0 if kind == "V10" else 20.0
    return raw / FULL_RAW * scale


def raw_from_eng(eng: float, kind: str) -> int:
    if kind not in RANGE_KINDS:
        raise ValueError(f"未知量程类型: {kind}")
    scale = 10.0 if kind == "V10" else 20.0
    if eng < 0 or eng > scale:
        raise ValueError(f"数值 {eng} 超出量程 {RANGE_LABELS[kind]}")
    return clamp_raw(round(eng / scale * FULL_RAW))


def step_eng(kind: str, step_pct: int) -> float:
    """满量程百分比步长对应工程增量（PRD §6.3 表）。"""
    if not 1 <= step_pct <= 10:
        raise ValueError("步长必须为 1–10 的整数百分比")
    scale = 10.0 if kind == "V10" else 20.0
    return scale * step_pct / 100.0


def format_parse(fmt: str) -> dict:
    """'8N1' → {'bytesize':8,'parity':'N','stopbits':1}；拒绝 7 位格式。"""
    if fmt not in FORMAT_CHOICES:
        raise ValueError(f"不支持的数据格式: {fmt}（首版 RTU 仅 8 数据位）")
    return {"bytesize": 8, "parity": fmt[1], "stopbits": int(fmt[2])}


# ---- 状态 ------------------------------------------------------------------
class State:
    DISCONNECTED = "未连接"
    CONNECTING = "连接中"
    CONNECTED = "已连接·未仿真"
    STARTING = "仿真启动中"
    SIMULATING = "仿真中"
    ENDING = "结束中"
    FAULT = "故障/断线"
    SCRIPT_RUNNING = "脚本测试中"
    SCRIPT_CONFIRM = "测试完毕·待确认"
    MANUAL = "手动测试"


class BenchEngine:
    """同步引擎。`record` 为存储钩子（可为 None）；`sink` 为 UI 事件回调。"""

    def __init__(self, *, profile: InterfaceProfile, sink: Callable[[dict], None] | None = None,
                 record: Callable[[str, dict], None] | None = None,
                 transport=None) -> None:
        self.profile = profile
        self.sink = sink
        self.record = record
        errors = profile.validate()
        if errors:
            raise ValueError("接口档案不可用: " + "; ".join(errors))
        self.state = State.DISCONNECTED
        self.last_error: str | None = None
        self.client: RtuClient | None = None
        self.transport = transport            # 允许注入回环传输（演示/测试）
        self.owns_transport = False
        # 连接配置（GUI 填充）
        self.settings = {"port": "", "baud": 9600, "format": "8N1", "station": 1,
                         "version_address": None, "demo": False}
        # 会话/观察数据
        self.version_value: int | None = None
        self.version_address: int | None = None
        self.y_bits: list[int | None] = [None] * 8
        self.da_raw: list[int | None] = [None, None]
        self.hw_x: list[int | None] = [None] * 8
        self.hw_ad: list[int | None] = [None] * 4
        self.effective_x: list[int | None] = [None] * 8
        self.effective_ad: list[int | None] = [None] * 4
        self.target_x: list[int] = [0] * 8
        self.target_ad_raw: list[int] = [0] * 4
        self.ad_range: list[str] = ["V10"] * 4
        self.da_range: list[str] = ["V10"] * 2
        self.step_pct = 5
        self.session_token = 0
        self.last_seq = 0
        self.in_flight: int | None = None     # 未确认组序号（一次只提交一组）
        self.session_active = False
        self._session_snapshot: dict = {}
        self.x_mode = "保持开关"              # 保持开关 | 按住有效
        self.block_times: dict[str, float | None] = {"y": None, "da": None,
                                                     "mirror": None, "session": None,
                                                     "hw_x": None, "hw_ad": None}
        self.last_roundtrip_ms: dict[str, float | None] = {}
        self.last_poll_ms: float | None = None
        self.customer_watches: dict[int, str] = {}
        # 工程适配器提供的注释/归一化：地址 -> (单位量程注释, 归一化类型)
        self.customer_notes: dict[int, tuple[str, str]] = {}
        self.customer_samples: dict[int, dict] = {}
        self.manual_inputs: dict[str, dict] = {}
        self.manual_identity: tuple[tuple[int, int], ...] = ()
        self._events: list[dict] = []
        self._seq = 0
        self._recording = False   # 会话记录进行中（开始仿真到结束/断开）
        self._t0 = time.monotonic()
        self._hb_counter = 0
        self._hb_written = 0.0

    # ---- 日志 ------------------------------------------------------------
    def _now_wall(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")

    def log_op(self, actor: str, obj: str, action: str, *, target=None, effective=None,
               unit=None, range_kind=None, step=None, result="成功", reason=None,
               detail=None) -> dict:
        self._seq += 1
        event = {
            "seq": self._seq,
            "wall": self._now_wall(),
            "mono_ms": round((time.monotonic() - self._t0) * 1000, 1),
            "actor": actor, "object": obj, "action": action,
            "target": target, "effective": effective, "unit": unit,
            "range_kind": range_kind, "step_pct": step,
            "result": result, "reason": reason, "detail": detail,
        }
        self._events.append(event)
        self.record and self.record("event", event)
        self.sink and self.sink({"type": "op", "event": event})
        return event

    @property
    def events(self) -> list[dict]:
        return list(self._events)

    def _emit(self, kind: str, **payload) -> None:
        self.sink and self.sink({"type": kind, **payload})

    def _fail(self, message: str) -> None:
        self.last_error = message
        self._emit("error", message=message)

    # ---- 配置 ------------------------------------------------------------
    def apply_settings(self, *, port=None, baud=None, format=None, station=None,
                       version_address=None, demo=None) -> list[str]:
        """校验并应用本机设置；连接/仿真期间锁定（返回警告列表）。"""
        warnings: list[str] = []
        if self.state not in (State.DISCONNECTED, State.FAULT):
            raise PermissionError("连接期间设置锁定；请先断开再修改")
        if port is not None:
            if not self.settings["demo"] and not str(port):
                raise ValueError("未选择串口")
            self.settings["port"] = str(port)
        if baud is not None:
            if baud not in BAUD_RATES:
                raise ValueError(f"不支持的波特率: {baud}")
            self.settings["baud"] = baud
        if format is not None:
            format_parse(format)  # 校验
            self.settings["format"] = format
        if station is not None:
            if type(station) is not int or not 1 <= station <= 247:
                raise ValueError("从机地址必须为 1..247（不使用广播 0，不改写 PLC 站号）")
            self.settings["station"] = station
        if version_address is not None:
            try:
                validate_version_address(version_address)
            except ValueError as exc:
                raise ValueError(f"版本寄存器: {exc}") from exc
            self.settings["version_address"] = version_address
        if demo is not None:
            self.settings["demo"] = bool(demo)
        return warnings

    def _require_version_address(self) -> int:
        address = self.settings["version_address"]
        if address is None:
            raise ValueError("版本寄存器未设置：须填写目标程序实际维护的版本地址")
        return address

    # ---- 连接 ------------------------------------------------------------
    def connect(self) -> None:
        if self.state not in (State.DISCONNECTED, State.FAULT):
            raise PermissionError(f"当前状态 {self.state} 不允许连接")
        self.state = State.CONNECTING
        self._emit("state", state=self.state)
        self.last_error = None
        self.customer_samples.clear()
        try:
            address = self._require_version_address()
            self._open_transport()
            assert self.client is not None
            version = self.client.read_words(address, 1)[0]
            self.version_value, self.version_address = version, address
            self.log_op("system", f"D{address}", "读取程序版本", target=version,
                        unit="原始版本数", result="成功")
            if self._recording:
                # 自动连接流程中的版本快照补录进当前会话（PRD §9.1）。
                self.record and self.record("update", {
                    "version_value": version, "version_address": f"D{address}"})
            self._observe_outputs(initial=True)
            self.state = State.CONNECTED
            self._emit("state", state=self.state, version=version,
                       version_address=f"D{address}")
        except RecordingError:
            raise
        except (ModbusError, ValueError, OSError) as exc:
            self._teardown_transport()
            self.version_value = None
            self.version_address = None
            self.state = State.DISCONNECTED
            self._emit("state", state=self.state)
            self.log_op("system", "连接", "连接失败", result="失败", reason=str(exc))
            self._fail(f"连接失败: {exc}")
            raise ConnectionError(f"连接失败: {exc}") from exc
        self._emit_customer_values()

    def _open_transport(self) -> None:
        if self.transport is None:
            if self.settings["demo"]:
                raise ValueError("演示模式必须注入回环传输层")
            fmt = format_parse(self.settings["format"])
            self.transport = SerialTransport(
                self.settings["port"], baudrate=self.settings["baud"],
                parity=fmt["parity"], bytesize=fmt["bytesize"], stopbits=fmt["stopbits"])
            self.owns_transport = True
            self.transport.open()
        self.client = RtuClient(self.transport, self.settings["station"], timeout=0.5)

    def _teardown_transport(self) -> None:
        self.client = None
        if self.owns_transport and self.transport is not None:
            # 只清理本引擎创建的传输；注入的回环传输保留复用。
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None
            self.owns_transport = False

    def disconnect(self, reason="用户断开") -> None:
        if self.state == State.SIMULATING:
            self.stop_simulation(reason)
        elif self.session_active:
            self._end_session_locked(reason)
        if self._recording:
            self.record and self.record("end", {"status": "异常中断",
                                                "end_reason": f"断开结束（{reason}）"})
            self._recording = False
        self._teardown_transport()
        self.state = State.DISCONNECTED
        self.version_value = None
        self.version_address = None
        self.y_bits = [None] * 8
        self.da_raw = [None, None]
        self.hw_x = [None] * 8
        self.hw_ad = [None] * 4
        self.effective_x = [None] * 8
        self.effective_ad = [None] * 4
        self.customer_samples.clear()
        self.block_times = {key: None for key in self.block_times}
        self.last_error = None
        self._emit("state", state=self.state)
        self.log_op("system", "连接", "断开", result="成功", reason=reason)
        self._emit("values", stale=True)
        self._emit_customer_values()

    # ---- 输出/诊断观察 ------------------------------------------------------
    def _observe_outputs(self, initial: bool = False) -> None:
        client = self.client
        assert client is not None
        started = time.monotonic()
        self.y_bits = client.read_bits(1, Y_COIL_BASE, 8)
        self.block_times["y"] = time.time()
        self.last_roundtrip_ms["y"] = client.last_roundtrip_ms
        self.da_raw = client.read_words(DA_HW_BASE, 2)
        self.block_times["da"] = time.time()
        self.last_roundtrip_ms["da"] = client.last_roundtrip_ms
        self.hw_x = client.read_bits(2, X_INPUT_BASE, 8)
        self.block_times["hw_x"] = time.time()
        self.hw_ad = client.read_words(AD_HW_BASE, 4)
        self.block_times["hw_ad"] = time.time()
        if not initial:
            self.last_poll_ms = round((time.monotonic() - started) * 1000, 1)
        self._emit("values")

    def poll(self) -> None:
        """常规只读轮询（已连接或仿真中）。失败进入 FAULT。"""
        if self.state not in (State.CONNECTED, State.SIMULATING, State.MANUAL):
            return
        try:
            self._observe_outputs()
            block = None
            if self.state in (State.CONNECTED, State.SIMULATING, State.MANUAL) and self.customer_watches:
                readable = sorted(address for address, watch in self.customer_watches.items()
                                  if "读" in watch.access)
                if readable:
                    block = self._read_customers_batch(readable)
            if self.state == State.SIMULATING:
                self._read_session_blocks()
            elif self.state == State.MANUAL:
                self._read_manual_inputs(block=block)
        except ModbusError as exc:
            self._enter_fault(f"通讯失败: {exc}")
            return
        if self.state != State.FAULT:
            self.last_error = None

    def _read_session_blocks(self) -> None:
        client = self.client
        assert client is not None
        now = time.time()
        profile = self.profile
        # 会话块：状态/存活/消费序号/结束确认
        state_value = client.read_words(profile.session_state, 1)[0]
        token = client.read_words(profile.session_confirm, 1)[0]
        liveness = client.read_words(profile.plc_liveness, 1)[0]
        ack_seq = client.read_words(profile.ack_seq, 1)[0]
        end_confirm = client.read_words(profile.end_confirm, 1)[0]
        self.block_times["session"] = now
        self.last_roundtrip_ms["session"] = client.last_roundtrip_ms
        # 生效镜像
        x_eff = client.read_words(profile.x_effective[0], 8)
        ad_eff = client.read_words(profile.ad_effective[0], 4)
        self.block_times["mirror"] = now
        self.last_roundtrip_ms["mirror"] = client.last_roundtrip_ms
        self.effective_x = [value & 1 for value in x_eff]
        self.effective_ad = [value & 0xFFFF for value in ad_eff]
        if self.in_flight is not None and ack_seq == self.in_flight:
            self.in_flight = None
        session_was_active = self.session_active
        self.session_active = state_value == 1
        self._session_snapshot = {
            "session_state": state_value, "plc_liveness": liveness,
            "ack_seq": ack_seq, "end_confirm": end_confirm,
        }
        if session_was_active and (state_value != 1 or token != self.session_token):
            # PLC 侧撤销会话（心跳超时等）：本地同步为故障态。
            self._enter_fault("PLC 会话已失效（状态码 %d）" % state_value)
        self._emit("values")

    # ---- 故障 ------------------------------------------------------------
    def _enter_fault(self, message: str) -> None:
        self.state = State.FAULT
        self.session_active = False
        self.in_flight = None
        self._teardown_transport()
        self._fail(message)
        self._emit("state", state=self.state)
        self.log_op("system", "通讯", "故障", result="失败", reason=message)
        if self._recording:
            self._recording = False
            self.record and self.record("end", {"status": "异常中断",
                                                "end_reason": "通讯故障", "error": message})
        self._emit("values", stale=True)

    def abort_recording(self, message: str) -> None:
        """尽力结束已建立的会话并释放连接。"""
        try:
            if self.session_active and self.client is not None:
                self._check_write(self.profile.end_request, self.session_token, "日志故障结束")
                self.client.write_word(self.profile.end_request, self.session_token)
        except (ModbusError, PermissionError):
            pass
        finally:
            self._recording = False
            self.session_active = False
            self.in_flight = None
            self._teardown_transport()
            self.state = State.FAULT
            self._fail(message)
            self._emit("state", state=self.state)
            self._emit("values", stale=True)

    # ---- 仿真会话 ----------------------------------------------------------
    def start_manual_test(self) -> None:
        """Resume readback and customer-register tests after a script releases its client."""
        if self.state != State.DISCONNECTED:
            raise PermissionError("手动接管前需释放脚本连接")
        self.record and self.record("start", {**self._session_snapshot_config(), "source": "manual_after_script"})
        self._recording = True
        try:
            self.connect()
        except (OSError, ModbusError, ValueError):
            self.record and self.record("end", {"status": "启动失败", "end_reason": "手动连接失败"})
            self._recording = False
            raise
        self.session_token = self.session_token % 65535 + 1
        self.state = State.MANUAL
        try:
            self._check_online_identity()
            self._read_manual_inputs(update_targets=True)
        except (ModbusError, PermissionError) as exc:
            self._enter_fault(str(exc))
            raise
        self.log_op("user", "手动测试", "确认后手动接管")
        self._emit("state", state=self.state)

    def start_simulation(self) -> None:
        """一键开始：未连接则自动连接；复用现有连接；失败即记录并退出启动流程。

        会话记录先于连接建立（PRD §9.1：自动连接、版本读取、预检失败都在
        同一次调试记录内）。
        """
        if self.state in (State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM, State.MANUAL,
                          State.SIMULATING, State.STARTING, State.ENDING):
            event = self.log_op("user", "开始仿真", "拒绝", result="拒绝",
                                reason=f"当前状态 {self.state}，不能重复启动")
            self._fail("仿真已在进行或启动中，不能重复启动")
            return event
        if self.state == State.FAULT:
            event = self.log_op("user", "开始仿真", "拒绝", result="拒绝",
                                reason="故障/断线状态需先重连")
            self._fail("故障/断线状态需先重连再开始新会话")
            return event
        self.record and self.record("start", self._session_snapshot_config())
        self._recording = True
        self.log_op("system", "开始仿真", "会话启动", result="成功")
        try:
            if self.state == State.DISCONNECTED:
                self.connect()  # 失败会抛 ConnectionError → 记“启动失败”
            self.state = State.STARTING
            self._emit("state", state=self.state)
            self._preflight()
            self._open_session()
            self._submit_initial_group()
        except RecordingError:
            raise
        except (ModbusError, PermissionError, ValueError, OSError) as exc:
            if self.session_active:
                self._end_session_locked("启动失败")
            self.log_op("system", "开始仿真", "启动失败", result="失败", reason=str(exc))
            if self._recording:
                self.record and self.record("end", {"end_reason": "启动失败", "status": "启动失败",
                                                    "error": str(exc)})
            self._recording = False
            if self.state != State.FAULT:
                self.state = State.CONNECTED if self.client is not None else State.DISCONNECTED
            self._emit("state", state=self.state)
            self._fail(f"启动失败: {exc}")
            return
        self.state = State.SIMULATING
        self._emit("state", state=self.state)
        self.log_op("system", "开始仿真", "仿真中", result="成功")

    def _preflight(self) -> None:
        errors = self.profile.validate()
        if errors or not self.profile.is_complete():
            raise ValueError("接口档案不完整或校验失败，禁止注入")
        if not self.settings["demo"] and not self.profile.confirmed:
            raise PermissionError("接口档案未经用户确认（confirmed=false），实机禁止写入")
        assert self.client is not None
        if self.settings["demo"]:
            self.client.read_words(self.profile.session_state, 1)
            return
        interface = (*self.profile.read_regs(), *self.profile.write_regs())
        if any(address > USER_D_MAX for address in interface):
            raise PermissionError("实机会话地址须在 D0–D7999 用户区")
        if self.version_address in interface:
            raise PermissionError("版本地址与会话接口重叠")
        identity = dict(self.profile.build_identity)
        if self.version_address not in identity or len(identity) < 2:
            raise PermissionError("实机档案须在 build_identity 中提供预期版本及独立构建标识")
        self._check_online_identity()
        liveness = self.profile.plc_liveness
        first = self.client.read_words(liveness, 1)[0]
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            time.sleep(0.05)
            if self.client.read_words(liveness, 1)[0] != first:
                return
        raise PermissionError("PLC 存活计数未变化")

    def _check_online_identity(self) -> None:
        if self.client.read_words(self.version_address, 1)[0] != self.version_value:
            raise PermissionError("PLC 程序版本已变化，请重新连接")
        identity = self.manual_identity if self.state == State.MANUAL and self.manual_identity else self.profile.build_identity
        for address, expected in identity:
            if self.client.read_words(address, 1)[0] & 0xFFFF != expected & 0xFFFF:
                raise PermissionError(f"D{address} 构建标识与接口档案不符")

    def _open_session(self) -> None:
        client = self.client
        assert client is not None
        profile = self.profile
        prior_request = client.read_words(profile.session_request, 1)[0]
        self.session_token = prior_request % 65535 + 1
        self.last_seq = 0
        self._check_write(profile.session_request, self.session_token, "会话申请")
        self.log_op("system", f"D{profile.session_request}", "会话申请待发送",
                    target=self.session_token, result="待发送")
        client.write_word(profile.session_request, self.session_token)
        self.log_op("system", f"D{profile.session_request}", "发送会话申请",
                    target=self.session_token, result="成功")
        deadline = time.monotonic() + ACK_TIMEOUT_S
        confirm = None
        while time.monotonic() < deadline:
            confirm = client.read_words(profile.session_confirm, 1)[0]
            if confirm == self.session_token:
                state_value = client.read_words(profile.session_state, 1)[0]
                if state_value == 1:
                    break
            time.sleep(0.05)
        else:
            raise TimeoutError(f"会话申请未在 {ACK_TIMEOUT_S:.0f}s 内确认（confirm={confirm}）")
        self.log_op("system", f"D{profile.session_confirm}", "会话确认",
                    effective=self.session_token, result="成功")
        self.session_active = True

    def _submit_initial_group(self) -> None:
        """提交用户可见的初始输入组（默认 X=0、AD=复位值 raw 0；含连接期预编辑值）。

        本机初始值不是已生效值：必须等待 PLC 消费确认（PRD §4.1）。
        """
        result = self._send_group(actor="system", obj="初始输入组",
                                  action="提交初始输入", source="start")
        if result["result"] != "已生效":
            raise ValueError(result.get("reason") or "PLC 未确认初始输入生效")

    def _send_group(self, *, actor: str, obj: str, action: str, source: str) -> dict:
        """一次组提交：暂存 → 校验和 → 序号。确认前不覆盖暂存。"""
        if self.state == State.MANUAL:
            return self._send_manual_inputs(actor, obj, action)
        client = self.client
        assert client is not None
        profile = self.profile
        if self.in_flight is not None:
            event = self.log_op(actor, obj, action, result="拒绝",
                                reason=f"上一组（序号 {self.in_flight}）尚未确认",
                                detail={"pending_seq": self.in_flight})
            return event
        seq = self.last_seq % 65535 + 1
        words = [*self.target_x, *self.target_ad_raw]
        target = {"x": words[:8], "ad_raw": words[8:]}
        checksum = group_checksum(words)
        detail = {"seq": seq, "checksum": checksum, "source": source}
        self.log_op(actor, obj, action, target=target, unit="raw", step=self.step_pct,
                    result="待发送", detail=detail)
        try:
            for address, value in zip((*profile.x_command, *profile.ad_command), words):
                self._check_write(address, value, "输入暂存")
            self._check_write(profile.content_checksum, checksum, "内容校验")
            self._check_write(profile.request_seq, seq, "提交序号")
            client.write_words(profile.x_command[0], target["x"])
            client.write_words(profile.ad_command[0], target["ad_raw"])
            client.write_word(profile.content_checksum, checksum)
            self.last_seq = seq
            self.in_flight = seq
            client.write_word(profile.request_seq, seq)
            deadline = time.monotonic() + ACK_TIMEOUT_S
            while time.monotonic() < deadline:
                if client.read_words(profile.ack_seq, 1)[0] == seq:
                    break
                time.sleep(0.05)
            else:
                raise ModbusError(f"组 {seq} 未收到消费确认")
            self._read_session_blocks()
            if self.state == State.FAULT:
                return self.log_op(actor, obj, action, target=target, result="失败",
                                   reason=self.last_error, detail=detail)
            effective = {"x": list(self.effective_x), "ad_raw": list(self.effective_ad)}
            if effective != target:
                raise ModbusError(f"组 {seq} 生效镜像与目标不一致")
        except (ModbusError, PermissionError) as exc:
            event = self.log_op(actor, obj, action, target=target, result="失败",
                                reason=str(exc), detail=detail)
            self._enter_fault(f"组提交失败: {exc}")
            return event
        self._emit("values")
        return self.log_op(actor, obj, action, target=target, effective=effective,
                           unit="raw", step=self.step_pct, result="已生效", detail=detail)

    def _check_write(self, address: int, value: int, label: str) -> None:
        self.profile.check_write_allowed(address)
        if address == self.version_address or (
                not self.settings["demo"] and address > USER_D_MAX):
            raise PermissionError(f"D{address} 不允许作为仿真写入地址")
        assert value is not None
        assert 0 <= int(value) <= 65535, f"{label} 值越界"

    def _read_manual_inputs(self, *, update_targets=False, block: dict[int, int] | None = None):
        for physical, row in self.manual_inputs.items():
            logical = row["logical"]
            index = int(logical[1:])
            value = (block or {}).get(index)
            if value is None:
                if logical.startswith("D"):
                    value = self.client.read_words(index, 1)[0]
                else:
                    address = index if index <= 7679 else 0x1E00 + index - 8000
                    value = self.client.read_bits(1, address, 1)[0]
            if physical.startswith("X"):
                channel = int(physical[1:], 8)
                self.effective_x[channel] = int(bool(value))
                if update_targets:
                    self.target_x[channel] = int(bool(value))
            else:
                channel = int(physical[1:]) - AD_HW_BASE
                self.effective_ad[channel] = value
                if update_targets:
                    self.target_ad_raw[channel] = value

    def _send_manual_inputs(self, actor, obj, action):
        physical = f"D{AD_HW_BASE + int(obj[2:])}" if obj.startswith("AD") and obj[2:].isdigit() else obj
        rows = ([self.manual_inputs[physical]] if physical in self.manual_inputs else
                list(self.manual_inputs.values()) if obj in ("应用全部", "复位仿真输入") else [])
        if not rows:
            return self.log_op(actor, obj, action, result="拒绝", reason="该点位需要原测试工程的输入映射")
        targets = {}
        try:
            if not self.settings["demo"]:
                self._check_online_identity()
            for row in rows:
                address = int(row["injection"][1:])
                if not 0 <= address <= USER_D_MAX or address == self.version_address:
                    raise PermissionError("脚本输入地址超出用户区或与版本地址重叠")
                name = row["physical"]
                value = self.target_x[int(name[1:], 8)] if name.startswith("X") else self.target_ad_raw[int(name[1:]) - AD_HW_BASE]
                targets[row["injection"]] = value
            self.log_op(actor, obj, action, target=targets, result="待发送", detail={"source": "script_input_mapping"})
            for address, value in targets.items():
                self.client.write_word(int(address[1:]), value)
            self._read_manual_inputs()
            self._observe_outputs()
        except (ModbusError, PermissionError) as exc:
            result = self.log_op(actor, obj, action, target=targets, result="失败", reason=str(exc))
            self._enter_fault(str(exc))
            return result
        self._emit("values")
        return self.log_op(actor, obj, action, target=targets,
                           effective={"x": self.effective_x, "ad_raw": self.effective_ad}, result="已读回")

    # ---- 客户寄存器 ------------------------------------------------------
    def _protected_customer(self, address: int) -> bool:
        """硬件观察点与档案/会话/版本寄存器：监控可见，但永不通过客户通道写。"""
        protected = (*self.profile.read_regs(), *self.profile.write_regs(),
                     *(word for word, _ in self.profile.build_identity),
                     *(word for word, _ in self.manual_identity),
                     self.settings["version_address"], self.version_address,
                     AD_HW_BASE, AD_HW_BASE + 1, AD_HW_BASE + 2, AD_HW_BASE + 3,
                     DA_HW_BASE, DA_HW_BASE + 1, DA_HW_BASE + 2, 8058)
        return address in protected

    def customer_permission(self, address: int) -> CustomerRegister | None:
        """档案声明的读写范围（用于显示换算与写入边界）；无声明返回 None。"""
        if self._protected_customer(address):
            return None
        if self.settings["demo"] and address == DEMO_CUSTOMER_REGISTER.address:
            return DEMO_CUSTOMER_REGISTER
        if self.profile.confirmed or self.settings["demo"]:
            return next((register for register in self.profile.customer_registers
                         if register.address == address), None)
        return None

    def customer_write_range(self, address: int) -> tuple[int, int] | None:
        """发送允许的数值范围：监控条目含写权限且地址不受保护时才有值。

        范围取 档案声明 与 条目自带范围 的交集；两者都缺省为 0–65535。
        """
        watch = self.customer_watches.get(address)
        if watch is None or "写" not in watch.access:
            return None
        if self._protected_customer(address):
            return None
        bounds = []
        declared = self.customer_permission(address)
        if declared is not None:
            bounds.append((declared.minimum, declared.maximum))
        if watch.minimum is not None and watch.maximum is not None:
            bounds.append((watch.minimum, watch.maximum))
        if not bounds:
            return (0, 65535)   # 无任何声明：16 位原始值全范围
        low = max(bound[0] for bound in bounds)
        high = min(bound[1] for bound in bounds)
        return (low, high) if low <= high else None

    def _emit_customer_values(self) -> None:
        rows = []
        for address, watch in self.customer_watches.items():
            row = {"address": address, "name": watch.name,
                   "access": watch.access,
                   "permission": self.customer_permission(address),
                   "write_range": self.customer_write_range(address),
                   "protected": self._protected_customer(address),
                   **self.customer_samples.get(address, {})}
            rows.append(row)
        self._emit("customer_values", rows=rows)

    def set_customer_watch(self, address: int, name: str, access: str = "读写",
                           minimum: int | None = None, maximum: int | None = None) -> None:
        if type(address) is not int or not 0 <= address <= D_MAX:
            raise ValueError(f"监控地址须在 D0–D{D_MAX}")
        if access not in CUSTOMER_ACCESS_MODES:
            raise ValueError("权限必须为 只读 / 只写 / 读写")
        name = name.strip()
        if len(name) > 40:
            raise ValueError("寄存器名称最多 40 个字符")
        if address not in self.customer_watches and len(self.customer_watches) >= MAX_CUSTOMER_WATCHES:
            raise ValueError(f"最多监控 {MAX_CUSTOMER_WATCHES} 个寄存器")
        self.log_op("user", f"D{address}", "添加或更新寄存器监控", target=name,
                    detail={"access": access})
        self.customer_watches[address] = CustomerWatch(
            name or f"D{address}", access,
            None if minimum is None else int(minimum),
            None if maximum is None else int(maximum))
        self._emit_customer_values()

    def remove_customer_watch(self, address: int) -> None:
        if address in self.customer_watches:
            self.log_op("user", f"D{address}", "移除寄存器监控")
            del self.customer_watches[address]
            self.customer_samples.pop(address, None)
            self._emit_customer_values()

    def import_customer_watches_csv(self, text: str) -> dict:
        """从 CSV 文本导入监控条目：列 = 地址,名称,权限[,最小值,最大值]。

        首行为表头（首格非数字地址）时自动跳过；权限支持 只读/只写/读写 及
        RO/WO/RW 等别名；范围可选（0–65535 原始值）。逐行校验，非法行跳过并
        记录原因；结果作为一条操作入日志。
        """
        imported, skipped = 0, []
        # csv.reader 处理引号字段（导出的名称含逗号时可正确往返）
        for lineno, cells in enumerate(csv.reader(io.StringIO(text)), 1):
            cells = [cell.strip() for cell in cells]
            if not cells or not any(cells):
                continue

            def skip(reason: str) -> None:
                skipped.append({"line": lineno, "reason": reason})

            address_text = cells[0].upper().removeprefix("D")
            if not address_text.isascii() or not address_text.isdigit():
                if lineno == 1:
                    continue   # 表头行静默跳过
                skip("地址无效")
                continue
            address = int(address_text)
            if not 0 <= address <= D_MAX:
                skip(f"地址超出 D0–D{D_MAX}")
                continue
            name = cells[1] if len(cells) > 1 and cells[1] else f"D{address}"
            if len(name) > 40:
                skip("名称超过 40 字符")
                continue
            access = normalize_customer_access(cells[2]) if len(cells) > 2 and cells[2] else "读写"
            if access is None:
                skip("权限列无效（只读/只写/读写）")
                continue
            minimum = maximum = None
            if len(cells) > 3 and cells[3]:
                try:
                    minimum = int(cells[3])
                    maximum = int(cells[4]) if len(cells) > 4 and cells[4] else 65535
                except ValueError:
                    skip("范围列不是整数")
                    continue
                if not 0 <= minimum <= 65535 or not 0 <= maximum <= 65535:
                    skip("范围须在 0–65535（原始值）")
                    continue
                if minimum > maximum:
                    skip("范围下限大于上限")
                    continue
            is_new = address not in self.customer_watches
            if is_new and len(self.customer_watches) >= MAX_CUSTOMER_WATCHES:
                skip(f"超过监控上限 {MAX_CUSTOMER_WATCHES} 条")
                continue
            self.customer_watches[address] = CustomerWatch(
                name, access, minimum, maximum)
            self.log_op("user", f"D{address}", "添加或更新寄存器监控", target=name,
                        detail={"access": access, "source": "CSV", "line": lineno})
            imported += 1
        result = "成功" if not skipped else ("部分成功" if imported else "失败")
        self.log_op("user", "客户寄存器", "导入监控CSV", target=imported,
                    effective=len(self.customer_watches), result=result,
                    detail={"skipped": skipped} if skipped else None)
        self._emit_customer_values()
        return {"imported": imported, "skipped": skipped,
                "total": len(self.customer_watches)}

    def export_customer_watches_csv(self) -> tuple[str, int]:
        """生成当前监控列表 CSV 文本（列 = 地址,名称,权限[,最小,最大]）。

        按地址排序；名称含逗号/引号时由 csv 模块自动加引号，导入侧可正确
        往返。范围列仅在该条目声明过范围时输出。文本由调用方写文件。
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(["地址", "名称", "权限", "最小", "最大"])
        count = 0
        for address in sorted(self.customer_watches):
            watch = self.customer_watches[address]
            row = [f"D{address}", watch.name, watch.access]
            if watch.minimum is not None and watch.maximum is not None:
                row += [watch.minimum, watch.maximum]
            writer.writerow(row)
            count += 1
        return buffer.getvalue(), count

    def _read_customer(self, address: int) -> int | None:
        assert self.client is not None
        try:
            raw = self.client.read_words(address, 1)[0]
        except SlaveException as exc:
            self.customer_samples[address] = {**self.customer_samples.get(address, {}),
                                              "error": str(exc)}
            self._emit_customer_values()
            return None
        value = self._store_customer_sample(address, raw)
        self._emit_customer_values()
        return value

    def _store_customer_sample(self, address: int, raw: int, *, wall: float | None = None) -> int:
        permission = self.customer_permission(address)
        value = permission.decode(raw) if permission else raw
        self.customer_samples[address] = {"value": value, "raw": raw,
                                          "wall": wall if wall is not None else self._now_wall()}
        return value

    def _read_customers_batch(self, readable: list[int]) -> dict[int, int]:
        """监控表批量刷新：连续（间隙≤2）区段合并为单帧 FC03。

        V005 批量接口的状态+命令块 D300..D335 由此一帧覆盖全表；逐点轮转
        （每拍 1 个地址）曾是手动模式下界面整表刷新需数十拍的原因。区段
        跨度上限 100 字（FC03 单帧 125 字留裕量）；从机对合并区段回异常时
        回退逐点读，保证对地址不连续的未知工程零风险。返回本次取到的
        {地址: 原始字}，供输入映射回读复用。
        """
        client = self.client
        assert client is not None
        runs: list[list[int]] = []
        run = [readable[0]]
        for address in readable[1:]:
            # 距离 ≤3 = 最多补 2 个未监控的间隙地址（如 V005 表缺 316/317），
            # 补读比单独事务便宜；从机异常时整段回退逐点，零风险。
            if address - run[-1] <= 3 and address - run[0] < 100:
                run.append(address)
            else:
                runs.append(run)
                run = [address]
        runs.append(run)
        block: dict[int, int] = {}
        for run in runs:
            if len(run) < 3:
                for address in run:
                    self._read_customer(address)
                continue
            span = run[-1] - run[0] + 1
            try:
                words = client.read_words(run[0], span)
            except SlaveException:
                for address in run:      # 区段内有未定义地址：退回逐点
                    self._read_customer(address)
                continue
            wall = self._now_wall()      # 样本时间戳必须是字符串：界面按 ISO 串切片显示
            for offset, address in enumerate(run):
                raw = words[address - run[0]]
                self._store_customer_sample(address, raw, wall=wall)
                block[address] = raw
            self.last_roundtrip_ms["watch"] = client.last_roundtrip_ms
        self._emit_customer_values()
        return block

    def write_customer_register(self, address: int, value_text: str,
                                *, session_token: int) -> dict:
        obj = f"D{address}"
        action = "发送客户寄存器"
        watch = self.customer_watches.get(address)
        try:
            if (self.state not in (State.SIMULATING, State.MANUAL)
                    or (self.state == State.SIMULATING and not self.session_active)
                    or session_token != self.session_token or self.in_flight is not None):
                raise PermissionError("请在当前仿真会话就绪后发送")
            if watch is None:
                raise PermissionError("请选择已添加监控的寄存器")
            write_range = self.customer_write_range(address)
            if write_range is None:
                if "写" not in watch.access:
                    raise PermissionError("该寄存器权限为只读，不能发送")
                if self._protected_customer(address):
                    raise PermissionError("该地址是观察/接口保护寄存器，禁止经客户通道写入")
                raise PermissionError("接口档案未确认，实机写入被禁止")
            try:
                value = int(value_text.strip())
            except ValueError as exc:
                raise ValueError("请输入整数寄存器值") from exc
            if not write_range[0] <= value <= write_range[1]:
                raise ValueError(f"允许范围 {write_range[0]}–{write_range[1]}")
        except (PermissionError, ValueError) as exc:
            return self.log_op("user", obj, action, target=value_text,
                               result="拒绝", reason=str(exc))

        assert self.client is not None
        try:
            if not self.settings["demo"]:
                self._check_online_identity()
            profile = self.profile
            if self.state == State.SIMULATING and (
                    self.client.read_words(profile.session_state, 1)[0] != 1
                    or self.client.read_words(profile.session_confirm, 1)[0] != session_token):
                raise PermissionError("PLC 仿真会话已变化，请重新连接")
        except (ModbusError, PermissionError) as exc:
            result = self.log_op("user", obj, action, target=value, result="未发送", reason=str(exc))
            self._enter_fault(str(exc))
            return result

        detail = {"name": watch.name, "address": address, "access": watch.access,
                  "raw": value & 0xFFFF, "session_token": session_token}
        if self.state == State.MANUAL and not self.settings["demo"]:
            if address > USER_D_MAX:
                return self.log_op("user", obj, action, target=value, result="拒绝", reason="手动写入限用户 D 区")
        self.log_op("user", obj, action, target=value, result="待发送", detail=detail)
        try:
            self.client.write_word(address, value & 0xFFFF)
            if "读" not in watch.access:
                # 只写寄存器：不读回，如实标注结果（不虚构生效值）。
                return self.log_op("system", obj, action, target=value,
                                   result="已发送（不读回）", detail=detail)
            actual = self._read_customer(address)
        except SlaveException as exc:
            return self.log_op("system", obj, action, target=value, result="写入拒绝",
                               reason=str(exc), detail=detail)
        except ModbusError as exc:
            result = self.log_op("system", obj, action, target=value, result="结果未知",
                                 reason=str(exc), detail=detail)
            self._enter_fault(str(exc))
            return result
        result = "已读回" if actual == value else "读回不一致" if actual is not None else "读回失败"
        return self.log_op("system", obj, action, target=value, effective=actual,
                           result=result, detail=detail)

    # ---- 用户输入操作 --------------------------------------------------------
    def _editable_states(self) -> tuple[str, ...]:
        """允许编辑“待应用值”（仅本机，不发送）的状态（PRD §4.4）。"""
        return (State.DISCONNECTED, State.CONNECTED)

    def set_x(self, index: int, value: int) -> dict:
        """X 目标提交：仿真中立即组提交；未连接/已连接只记待应用值；其余拒绝。"""
        if not 0 <= index <= 7:
            raise ValueError("X 通道编号必须为 0..7")
        value = 1 if value else 0
        if self.state in (State.SIMULATING, State.MANUAL):
            self.target_x[index] = value
            return self._send_group(actor="user", obj=f"X{index}",
                                    action="提交输入", source="x")
        if self.state in self._editable_states():
            old = self.target_x[index]
            self.target_x[index] = value
            return self.log_op("user", f"X{index}", "编辑待应用值", target=value,
                               effective=old, result="待应用",
                               reason=f"当前状态 {self.state}，仅本机记录不发送")
        return self.log_op("user", f"X{index}", "提交输入", target=value,
                           result="拒绝", reason=f"当前状态 {self.state} 不允许输入")

    def press_x(self, index: int) -> dict:
        """按住模式按下：提交 1（或未连接/已连接时记待应用值）。"""
        return self.set_x(index, 1)

    def release_x(self, index: int) -> dict:
        if not 0 <= index <= 7:
            raise ValueError("X 通道编号必须为 0..7")
        if self.state in (State.SIMULATING, State.MANUAL):
            self.target_x[index] = 0
            return self._send_group(actor="user", obj=f"X{index}",
                                    action="松开输入", source="x")
        if self.state in self._editable_states():
            old = self.target_x[index]
            self.target_x[index] = 0
            return self.log_op("user", f"X{index}", "编辑待应用值（松开）", target=0,
                               effective=old, result="待应用",
                               reason=f"当前状态 {self.state}，仅本机记录不发送")
        return self.log_op("user", f"X{index}", "松开输入", target=0,
                           result="拒绝", reason=f"当前状态 {self.state} 不允许输入")

    def nudge_ad(self, index: int, direction: int) -> dict:
        """＋/−：按当前步长调工程值并立即提交；边界钳位；非会话期拒绝。"""
        if not 0 <= index <= 3:
            raise ValueError("AD 通道编号必须为 0..3")
        kind = self.ad_range[index]
        delta = step_eng(kind, self.step_pct)
        action = "＋调节" if direction > 0 else "−调节"
        if self.state not in (State.SIMULATING, State.MANUAL):
            return self.log_op("user", f"AD{index}", action,
                               result="拒绝", reason=f"当前状态 {self.state} 不允许输入",
                               range_kind=kind, step=self.step_pct, unit=UNIT_LABELS[kind])
        current = eng_from_raw(self.target_ad_raw[index], kind)
        target = current + delta if direction > 0 else current - delta
        target = max(0.0, min(10.0 if kind == "V10" else 20.0, target))
        raw = raw_from_eng(round(target, 6), kind)
        if raw == self.target_ad_raw[index]:
            return self.log_op("user", f"AD{index}", action,
                               target=round(target, 2), effective=round(current, 2),
                               unit=UNIT_LABELS[kind], range_kind=kind, step=self.step_pct,
                               result="钳位", reason="已达量程边界，保持当前值")
        self.target_ad_raw[index] = raw
        return self._send_group(actor="user", obj=f"AD{index}",
                                action=action, source="ad")

    def set_ad_eng(self, index: int, eng_text: str) -> dict:
        """工程值输入框提交；非法/空白/超范围就地报错，不发送。"""
        if not 0 <= index <= 3:
            raise ValueError("AD 通道编号必须为 0..3")
        kind = self.ad_range[index]
        text = eng_text.strip()
        if not text:
            return self.log_op("user", f"AD{index}", "数值输入", result="拒绝",
                               reason="输入为空", range_kind=kind, unit=UNIT_LABELS[kind])
        try:
            value = float(text)
        except ValueError:
            return self.log_op("user", f"AD{index}", "数值输入", target=text,
                               result="拒绝", reason="不是合法数字",
                               range_kind=kind, unit=UNIT_LABELS[kind])
        try:
            raw = raw_from_eng(value, kind)
        except ValueError as exc:
            return self.log_op("user", f"AD{index}", "数值输入", target=value,
                               result="拒绝", reason=str(exc),
                               range_kind=kind, unit=UNIT_LABELS[kind])
        if self.state in (State.SIMULATING, State.MANUAL):
            self.target_ad_raw[index] = raw
            return self._send_group(actor="user", obj=f"AD{index}", action="数值输入",
                                    source="ad")
        if self.state in self._editable_states():
            old = self.target_ad_raw[index]
            self.target_ad_raw[index] = raw
            return self.log_op("user", f"AD{index}", "编辑待应用值", target=value,
                               effective=round(eng_from_raw(old, kind), 2),
                               unit=UNIT_LABELS[kind], range_kind=kind,
                               result="待应用",
                               reason=f"当前状态 {self.state}，仅本机记录不发送")
        return self.log_op("user", f"AD{index}", "数值输入", target=value,
                           result="拒绝", reason=f"当前状态 {self.state} 不允许输入",
                           range_kind=kind, unit=UNIT_LABELS[kind])

    def apply_all(self) -> dict:
        """应用全部：8X+4AD 待应用值作为一组提交（PRD §6.4）。"""
        if self.state not in (State.SIMULATING, State.MANUAL):
            return self.log_op("user", "应用全部", "组提交", result="拒绝",
                               reason=f"当前状态 {self.state} 不允许提交")
        return self._send_group(actor="user", obj="应用全部", action="组提交",
                                source="apply_all")

    def reset_inputs(self) -> dict:
        """复位仿真输入：X=0、AD=档案复位值（默认 raw 0）并提交。"""
        if self.state not in (State.SIMULATING, State.MANUAL):
            return self.log_op("user", "复位仿真输入", "复位提交", result="拒绝",
                               reason=f"当前状态 {self.state} 不允许复位")
        self.target_x = [0] * 8
        self.target_ad_raw = [0] * 4
        return self._send_group(actor="user", obj="复位仿真输入", action="复位提交",
                                source="reset")

    def set_step(self, pct: int) -> dict:
        """步长调整：本机操作，不写 PLC（PRD §6.3）。"""
        if not 1 <= pct <= 10:
            return self.log_op("user", "步长", "调整", target=pct, unit="满量程%",
                               result="拒绝", reason="步长必须为 1–10%")
        old = self.step_pct
        self.step_pct = pct
        return self.log_op("user", "步长", "调整", target=pct, effective=old,
                           unit="满量程%", result="成功",
                           detail={"note": "本机操作，未写 PLC"})

    def set_ad_range(self, index: int, kind: str) -> dict:
        """AD 量程切换：保持 raw 及百分比位置不变，仅重算工程显示；不发写入。"""
        if kind not in RANGE_KINDS:
            return self.log_op("user", f"AD{index}", "量程切换", target=kind,
                               result="拒绝", reason="未知量程")
        old = self.ad_range[index]
        self.ad_range[index] = kind
        return self.log_op("user", f"AD{index}", "量程切换", target=RANGE_LABELS[kind],
                           effective=RANGE_LABELS[old], result="成功",
                           detail={"note": "保持原始值不变，未写 PLC；不改变硬件类型"})

    def set_da_range(self, index: int, kind: str) -> dict:
        if kind not in RANGE_KINDS:
            return self.log_op("user", f"DA{index + 1}", "量程切换", target=kind,
                               result="拒绝", reason="未知量程")
        old = self.da_range[index]
        self.da_range[index] = kind
        return self.log_op("user", f"DA{index + 1}", "量程切换", target=RANGE_LABELS[kind],
                           effective=RANGE_LABELS[old], result="成功",
                           detail={"note": "仅改显示换算，未写 PLC、未改 D8058"})

    def set_x_mode(self, mode: str) -> dict:
        if mode not in ("保持开关", "按住有效"):
            return self.log_op("user", "X交互模式", "切换", target=mode,
                               result="拒绝", reason="未知模式")
        old = self.x_mode
        self.x_mode = mode
        return self.log_op("user", "X交互模式", "切换", target=mode, effective=old,
                           result="成功", detail={"note": "人工操作，不承诺精确脉宽"})

    def heartbeat(self) -> dict | None:
        """PC 心跳：仿真中每 500ms 调用一次（worker 负责）。"""
        if self.state != State.SIMULATING:
            return None
        self._hb_counter = (self._hb_counter + 1) & 0xFFFF
        client = self.client
        assert client is not None
        profile = self.profile
        try:
            self._check_write(profile.host_heartbeat, self._hb_counter, "主机心跳")
            client.write_word(profile.host_heartbeat, self._hb_counter)
            self._hb_written = time.time()
            return {"counter": self._hb_counter}
        except ModbusError as exc:
            self._enter_fault(f"心跳发送失败: {exc}")
            return None

    # ---- 结束 ------------------------------------------------------------
    def stop_simulation(self, reason="正常结束") -> dict:
        """结束仿真：停止接收新输入 → 发结束请求 → 等确认与结束态 → 回到已连接。"""
        if self.state == State.MANUAL:
            self.log_op("user", "手动测试", "结束手动测试")
            self.record and self.record("end", {"status": "正常结束", "end_reason": reason})
            self._recording = False
            self.state = State.CONNECTED
            self._emit("state", state=self.state)
            return {"status": "正常结束", "end_reason": reason}
        if self.state != State.SIMULATING:
            return self.log_op("user", "结束仿真", "拒绝", result="拒绝",
                               reason=f"当前状态 {self.state}，无可结束的仿真")
        self.state = State.ENDING
        self._emit("state", state=self.state)
        self.log_op("user", "结束仿真", "发送结束请求", result="待发送", reason=reason)
        client = self.client
        profile = self.profile
        result_summary = {"end_reason": reason,
                          "status": "正常结束" if reason == "正常结束" else "异常中断"}
        try:
            token = self.session_token
            self._check_write(profile.end_request, token, "结束请求")
            client.write_word(profile.end_request, token)
            deadline = time.monotonic() + END_TIMEOUT_S
            confirmed = False
            while time.monotonic() < deadline:
                confirm = client.read_words(profile.end_confirm, 1)[0]
                state_value = client.read_words(profile.session_state, 1)[0]
                if confirm == token and state_value == 0:
                    confirmed = True
                    break
                time.sleep(0.05)
            # 尽力读回结束态输出
            try:
                self._observe_outputs(initial=True)
                result_summary["final_outputs"] = {"y": self.y_bits, "da_raw": self.da_raw}
            except ModbusError as exc:
                result_summary["readback_error"] = str(exc)
            if not confirmed:
                result_summary.update(end_reason="结束未确认", status="异常中断",
                                      error=f"{END_TIMEOUT_S:.0f}s 内未收到结束确认")
                self.log_op("system", "结束仿真", "结束确认", result="失败",
                            reason="结束未确认，不虚构输出已归零")
                self.record and self.record("end", result_summary)
                self._recording = False
                self.session_active = False
                self._teardown_transport()
                self.state = State.DISCONNECTED
                self._emit("state", state=self.state)
                self._fail("结束未确认：已释放串口，请核对 PLC 状态后重连")
                return result_summary
            self.session_active = False
            self.in_flight = None
            self.state = State.CONNECTED
            self._emit("state", state=self.state)
            self.log_op("system", "结束仿真", "结束确认", result=result_summary["status"],
                        detail={"plc_outputs_readback": "final_outputs" in result_summary,
                                "readback_error": result_summary.get("readback_error")})
        except ModbusError as exc:
            result_summary.update(end_reason="结束未确认", status="异常中断",
                                  error=str(exc))
            self.log_op("system", "结束仿真", "结束清理", result="失败", reason=str(exc))
            self.record and self.record("end", result_summary)
            self._recording = False
            self.session_active = False
            self._teardown_transport()
            self.state = State.DISCONNECTED
            self._emit("state", state=self.state)
            self._fail(f"结束过程通讯失败: {exc}")
            return result_summary
        self.record and self.record("end", result_summary)
        self._recording = False
        return result_summary

    def _end_session_locked(self, end_reason: str) -> None:
        """断开/退出时尽力关闭会话：只发结束请求，不重试不重放。"""
        client = self.client
        profile = self.profile
        if client is None or not self.session_active:
            return
        try:
            token = self.session_token or 1
            self._check_write(profile.end_request, token, "结束请求")
            client.write_word(profile.end_request, token)
            self.log_op("system", "会话", "断开前结束请求", target=token,
                        result="已发送", reason=end_reason)
        except (ModbusError, PermissionError) as exc:
            self.log_op("system", "会话", "断开前结束请求", result="失败",
                        reason=f"{end_reason}: {exc}")
        self.session_active = False

    # ---- 会话快照 ----------------------------------------------------------
    def _session_snapshot_config(self) -> dict:
        return {
            "tool": "plcweave-bench", "tool_version": "0.5.0",
            "profile_name": self.profile.name, "profile_digest": self.profile.digest(),
            "profile_confirmed": self.profile.confirmed,
            "port": "loopback" if self.settings["demo"] else self.settings["port"],
            "baud": self.settings["baud"], "format": self.settings["format"],
            "station": self.settings["station"],
            "version_address": (f"D{self.version_address}"
                                if self.version_address is not None else None),
            "version_value": self.version_value,
            "demo": self.settings["demo"],
            "customer_watches": [[address, watch.name, watch.access]
                                 for address, watch in self.customer_watches.items()],
            "started_wall": self._now_wall(),
        }

    def sample_snapshot(self) -> dict:
        """带时间戳的输出观察采样（供记录落盘）。"""
        return {
            "wall": self._now_wall(),
            "y": list(self.y_bits), "da_raw": list(self.da_raw),
            "effective_x": list(self.effective_x),
            "effective_ad_raw": list(self.effective_ad),
            "blocks": dict(self.block_times),
            "customer_registers": {f"D{address}": {**sample,
                                                   "name": self.customer_watches[address].name}
                                   for address, sample in self.customer_samples.items()},
            "state": self.state,
        }
