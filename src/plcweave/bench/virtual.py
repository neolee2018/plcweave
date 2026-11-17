"""内置虚拟 PLC：完整实现输入接口契约的演示/测试后端。

用途：
1. 演示模式（无硬件、无串口、无端口监听）下让工具端到端可用；
2. 自动化测试中充当被测设备，验证引擎与协议实现。

它模拟一台 L01S 的 Modbus RTU 从站行为：
- Y0–Y7   : FC01 @ 0x3300（八进制编号，虚拟演示程序实际驱动）
- X 硬件  : FC02 @ 0x3400（可注入“现场按钮”变化，仅诊断原值）
- D 区    : FC03/FC06/FC16，稀疏字典模型
- D8030–33: 硬件模拟输入原值；D8050/D8051: 两路模拟输出 raw
- 接口档案寄存器: 会话握手、心跳、组提交/消费序号、生效镜像、结束确认

演示程序（真实驱动 Y/DA，满足 PRD §4.2 对配套调试程序的要求）：
  Y0 = 生效X0            Y1 = 生效X1
  Y2 = 生效X0 与 生效X1   Y3 = 生效AD0 > 2000（高限指示）
  DA1 = 生效AD0 raw       DA2 = 生效AD1 raw
结束会话时按 PRD §8.3 由“PLC 自身程序”执行退出：输出清零、会话失效。
"""
from __future__ import annotations

import time

from .contract import DA_HW_BASE, AD_HW_BASE, InterfaceProfile, group_checksum

SESSION_IDLE, SESSION_ACTIVE, SESSION_ENDING, SESSION_FAULT = 0, 1, 2, 3
DEFAULT_VERSION_ADDRESS = 196   # 演示程序把应用版本放在 D196（仅演示，非通用协议）
DEFAULT_VERSION_VALUE = 101
HOST_HEARTBEAT_TIMEOUT_S = 3.0  # PRD §8.3：PLC 连续 3s 无有效心跳变化即会话失效


