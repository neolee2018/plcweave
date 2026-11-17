"""引擎测试：状态机、组提交、换算、步长、量程切换、拒绝路径、结束与故障。"""
from dataclasses import replace

import pytest

from plcweave.bench.contract import CustomerRegister, DA_HW_BASE, DEFAULT_DEMO_PROFILE
from plcweave.bench.engine import (
    FULL_RAW,
    BenchEngine,
    RecordingError,
    State,
    eng_from_raw,
    format_parse,
    raw_from_eng,
    step_eng,
)
from plcweave.bench.rtu import LoopbackTransport, RtuClient
from plcweave.bench.virtual import SESSION_ACTIVE, VirtualPLC


def make_engine(sink=None, record=None):
    device = VirtualPLC(DEFAULT_DEMO_PROFILE)
    transport = LoopbackTransport(device)
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, sink=sink, record=record,
                         transport=transport)
    engine.apply_settings(demo=True, version_address=196, station=1)
    return engine, device


def start_sim(engine):
    engine.connect()
    engine.start_simulation()


def verified_profile():
    data = DEFAULT_DEMO_PROFILE.to_dict()
    for key, value in data.items():
        if type(value) is int:
            data[key] = value - 6000
        elif isinstance(value, list):
            data[key] = [address - 6000 for address in value]
    data.update(name="customer-l01s", confirmed=True, status="confirmed",
                build_identity={"196": 101, "200": 4321},
                customer_registers=[{"address": 260, "minimum": -20, "maximum": 120, "signed": True}])
    return type(DEFAULT_DEMO_PROFILE).from_dict(data)


class TestConversion:
    def test_eng_roundtrip(self):
        # PRD A06: 0/50%/100% → 0/5/10V、0/10/20mA、0/2000/4000
        assert eng_from_raw(0, "V10") == 0.0
        assert eng_from_raw(2000, "V10") == 5.0
        assert eng_from_raw(4000, "V10") == 10.0
        assert eng_from_raw(2000, "MA20") == 10.0
        assert eng_from_raw(4000, "MA20") == 20.0
        assert raw_from_eng(5.0, "V10") == 2000
        assert raw_from_eng(10.0, "MA20") == 2000
        assert raw_from_eng(10.0, "V10") == 4000

    def test_raw_rounding(self):
        assert raw_from_eng(0.25, "V10") == 100   # 0.25/10*4000
        assert raw_from_eng(0.125, "V10") == 50

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            raw_from_eng(10.1, "V10")
        with pytest.raises(ValueError):
            raw_from_eng(-0.1, "V10")

    def test_step_table(self):
        # PRD §6.3 表：1%→0.1V/0.2mA/40；5%→0.5V/1mA/200；10%→1V/2mA/400
        assert step_eng("V10", 1) == pytest.approx(0.1)
        assert step_eng("V10", 5) == pytest.approx(0.5)
        assert step_eng("V10", 10) == pytest.approx(1.0)
        assert step_eng("MA20", 1) == pytest.approx(0.2)
        assert step_eng("MA20", 5) == pytest.approx(1.0)
        assert step_eng("MA20", 10) == pytest.approx(2.0)
        assert raw_from_eng(step_eng("V10", 5), "V10") == 200
        assert raw_from_eng(step_eng("MA20", 1), "MA20") == 40
        assert raw_from_eng(step_eng("MA20", 10), "MA20") == 400
        with pytest.raises(ValueError):
            step_eng("V10", 0)
        with pytest.raises(ValueError):
            step_eng("V10", 11)

    def test_format_parse(self):
        assert format_parse("8N2") == {"bytesize": 8, "parity": "N", "stopbits": 2}
        assert format_parse("8E1")["parity"] == "E"
        assert format_parse("8O2")["parity"] == "O"
        with pytest.raises(ValueError):
            format_parse("7E1")
        with pytest.raises(ValueError):
            format_parse("9N1")


