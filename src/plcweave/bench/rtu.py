"""最小 Modbus RTU 客户端：自建编解码 + 串口/回环传输层。

只实现本工具需要的功能码：FC01 读线圈、FC02 读离散输入、FC03 读保持寄存器、
FC06 写单字、FC16 写多字。报文零基地址，不叠加 40001。CRC 为标准 Modbus
CRC16（多项式 0xA001，低字节在前）。

传输层抽象 `Transport`：
- SerialTransport : pyserial 串口（实机 RS485/USB-RS485）
- LoopbackTransport: 进程内回环，把请求字节直接交给虚拟 PLC 处理，
  供演示模式与自动化测试使用，不占用任何串口、不监听任何端口。
"""
from __future__ import annotations

import time
from typing import Protocol


class ModbusError(Exception):
    """通讯层基础错误。"""


class TransportTimeout(ModbusError):
    """响应超时或帧不完整。"""


class CrcMismatch(ModbusError):
    """CRC 校验失败。"""


class SlaveException(ModbusError):
    """从机返回 Modbus 异常响应。"""

    def __init__(self, function: int, code: int) -> None:
        self.function = function
        self.code = code
        super().__init__(f"从机异常响应: 功能码 {function} 异常码 0x{code:02X}")


class FrameError(ModbusError):
    """响应帧结构/长度不符。"""