class VirtualPLC:
    """进程内 L01S 从站模型。测试可注入 clock 以控制时间流逝。"""

    def __init__(self, profile: InterfaceProfile, *,
                 version_address: int = DEFAULT_VERSION_ADDRESS,
                 version_value: int = DEFAULT_VERSION_VALUE,
                 clock=time.monotonic) -> None:
        self.profile = profile
        self.version_address = version_address
        self.version_value = version_value
        self.clock = clock
        self.registers: dict[int, int] = {}
        self.registers[version_address] = version_value & 0xFFFF   # 版本真值在寄存器
        if version_address != 260:
            self.registers[260] = 60     # 演示用客户寄存器，独立于真实水泵工程
        self.coils = [0] * 8              # Y0–Y7 输出映像（0x3300 起）
        self.hw_inputs = [0] * 8          # X0–X7 硬件原值（0x3400 起）
        self.session_state = SESSION_IDLE
        self.session_confirm_value = 0
        self.last_ack_seq = 0
        self.last_end_confirm = 0
        self.last_heartbeat_value = 0
        self.last_heartbeat_change = clock()
        self.last_session_request = 0
        self.consume_errors: list[str] = []
        self._session_token = 0

    # ---- 测试/演示辅助 ---------------------------------------------------
    def set_hw_input(self, index: int, value: int) -> None:
        """模拟现场硬接线输入变化（不影响仿真输入，仅诊断原值）。"""
        self.hw_inputs[index] = 1 if value else 0

    def set_hw_analog(self, index: int, raw: int) -> None:
        self.registers[AD_HW_BASE + index] = max(0, min(4000, int(raw))) & 0xFFFF

    @property
    def da_raw(self) -> list[int]:
        return [self.registers.get(DA_HW_BASE + i, 0) for i in range(2)]

    # ---- 演示业务程序 -----------------------------------------------------
    def run_program(self) -> None:
        """依据生效输入镜像驱动输出（每次请求处理后执行一遍）。"""
        x = self._effective_x()
        ad = self._effective_ad()
        y0 = 1 if x[0] else 0
        y1 = 1 if x[1] else 0
        y2 = 1 if (x[0] and x[1]) else 0
        y3 = 1 if ad[0] > 2000 else 0
        self.coils = [y0, y1, y2, y3, 0, 0, 0, 0]
        self.registers[DA_HW_BASE] = ad[0] & 0xFFFF
        self.registers[DA_HW_BASE + 1] = ad[1] & 0xFFFF

    def _effective_x(self) -> list[int]:
        if self.session_state in (SESSION_ACTIVE, SESSION_ENDING):
            return [self.registers.get(address, 0) & 1
                    for address in self.profile.x_effective]
        return [0] * 8

    def _effective_ad(self) -> list[int]:
        if self.session_state in (SESSION_ACTIVE, SESSION_ENDING):
            return [self.registers.get(address, 0) & 0xFFFF
                    for address in self.profile.ad_effective]
        return [0] * 4

    # ---- 会话与组消费 ------------------------------------------------------
    def _check_watchdog(self) -> None:
        if self.session_state != SESSION_ACTIVE:
            return
        now = self.clock()
        if now - self.last_heartbeat_change >= HOST_HEARTBEAT_TIMEOUT_S:
            # PRD §8.3：心跳超时后 PLC 撤销注入会话，采用失效输入并退出输出。
            self.session_state = SESSION_FAULT
            self.registers[self.profile.session_state] = SESSION_FAULT
            self.session_confirm_value = 0
            self.registers[self.profile.session_confirm] = 0
            self._apply_exit_outputs()
            self.run_program()

    def _apply_exit_outputs(self) -> None:
        """结束/失效的 PLC 侧退出行为：Y 关闭、DA 原始值 0。"""
        self.coils = [0] * 8
        self.registers[DA_HW_BASE] = 0
        self.registers[DA_HW_BASE + 1] = 0

    def _handle_session_request(self, value: int) -> None:
        if value == 0:
            return
        if self.session_state == SESSION_IDLE:
            self._session_token += 1
            self.last_session_request = value
            self.session_confirm_value = value
            self.session_state = SESSION_ACTIVE
            # 线上真值写回寄存器（PC 通过 FC03 读到的就是这些）。
            self.registers[self.profile.session_confirm] = value
            self.registers[self.profile.session_state] = SESSION_ACTIVE
            self.last_ack_seq = 0
            self.registers[self.profile.ack_seq] = 0
            self.last_end_confirm = 0
            self.registers[self.profile.end_confirm] = 0
            self.last_heartbeat_value = 0
            self.last_heartbeat_change = self.clock()
            # 初始生效值由 PLC 自己写入（不是“PC 本机初值即生效”）。
            for address in self.profile.x_effective:
                self.registers[address] = 0
            for address in self.profile.ad_effective:
                self.registers[address] = 0
            self.run_program()
        # 已处于会话中时忽略迟到/重复申请：不污染新会话。

    def _handle_heartbeat(self, value: int) -> None:
        if self.session_state != SESSION_ACTIVE:
            return
        if value != self.last_heartbeat_value:
            self.last_heartbeat_value = value
            self.last_heartbeat_change = self.clock()

    def _consume_group(self, seq: int, checksum: int) -> None:
        """校验并整组消费 8X+4AD。校验失败不消费、不 ACK。"""
        if self.session_state != SESSION_ACTIVE or seq == self.last_ack_seq:
            return
        words = ([self.registers.get(address, 0) for address in self.profile.x_command]
                 + [self.registers.get(address, 0) for address in self.profile.ad_command])
        if group_checksum(words) != checksum:
            self.consume_errors.append(f"组 {seq} 校验和不符: 收到 0x{checksum:04X}")
            return
        for src, dst in list(zip(self.profile.x_command, self.profile.x_effective)) + \
                list(zip(self.profile.ad_command, self.profile.ad_effective)):
            self.registers[dst] = self.registers.get(src, 0) & 0xFFFF
        self.last_ack_seq = seq
        self.registers[self.profile.ack_seq] = seq
        self.run_program()

    def _handle_end_request(self, value: int) -> None:
        if value == 0 or self.last_end_confirm == value:
            return
        if self.session_state in (SESSION_ACTIVE, SESSION_FAULT):
            self.session_state = SESSION_ENDING
            self._apply_exit_outputs()
            self.session_state = SESSION_IDLE
            self.registers[self.profile.session_state] = SESSION_IDLE
            self.session_confirm_value = 0
            self.registers[self.profile.session_confirm] = 0
            self.last_end_confirm = value
            self.registers[self.profile.end_confirm] = value
            self.run_program()

    # ---- 寄存器写入路由 ----------------------------------------------------
    def _write_register(self, address: int, value: int) -> None:
        self.registers[address] = value & 0xFFFF
        profile = self.profile
        if address == profile.session_request:
            self._handle_session_request(value)
        elif address == profile.host_heartbeat:
            self._handle_heartbeat(value)
        elif address == profile.request_seq:
            checksum = self.registers.get(profile.content_checksum, 0)
            self._consume_group(value, checksum)
        elif address == profile.end_request:
            self._handle_end_request(value)

    # ---- RTU 从站 ----------------------------------------------------------
    def handle_request(self, request: bytes) -> bytes:
        """处理一帧 RTU 请求，返回响应字节；坏帧返回 b""（沉默）。"""
        self._check_watchdog()
        if len(request) < 4 or request[-2:] != _crc_bytes(request[:-2]):
            return b""
        station, function = request[0], request[1]
        if station != 1:
            return b""   # 单从站模型：其他站号不响应
        counter = self.profile.plc_liveness
        if counter is not None:
            self.registers[counter] = (self.registers.get(counter, 0) + 1) & 0xFFFF
        try:
            return self._dispatch(function, request[2:-2])
        except _IllegalAddress:
            return _frame(station, function | 0x80, bytes((2,)))

    def _dispatch(self, function: int, payload: bytes) -> bytes:
        if function in (1, 2, 3, 6) and len(payload) != 4:
            return _frame(1, function | 0x80, bytes((3,)))
        if function in (1, 2):
            return self._read_bits(function, payload)
        if function == 3:
            return self._read_words(payload)
        if function == 6:
            return self._write_single(payload)
        if function == 16:
            return self._write_multiple(payload)
        return _frame(1, function | 0x80, bytes((1,)))  # 非法功能

    def _read_bits(self, function: int, payload: bytes) -> bytes:
        address, count = int.from_bytes(payload[0:2], "big"), int.from_bytes(payload[2:4], "big")
        if count < 1 or count > 2000:
            raise _IllegalAddress()
        if function == 1:
            base = 0x3300
            source = lambda i: self.coils[i - base] if 0x3300 <= i < 0x3308 else 0
        else:
            base = 0x3400
            source = lambda i: self.hw_inputs[i - base] if 0x3400 <= i < 0x3408 else 0
        end = address + count
        if end > base + 16:
            raise _IllegalAddress()
        values = [source(i) for i in range(address, end)]
        packed = bytearray((count + 7) // 8)
        for i, value in enumerate(values):
            if value:
                packed[i // 8] |= 1 << (i % 8)
        return _frame(1, function, bytes((len(packed),)) + bytes(packed))

    def _read_words(self, payload: bytes) -> bytes:
        address, count = int.from_bytes(payload[0:2], "big"), int.from_bytes(payload[2:4], "big")
        if count < 1 or count > 125 or address + count > 8512:
            raise _IllegalAddress()
        data = b"".join(self.registers.get(address + i, 0).to_bytes(2, "big")
                        for i in range(count))
        return _frame(1, 3, bytes((len(data),)) + data)

    def _write_single(self, payload: bytes) -> bytes:
        address, value = int.from_bytes(payload[0:2], "big"), int.from_bytes(payload[2:4], "big")
        if address > 8511:
            raise _IllegalAddress()
        self._write_register(address, value)
        self.run_program()
        return _frame(1, 6, payload)

    def _write_multiple(self, payload: bytes) -> bytes:
        if len(payload) < 5 or payload[4] != len(payload) - 5:
            return _frame(1, 16 | 0x80, bytes((3,)))
        address, count = int.from_bytes(payload[0:2], "big"), int.from_bytes(payload[2:4], "big")
        if payload[4] != 2 * count:
            return _frame(1, 16 | 0x80, bytes((3,)))
        if count < 1 or count > 123 or address + count > 8512:
            raise _IllegalAddress()
        data = payload[5:5 + 2 * count]
        for i in range(count):
            self.registers[address + i] = int.from_bytes(data[2 * i:2 * i + 2], "big")
        # 逐个触发会话语义（FC16 落地后按最终值处理）。
        for i in range(count):
            self._write_register(address + i, self.registers[address + i])
        self.run_program()
        return _frame(1, 16, payload[0:4])


class _IllegalAddress(Exception):
    pass


def _crc_bytes(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def _frame(station: int, function: int, payload: bytes) -> bytes:
    body = bytes((station, function)) + payload
    return body + _crc_bytes(body)