class TestConnect:
    def test_connect_reads_version_and_outputs(self):
        engine, device = make_engine()
        device.registers[DA_HW_BASE] = 1234
        engine.connect()
        assert engine.state == State.CONNECTED
        assert engine.version_value == 101
        assert engine.version_address == 196
        assert engine.da_raw == [1234, 0]
        engine.disconnect()
        assert engine.state == State.DISCONNECTED
        assert engine.version_value is None   # 断开后不显示缓存版本

    def test_connect_requires_version_address(self):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE,
                             transport=LoopbackTransport(device))
        engine.apply_settings(demo=True)   # 未设版本地址
        with pytest.raises(ConnectionError):
            engine.connect()
        assert engine.state == State.DISCONNECTED

    def test_connect_failure_keeps_state_clean(self):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE,
                             transport=LoopbackTransport(device))
        engine.apply_settings(demo=True, version_address=196)

        def dead(request):
            return b""   # 模拟总线无响应

        engine.transport.device = type("Dead", (), {"handle_request": staticmethod(dead)})()
        with pytest.raises(ConnectionError):
            engine.connect()
        assert engine.state == State.DISCONNECTED
        assert "连接失败" in engine.last_error

    def test_settings_locked_when_connected(self):
        engine, _ = make_engine()
        engine.connect()
        with pytest.raises(PermissionError):
            engine.apply_settings(baud=115200)


class TestStartStop:
    def test_one_click_start_from_disconnected(self):
        engine, device = make_engine()
        engine.start_simulation()   # 未连接 → 自动连接 + 预检 + 会话
        assert engine.state == State.SIMULATING
        assert device.session_state == SESSION_ACTIVE

    def test_start_reuses_connection(self):
        engine, device = make_engine()
        engine.connect()
        first = engine.transport
        engine.start_simulation()
        assert engine.transport is first   # 复用连接，不重复占用

    def test_double_click_rejected_and_logged(self):
        engine, _ = make_engine()
        engine.start_simulation()
        event = engine.start_simulation()
        assert event["result"] == "拒绝"
        assert engine.state == State.SIMULATING

    def test_start_failure_recorded_and_no_injection(self):
        engine, device = make_engine()
        engine.profile = type(engine.profile)(
            **{**DEFAULT_DEMO_PROFILE.to_dict(), "name": "broken",
               "session_request": None})   # 档案缺会话申请地址
        engine.connect()
        engine.start_simulation()
        assert engine.state == State.CONNECTED   # 退出启动流程，保持只读连接
        assert device.session_state == 0
        assert any(event["action"] == "启动失败" and event["result"] == "失败"
                   for event in engine.events)

    def test_stop_returns_to_connected(self):
        engine, device = make_engine()
        start_sim(engine)
        summary = engine.stop_simulation()
        assert summary["status"] == "正常结束"
        assert engine.state == State.CONNECTED
        assert device.session_state == 0
        # 结束后输出清零可观察
        assert engine.y_bits == [0] * 8
        assert engine.da_raw == [0, 0]

    def test_stop_without_session_rejected(self):
        engine, _ = make_engine()
        engine.connect()
        event = engine.stop_simulation()
        assert event["result"] == "拒绝"


