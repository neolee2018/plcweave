"""RTU 编解码与传输层测试。"""
import pytest

from plcweave.bench.rtu import (
    CrcMismatch,
    LoopbackTransport,
    ModbusError,
    RtuClient,
    crc16,
)
from plcweave.bench.virtual import VirtualPLC
from plcweave.bench.contract import DEFAULT_DEMO_PROFILE


class TestCrc:
    def test_known_vector(self):
        # 标准 Modbus 校验向量: 0x01 0x03 0x00 0x00 0x00 0x0A → CRC 0xC5 0xCD
        assert crc16(bytes.fromhex("01030000000A")) == 0xCDC5

    def test_crc_bytes_lsb_first(self):
        from plcweave.bench.rtu import _crc_bytes
        assert _crc_bytes(bytes.fromhex("01030000000A")) == bytes.fromhex("C5CD")


class TestRtuClient:
    def make_client(self):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        client = RtuClient(LoopbackTransport(device), 1, timeout=0.5)
        return client, device

    def test_read_words(self):
        client, device = self.make_client()
        device.registers[8050] = 3000
        device.registers[8051] = 2000
        assert client.read_words(8050, 2) == [3000, 2000]

    def test_read_bits_fc01_y_outputs(self):
        client, device = self.make_client()
        device.coils = [1, 0, 1, 1, 0, 0, 0, 0]
        assert client.read_bits(1, 0x3300, 8) == [1, 0, 1, 1, 0, 0, 0, 0]

    def test_read_bits_fc02_hw_inputs(self):
        client, device = self.make_client()
        device.hw_inputs = [0, 1, 0, 0, 0, 0, 0, 1]
        assert client.read_bits(2, 0x3400, 8) == [0, 1, 0, 0, 0, 0, 0, 1]

    def test_write_word_fc06_echo(self):
        client, device = self.make_client()
        client.write_word(8110, 1)
        assert device.registers[8110] == 1

    def test_write_words_fc16(self):
        client, device = self.make_client()
        client.write_words(8118, [10, 20, 30, 40])
        assert [device.registers[a] for a in range(8118, 8122)] == [10, 20, 30, 40]

    def test_crc_error_raises(self):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)

        class CorruptDevice:
            def handle_request(self, request):
                # 破坏数据字节（索引 3）：帧结构完整但 CRC 必然不匹配。
                bad = bytearray(device.handle_request(request))
                bad[3] ^= 0xFF
                return bytes(bad)

        client = RtuClient(LoopbackTransport(CorruptDevice()), 1)
        with pytest.raises(CrcMismatch):
            client.read_words(0, 1)

    def test_corrupt_length_byte_times_out(self):
        # 破坏字节数字段（索引 2）：分段读取按错误长度等待 → 超时（真实 RTU 同理）。
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)

        class CorruptDevice:
            def handle_request(self, request):
                bad = bytearray(device.handle_request(request))
                bad[2] ^= 0xFF
                return bytes(bad)

        client = RtuClient(LoopbackTransport(CorruptDevice()), 1, timeout=0.05)
        from plcweave.bench.rtu import TransportTimeout
        with pytest.raises(TransportTimeout):
            client.read_words(0, 1)

    def test_station_mismatch_raises(self):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        # 从站只应答站号 1；用站号 2 的客户端请求应得到帧错误/超时。
        client = RtuClient(LoopbackTransport(device), 2)
        with pytest.raises(ModbusError):
            client.read_words(0, 1)

    def test_station_bounds(self):
        with pytest.raises(ValueError):
            RtuClient(LoopbackTransport(VirtualPLC(DEFAULT_DEMO_PROFILE)), 0)
        with pytest.raises(ValueError):
            RtuClient(LoopbackTransport(VirtualPLC(DEFAULT_DEMO_PROFILE)), 248)

    def test_illegal_address_exception(self):
        client, _ = self.make_client()
        from plcweave.bench.rtu import SlaveException
        with pytest.raises(SlaveException):
            client.read_words(8500, 100)   # 越出 D8511 上限

    def test_roundtrip_latency_recorded(self):
        client, _ = self.make_client()
        client.read_words(8050, 1)
        assert client.last_roundtrip_ms is not None
        assert client.last_roundtrip_ms >= 0

    def test_write_value_bounds(self):
        client, _ = self.make_client()
        with pytest.raises(ValueError):
            client.write_word(8110, 70000)
        with pytest.raises(ValueError):
            client.write_words(8110, [-1])

    def test_read_count_bounds(self):
        client, _ = self.make_client()
        with pytest.raises(ValueError):
            client.read_words(0, 126)
        with pytest.raises(ValueError):
            client.read_bits(1, 0x3300, 2001)