def crc16(data: bytes) -> int:
    """标准 Modbus RTU CRC16。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _crc_bytes(data: bytes) -> bytes:
    crc = crc16(data)
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


class Transport(Protocol):
    """字节传输原语。实现必须自身保证事务串行（engine 单线程调用）。"""

    def write(self, data: bytes) -> None:
        """发送请求字节。"""

    def read_exact(self, count: int, timeout: float) -> bytes:
        """读满 count 字节；超时抛 TransportTimeout。"""

    def close(self) -> None: ...


class SerialTransport:
    """pyserial 串口传输。端口参数在 open 时才生效，构造不触碰设备。"""

    def __init__(self, port: str, *, baudrate: int = 9600, bytesize: int = 8,
                 parity: str = "N", stopbits: int = 1, timeout: float = 0.5) -> None:
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self._serial = None

    def open(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise ModbusError("实机连接需要安装 pyserial") from exc

        self._serial = serial.Serial(
            port=self.port, baudrate=self.baudrate, bytesize=self.bytesize,
            parity=self.parity, stopbits=self.stopbits,
            timeout=self.timeout, write_timeout=self.timeout,
        )
        self._serial.reset_input_buffer()

    def write(self, data: bytes) -> None:
        if self._serial is None:
            raise ModbusError("串口未打开")
        self._serial.reset_input_buffer()
        self._serial.write(data)

    def read_exact(self, count: int, timeout: float) -> bytes:
        if self._serial is None:
            raise ModbusError("串口未打开")
        self._serial.timeout = timeout
        data = self._serial.read(count)
        if len(data) != count:
            raise TransportTimeout(
                f"响应不完整: 期望 {count} 字节, 收到 {len(data)} 字节")
        return data

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None


class LoopbackTransport:
    """进程内回环传输：请求交给 `device.handle_request`，零端口零串口。

    write 时立刻取得设备响应并存入缓冲；read_exact 逐段取走，
    与真实串口的分段读取行为一致。设备返回 b\"\"（坏帧沉默）时
    read_exact 直接超时。
    """

    def __init__(self, device, latency_s: float = 0.0) -> None:
        self.device = device
        self.latency_s = latency_s
        self.last_request_hex: str | None = None
        self.last_response_hex: str | None = None
        self._buffer = bytearray()

    def write(self, data: bytes) -> None:
        if self.latency_s:
            time.sleep(self.latency_s)
        response = self.device.handle_request(bytes(data))
        self.last_request_hex = data.hex()
        self.last_response_hex = response.hex()
        self._buffer = bytearray(response)

    def read_exact(self, count: int, timeout: float) -> bytes:
        if len(self._buffer) < count:
            if not self._buffer and self.last_response_hex == "":
                raise TransportTimeout("虚拟设备无响应（静默丢帧）")
            raise TransportTimeout(
                f"响应不完整: 期望 {count} 字节, 缓冲 {len(self._buffer)} 字节")
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def close(self) -> None:
        self._buffer.clear()


class RtuClient:
    """RTU 主站客户端。地址全部为零基协议地址。"""

    def __init__(self, transport: Transport, station: int, *, timeout: float = 0.5) -> None:
        if not 1 <= station <= 247:
            raise ValueError("从机地址必须为 1..247")
        self.transport = transport
        self.station = station
        self.timeout = timeout
        self.last_roundtrip_ms: float | None = None

    # ---- 帧构造 -------------------------------------------------------
    def _request(self, payload: bytes) -> bytes:
        try:
            return self._exchange(payload)
        except OSError as exc:
            raise ModbusError(f"串口通讯失败: {exc}") from exc

    def _exchange(self, payload: bytes) -> bytes:
        """分段读取响应：先读站号+功能码，再按帧型读余量。

        这样异常响应（5 字节短帧）不会像整帧读取那样在串口上等到超时。
        """
        frame = bytes((self.station,)) + payload
        frame += _crc_bytes(frame)
        started = time.monotonic_ns()
        self.transport.write(frame)
        head = self.transport.read_exact(2, self.timeout)
        self.last_roundtrip_ms = (time.monotonic_ns() - started) / 1e6
        if head[0] != self.station:
            raise FrameError(f"响应站号 {head[0]} 与请求 {self.station} 不符")
        function = head[1]
        if function & 0x80:
            rest = self.transport.read_exact(3, self.timeout)
            body = head + rest
            self._verify_crc(body)
            if (function & 0x7F) != payload[0]:
                raise FrameError("异常响应功能码不符")
            raise SlaveException(function & 0x7F, rest[0])
        if function in (1, 2, 3):
            byte_count = self.transport.read_exact(1, self.timeout)[0]
            rest = self.transport.read_exact(byte_count + 2, self.timeout)
            body = head + bytes((byte_count,)) + rest
        elif function in (6, 16):
            rest = self.transport.read_exact(6, self.timeout)
            body = head + rest
        else:
            raise FrameError(f"未知响应功能码 0x{function:02X}")
        self._verify_crc(body)
        return body

    @staticmethod
    def _verify_crc(body: bytes) -> None:
        if len(body) < 4 or _crc_bytes(body[:-2]) != body[-2:]:
            raise CrcMismatch("响应 CRC 校验失败")

    @staticmethod
    def _regs(raw: bytes, count: int) -> list[int]:
        if len(raw) != 2 * count:
            raise FrameError(f"数据长度 {len(raw)} 与请求数 {count} 不符")
        return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw), 2)]

    # ---- 公共操作 -----------------------------------------------------
    def read_bits(self, function: int, address: int, count: int) -> list[int]:
        """FC01/FC02 读位。返回 0/1 列表。"""
        if function not in (1, 2):
            raise ValueError("读位功能码必须为 1 或 2")
        if not 1 <= count <= 2000:
            raise ValueError("位读数量必须为 1..2000")
        payload = bytes((function,)) + address.to_bytes(2, "big") + count.to_bytes(2, "big")
        byte_count = (count + 7) // 8
        response = self._request(payload)
        if response[1] != function:
            raise FrameError("响应功能码不符")
        if response[2] != byte_count:
            raise FrameError("响应字节数不符")
        bits = []
        for i in range(count):
            bits.append((response[3 + i // 8] >> (i % 8)) & 1)
        return bits

    def read_words(self, address: int, count: int) -> list[int]:
        """FC03 读保持寄存器。返回 0..65535 列表。"""
        if not 1 <= count <= 125:
            raise ValueError("字读数量必须为 1..125")
        payload = bytes((3,)) + address.to_bytes(2, "big") + count.to_bytes(2, "big")
        response = self._request(payload)
        if response[1] != 3:
            raise FrameError("响应功能码不符")
        return self._regs(response[3:-2], count)

    def write_word(self, address: int, value: int) -> None:
        """FC06 写单字。"""
        if not 0 <= value <= 65535:
            raise ValueError("写入值必须为 0..65535")
        payload = bytes((6,)) + address.to_bytes(2, "big") + value.to_bytes(2, "big")
        response = self._request(payload)
        if response[1] != 6 or response[2:6] != payload[1:5]:
            raise FrameError("FC06 回显不符")

    def write_words(self, address: int, values: list[int]) -> None:
        """FC16 写多字。"""
        if not 1 <= len(values) <= 123:
            raise ValueError("多字写数量必须为 1..123")
        if any(not 0 <= v <= 65535 for v in values):
            raise ValueError("写入值必须为 0..65535")
        body = bytes((16,)) + address.to_bytes(2, "big") + len(values).to_bytes(2, "big")
        body += bytes((2 * len(values),))
        for value in values:
            body += value.to_bytes(2, "big")
        response = self._request(body)
        if response[1] != 16 or response[2:6] != body[1:5]:
            raise FrameError("FC16 回显不符")

    def close(self) -> None:
        self.transport.close()