class TestInputOperations:
    def test_x_editable_before_session(self):
        engine, _ = make_engine()
        engine.connect()
        event = engine.set_x(0, 1)
        assert event["result"] == "待应用"
        assert engine.target_x[0] == 1

    def test_x_editable_disconnected(self):
        engine, _ = make_engine()
        event = engine.set_x(3, 1)
        assert event["result"] == "待应用"
        assert engine.target_x[3] == 1

    def test_x_submit_and_effective(self):
        engine, _ = make_engine()
        start_sim(engine)
        event = engine.set_x(0, 1)
        assert event["result"] == "已生效"
        assert engine.effective_x[0] == 1
        engine.poll()                          # 轮询观察输出（Y 由演示程序驱动）
        assert engine.y_bits[0] == 1           # Y0=X0
        event = engine.release_x(0)
        assert engine.effective_x[0] == 0
        engine.poll()
        assert engine.y_bits[0] == 0

    def test_x_rejected_during_starting(self):
        engine, _ = make_engine()
        engine.state = State.STARTING
        event = engine.set_x(0, 1)
        assert event["result"] == "拒绝"

    def test_ad_nudge_step_and_clamp(self):
        engine, _ = make_engine()
        start_sim(engine)
        engine.nudge_ad(0, +1)                # 默认 5% → 0.5V → raw 200
        assert engine.target_ad_raw[0] == 200
        assert engine.effective_ad[0] == 200
        engine.nudge_ad(0, -1)
        engine.nudge_ad(0, -1)                # 0 以下钳位，第二次为“钳位”不越界
        assert engine.target_ad_raw[0] == 0
        events = engine.events
        assert events[-1]["result"] == "钳位"

    def test_ad_nudge_non_multiple_continue(self):
        engine, _ = make_engine()
        start_sim(engine)
        engine.set_ad_eng(1, "3.33")          # 非步长整倍值（0–10V 默认量程）
        engine.nudge_ad(1, +1)                # 从 3.33V 继续加 0.5V
        assert engine.target_ad_raw[1] == round(3.33 / 10 * FULL_RAW) + 200

    def test_ad_entry_invalid_rejected_in_place(self):
        engine, _ = make_engine()
        start_sim(engine)
        for text in ("", "abc", "-1", "11"):
            event = engine.set_ad_eng(2, text)
            assert event["result"] == "拒绝"
        assert engine.target_ad_raw[2] == 0

    def test_ad_entry_success(self):
        engine, _ = make_engine()
        start_sim(engine)
        event = engine.set_ad_eng(0, "7.5")
        assert event["result"] == "已生效"
        assert engine.target_ad_raw[0] == 3000
        assert engine.effective_ad[0] == 3000

    def test_apply_all_group_submit(self):
        engine, _ = make_engine()
        start_sim(engine)
        engine.set_x(2, 1)
        engine.set_ad_eng(3, "2.5")
        event = engine.apply_all()
        assert event["result"] == "已生效"
        assert engine.effective_x[2] == 1
        assert engine.effective_ad[3] == 1000   # 2.5V on 0–10V → raw 1000

    def test_reset_inputs(self):
        engine, _ = make_engine()
        start_sim(engine)
        engine.set_x(1, 1)
        engine.set_ad_eng(0, "5")
        engine.reset_inputs()
        assert engine.effective_x == [0] * 8
        assert engine.effective_ad == [0] * 4

    def test_step_change_is_local_only(self):
        engine, device = make_engine()
        start_sim(engine)
        before = dict(device.registers)
        event = engine.set_step(10)
        assert event["result"] == "成功"
        assert engine.step_pct == 10
        # 设备寄存器无任何变化（步长不写 PLC）
        assert dict(device.registers) == before

    def test_step_out_of_bounds_rejected(self):
        engine, _ = make_engine()
        event = engine.set_step(0)
        assert event["result"] == "拒绝"
        event = engine.set_step(11)
        assert event["result"] == "拒绝"

    def test_range_switch_keeps_raw_no_write(self):
        engine, device = make_engine()
        start_sim(engine)
        engine.set_ad_eng(0, "5")             # raw 2000
        before = dict(device.registers)
        engine.set_ad_range(0, "MA20")        # 切 mA：5V 显示为 10mA，raw 不变
        assert engine.ad_range[0] == "MA20"
        assert engine.target_ad_raw[0] == 2000
        assert dict(device.registers) == before
        assert any(event["action"] == "量程切换" and event["object"] == "AD0"
                   and "保持原始值" in str(event["detail"]) for event in engine.events)


class TestLogging:
    def test_rejected_ops_logged(self):
        engine, _ = make_engine()
        engine.set_x(0, 1)                    # 未连接：待应用
        engine.nudge_ad(0, 1)                 # 未连接：拒绝
        results = [event["result"] for event in engine.events]
        assert "待应用" in results and "拒绝" in results
        seqs = [event["seq"] for event in engine.events]
        assert seqs == list(range(1, len(seqs) + 1))   # 序号连续

    def test_events_have_required_fields(self):
        engine, _ = make_engine()
        engine.log_op("user", "X0", "提交输入", target=1)
        event = engine.events[-1]
        for field in ("seq", "wall", "mono_ms", "actor", "object", "action",
                      "result"):
            assert field in event

    def test_comm_write_audited_in_events(self):
        engine, _ = make_engine()
        start_sim(engine)
        # 会话申请、组提交等通讯动作都有日志
        actions = [event["action"] for event in engine.events]
        assert "发送会话申请" in actions
        assert "会话确认" in actions


