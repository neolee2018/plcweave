"""虚拟 PLC 契约行为测试：会话握手、组消费、演示程序输出、结束与心跳看门狗。"""
import pytest

from plcweave.bench.contract import (
    DA_HW_BASE,
    DEFAULT_DEMO_PROFILE,
    group_checksum,
)
from plcweave.bench.rtu import LoopbackTransport, RtuClient
from plcweave.bench.virtual import (
    SESSION_ACTIVE,
    SESSION_FAULT,
    SESSION_IDLE,
    HOST_HEARTBEAT_TIMEOUT_S,
    VirtualPLC,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_pair():
    clock = FakeClock()
    device = VirtualPLC(DEFAULT_DEMO_PROFILE, clock=clock)
    client = RtuClient(LoopbackTransport(device), 1, timeout=0.5)
    return client, device, clock


def open_session(client, device, token=7):
    client.write_word(DEFAULT_DEMO_PROFILE.session_request, token)
    assert device.session_state == SESSION_ACTIVE
    assert client.read_words(DEFAULT_DEMO_PROFILE.session_confirm, 1)[0] == token


def submit_group(client, device, x, ad, seq=101):
    words = [*x, *ad]
    client.write_words(DEFAULT_DEMO_PROFILE.x_command[0], x)
    client.write_words(DEFAULT_DEMO_PROFILE.ad_command[0], ad)
    client.write_word(DEFAULT_DEMO_PROFILE.content_checksum, group_checksum(words))
    client.write_word(DEFAULT_DEMO_PROFILE.request_seq, seq)
    return seq


class TestSessionHandshake:
    def test_open_and_confirm(self):
        client, device, clock = make_pair()
        open_session(client, device, token=5)
        assert client.read_words(DEFAULT_DEMO_PROFILE.session_state, 1)[0] == 1
        # 初始生效镜像由 PLC 写入，X=0、AD=0
        assert client.read_words(DEFAULT_DEMO_PROFILE.x_effective[0], 8) == [0] * 8

    def test_late_request_does_not_pollute_active_session(self):
        client, device, clock = make_pair()
        open_session(client, device, token=5)
        client.write_word(DEFAULT_DEMO_PROFILE.session_request, 99)  # 迟到申请
        assert device.session_confirm_value == 5
        assert device.session_state == SESSION_ACTIVE

    def test_idle_by_default(self):
        _, device, _ = make_pair()
        assert device.session_state == SESSION_IDLE


class TestGroupConsumption:
    def test_consume_updates_mirrors_and_outputs(self):
        client, device, clock = make_pair()
        open_session(client, device)
        submit_group(client, device, x=[1, 0, 0, 0, 0, 0, 0, 0], ad=[1000, 2500, 0, 0])
        assert client.read_words(DEFAULT_DEMO_PROFILE.ack_seq, 1)[0] == 101
        assert client.read_words(DEFAULT_DEMO_PROFILE.x_effective[0], 8)[0] == 1
        assert client.read_words(DEFAULT_DEMO_PROFILE.ad_effective[0], 4) == [1000, 2500, 0, 0]
        # 演示程序真实驱动输出：Y0=X0；DA1=AD0；DA2=AD1；Y3=AD0>2000（1000 未超限）
        assert client.read_bits(1, 0x3300, 8) == [1, 0, 0, 0, 0, 0, 0, 0]
        assert client.read_words(DA_HW_BASE, 2) == [1000, 2500]
        # AD0 越过 2000 → Y3 点亮
        submit_group(client, device, x=[1, 0, 0, 0, 0, 0, 0, 0], ad=[3000, 2500, 0, 0],
                     seq=102)
        assert client.read_bits(1, 0x3300, 8)[3] == 1
        assert client.read_words(DA_HW_BASE, 2) == [3000, 2500]

    def test_bad_checksum_not_consumed(self):
        client, device, clock = make_pair()
        open_session(client, device)
        client.write_words(DEFAULT_DEMO_PROFILE.x_command[0], [1] * 8)
        client.write_words(DEFAULT_DEMO_PROFILE.ad_command[0], [0] * 4)
        client.write_word(DEFAULT_DEMO_PROFILE.content_checksum, 12345)  # 错误校验和
        client.write_word(DEFAULT_DEMO_PROFILE.request_seq, 101)
        assert client.read_words(DEFAULT_DEMO_PROFILE.ack_seq, 1)[0] == 0
        assert device.consume_errors and "校验和不符" in device.consume_errors[0]
        # 未消费：生效镜像保持 0，输出不变
        assert client.read_words(DEFAULT_DEMO_PROFILE.x_effective[0], 8) == [0] * 8

    def test_repeat_seq_ignored(self):
        client, device, clock = make_pair()
        open_session(client, device)
        submit_group(client, device, [1] * 8, [0] * 4)
        submit_group(client, device, [1] * 8, [0] * 4)  # 同序号重复提交
        assert client.read_words(DEFAULT_DEMO_PROFILE.ack_seq, 1)[0] == 101


class TestEndSession:
    def test_end_clears_outputs_and_confirms(self):
        client, device, clock = make_pair()
        open_session(client, device)
        submit_group(client, device, [1, 0, 0, 0, 0, 0, 0, 0], [3000, 0, 0, 0])
        assert client.read_bits(1, 0x3300, 8)[0] == 1
        client.write_word(DEFAULT_DEMO_PROFILE.end_request, 77)
        assert device.session_state == SESSION_IDLE
        assert client.read_words(DEFAULT_DEMO_PROFILE.end_confirm, 1)[0] == 77
        # PRD §8.3：结束退出行为由 PLC 执行——Y 关闭、DA 原始值 0
        assert client.read_bits(1, 0x3300, 8) == [0] * 8
        assert client.read_words(DA_HW_BASE, 2) == [0, 0]

    def test_duplicate_end_ignored(self):
        client, device, clock = make_pair()
        open_session(client, device)
        client.write_word(DEFAULT_DEMO_PROFILE.end_request, 77)
        client.write_word(DEFAULT_DEMO_PROFILE.end_request, 77)
        assert client.read_words(DEFAULT_DEMO_PROFILE.end_confirm, 1)[0] == 77


class TestWatchdog:
    def test_heartbeat_timeout_fails_session(self):
        client, device, clock = make_pair()
        open_session(client, device)
        submit_group(client, device, [1] * 8, [4000] * 4)
        client.write_word(DEFAULT_DEMO_PROFILE.host_heartbeat, 1)
        clock.advance(0.5)
        client.write_word(DEFAULT_DEMO_PROFILE.host_heartbeat, 2)  # 心跳持续变化
        clock.advance(0.5)
        client.write_word(DEFAULT_DEMO_PROFILE.host_heartbeat, 3)
        assert device.session_state == SESSION_ACTIVE
        clock.advance(HOST_HEARTBEAT_TIMEOUT_S + 0.1)  # PC 崩溃：心跳停更
        # 任意合法读请求触发看门狗检查（帧: 01 03 00 00 00 01 CRC=840A）
        device.handle_request(bytes.fromhex("010300000001840A"))
        assert device.session_state == SESSION_FAULT
        # 失效输入退出：输出清零（由 PLC 自身执行）
        assert client.read_bits(1, 0x3300, 8) == [0] * 8
        assert client.read_words(DA_HW_BASE, 2) == [0, 0]

    def test_no_watchdog_without_session(self):
        client, device, clock = make_pair()
        clock.advance(100)
        client.read_words(DA_HW_BASE, 2)
        assert device.session_state == SESSION_IDLE


class TestHardwareObservation:
    def test_hw_inputs_independent_of_simulation(self):
        client, device, clock = make_pair()
        device.set_hw_input(3, 1)
        device.set_hw_analog(0, 1234)
        open_session(client, device)
        submit_group(client, device, [0] * 8, [0] * 4)
        # 硬件原值仅诊断：不覆盖仿真输入，生效镜像仍为 0
        assert client.read_bits(2, 0x3400, 8)[3] == 1
        assert client.read_words(DEFAULT_DEMO_PROFILE.x_effective[0], 8) == [0] * 8
        assert client.read_words(8030, 4)[0] == 1234

    def test_version_register_readable(self):
        client, device, clock = make_pair()
        assert client.read_words(device.version_address, 1)[0] == 101