class TestFaultPaths:
    def test_comm_failure_during_simulation_enters_fault(self):
        engine, device = make_engine()
        start_sim(engine)

        def dead(request):
            return b""

        engine.transport.device = type("Dead", (), {"handle_request": staticmethod(dead)})()
        engine.poll()
        assert engine.state == State.FAULT
        assert "通讯失败" in engine.last_error
        # 故障后禁止输入
        event = engine.set_x(0, 1)
        assert event["result"] == "拒绝"

    def test_fault_requires_reconnect_before_new_session(self):
        engine, device = make_engine()
        start_sim(engine)
        engine.transport.device = type("Dead", (), {"handle_request": staticmethod(dead)})()
        engine.poll()
        event = engine.start_simulation()
        assert event["result"] == "拒绝"
        assert engine.state == State.FAULT

    def test_heartbeat_failure_enters_fault(self):
        engine, _ = make_engine()
        start_sim(engine)
        engine.transport.device = type("Dead", (), {"handle_request": staticmethod(dead)})()
        engine.heartbeat()
        assert engine.state == State.FAULT


class TestRealHardwareGate:
    def test_unconfirmed_profile_blocks_real_serial_writes(self):
        # 默认演示档案 confirmed=False：非 demo 模式（真实串口）预检必须拒绝注入
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE,
                             transport=LoopbackTransport(device))
        engine.apply_settings(demo=False, version_address=196, station=1)
        engine.connect()
        engine.start_simulation()
        assert engine.state == State.CONNECTED
        assert device.session_state == 0        # 会话未建立，未写任何注入寄存器
        assert any("档案未经用户确认" in str(event["reason"])
                   for event in engine.events if event["result"] == "失败")

    def test_confirmed_profile_allows_real_mode(self):
        confirmed = verified_profile()
        device = VirtualPLC(confirmed)
        device.registers[200] = 4321
        engine = BenchEngine(profile=confirmed, transport=LoopbackTransport(device))
        engine.apply_settings(demo=False, version_address=196, station=1)
        engine.start_simulation()
        assert engine.state == State.SIMULATING

    @pytest.mark.parametrize("unsafe_profile", [False, True])
    def test_wrong_build_or_system_address_emits_no_writes(self, unsafe_profile):
        profile = verified_profile()
        if unsafe_profile:
            profile = replace(profile, session_request=8121)
        device = VirtualPLC(profile)
        device.registers[200] = 4321 if unsafe_profile else 999
        engine = BenchEngine(profile=profile, transport=LoopbackTransport(device))
        engine.apply_settings(version_address=196)
        engine.start_simulation()
        assert engine.state == State.CONNECTED
        assert profile.session_request not in device.registers


class TestCustomerRegisters:
    def test_monitor_write_readback_and_protected_words(self):
        engine, device = make_engine()
        engine.set_customer_watch(260, "设定压力")
        engine.set_customer_watch(8050, "模拟输出")
        engine.connect()
        engine.poll()
        assert engine.customer_samples[260]["value"] == 60
        assert engine.write_customer_register(260, "88", session_token=0)["result"] == "拒绝"
        engine.start_simulation()
        token = engine.session_token
        assert engine.write_customer_register(8050, "88", session_token=token)["result"] == "拒绝"
        assert engine.write_customer_register(260, "4001", session_token=token)["result"] == "拒绝"
        result = engine.write_customer_register(260, "88", session_token=token)
        assert (result["result"], result["effective"]) == ("已读回", 88)
        assert engine.sample_snapshot()["customer_registers"]["D260"]["raw"] == 88
        assert device.registers[260] == 88
        engine.stop_simulation()
        engine.start_simulation()
        assert engine.write_customer_register(260, "90", session_token=token)["result"] == "拒绝"
        assert device.registers[260] == 88

    def test_real_gate_with_signed_value_and_changed_identity(self):
        profile = verified_profile()
        device = VirtualPLC(profile)
        device.registers[200] = 4321
        engine = BenchEngine(profile=profile, transport=LoopbackTransport(device))
        engine.apply_settings(version_address=196)
        engine.set_customer_watch(260, "带符号设定")
        engine.start_simulation()
        token = engine.session_token
        result = engine.write_customer_register(260, "-10", session_token=token)
        assert result["effective"] == -10
        assert device.registers[260] == 65526
        device.registers[200] = 4322
        assert engine.write_customer_register(260, "5", session_token=token)["result"] == "未发送"
        assert device.registers[260] == 65526
        assert engine.state == State.FAULT

    def test_write_readback_mismatch_and_log_failure(self, monkeypatch):
        engine, device = make_engine()
        engine.set_customer_watch(260, "设定压力")
        engine.start_simulation()
        original = device._write_register

        def overwrite(address, value):
            original(address, 60 if address == 260 else value)

        monkeypatch.setattr(device, "_write_register", overwrite)
        result = engine.write_customer_register(260, "88", session_token=engine.session_token)
        assert (result["result"], result["effective"]) == ("读回不一致", 60)
        monkeypatch.setattr(device, "_write_register", original)

        def disk_full(kind, payload):
            raise RecordingError("disk full")

        engine.record = disk_full
        with pytest.raises(RecordingError):
            engine.write_customer_register(260, "88", session_token=engine.session_token)
        assert device.registers[260] == 60

    def test_contract_rejects_unsafe_permissions(self):
        with pytest.raises(ValueError, match="D0–D7999"):
            CustomerRegister(8121, 0, 1)
        data = verified_profile().to_dict()
        data["confirmed"] = "false"
        with pytest.raises(ValueError, match="布尔值"):
            type(DEFAULT_DEMO_PROFILE).from_dict(data)
        profile = verified_profile()
        overlap = replace(profile, customer_registers=(CustomerRegister(200, 0, 1),))
        assert any("重叠" in error for error in overlap.validate())


class TestAcceptanceRegressions:
    def test_unacknowledged_initial_group_never_starts_simulation(self, monkeypatch):
        engine, device = make_engine()
        monkeypatch.setattr("plcweave.bench.engine.ACK_TIMEOUT_S", 0.15)
        monkeypatch.setattr(device, "_consume_group", lambda seq, checksum: None)
        engine.start_simulation()
        assert engine.state == State.FAULT
        assert engine.client is None
        assert all(event["action"] != "仿真中" for event in engine.events)

    def test_ack_with_wrong_mirror_is_not_effective(self, monkeypatch):
        engine, device = make_engine()
        engine.start_simulation()
        consume = device._consume_group

        def wrong_mirror(seq, checksum):
            consume(seq, checksum)
            device.registers[device.profile.x_effective[0]] = 0

        monkeypatch.setattr(device, "_consume_group", wrong_mirror)
        result = engine.set_x(0, 1)
        assert result["result"] == "失败"
        assert "生效镜像与目标不一致" in result["reason"]
        assert engine.state == State.FAULT


class TestRecordHooks:
    def test_record_lifecycle(self):
        records = []
        engine, _ = make_engine(record=lambda kind, payload: records.append((kind, payload)))
        engine.start_simulation()
        engine.set_x(0, 1)
        engine.stop_simulation()
        kinds = [kind for kind, _ in records]
        assert kinds[0] == "start"
        assert "end" in kinds
        start_payload = records[0][1]
        assert start_payload["profile_digest"] == DEFAULT_DEMO_PROFILE.digest()
        updates = [payload for kind, payload in records if kind == "update"]
        assert updates and updates[-1]["version_value"] == 101   # 版本快照补录进会话
        end_payload = [payload for kind, payload in records if kind == "end"][-1]
        assert end_payload["status"] == "正常结束"


class TestSnapshot:
    def test_sample_snapshot_has_timestamps(self):
        engine, _ = make_engine()
        start_sim(engine)
        snapshot = engine.sample_snapshot()
        assert snapshot["state"] == State.SIMULATING
        assert len(snapshot["y"]) == 8
        assert snapshot["blocks"]["y"] is not None


def dead(request):
    return b""
