# -*- coding: utf-8 -*-
"""客户寄存器监控：读写权限开关与 CSV 导入（V0.4.2）。

权限语义（用户指令）：只读=仅监控；只写=仅发送命令不轮询读取；读写=既读又可发。
发送规则：只要监控条目权限含“写”即可发送（受保护地址除外）。
"""
import pytest

from plcweave.bench.contract import DEFAULT_DEMO_PROFILE
from plcweave.bench.engine import CUSTOMER_ACCESS_MODES, BenchEngine, State
from plcweave.bench.rtu import LoopbackTransport, SlaveException
from plcweave.bench.virtual import SESSION_ACTIVE, VirtualPLC


@pytest.fixture()
def engine_demo():
    device = VirtualPLC(DEFAULT_DEMO_PROFILE)
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, transport=LoopbackTransport(device))
    engine.apply_settings(demo=True, version_address=196, station=1)
    return engine


class TestAccessModes:
    def test_access_validation(self, engine_demo):
        with pytest.raises(ValueError):
            engine_demo.set_customer_watch(300, "x", "随便")
        assert CUSTOMER_ACCESS_MODES == ("只读", "只写", "读写")

    def test_readwrite_default_sendable_and_polled(self, engine_demo):
        engine_demo.set_customer_watch(300, "普通设定")
        assert engine_demo.customer_write_range(300) == (0, 65535)
        engine_demo.start_simulation()
        engine_demo.poll()
        assert 300 in engine_demo.customer_samples   # 读写：轮询读取

    def test_readonly_blocks_send_but_polls(self, engine_demo):
        engine_demo.set_customer_watch(301, "过程值", "只读")
        assert engine_demo.customer_write_range(301) is None
        engine_demo.start_simulation()
        token = engine_demo.session_token
        result = engine_demo.write_customer_register(301, "5", session_token=token)
        assert result["result"] == "拒绝"
        assert "只读" in result["reason"]
        engine_demo.poll()
        assert 301 in engine_demo.customer_samples   # 只读仍轮询显示

    def test_writeonly_sends_without_readback_or_polling(self, engine_demo):
        engine_demo.set_customer_watch(302, "命令字", "只写")
        assert engine_demo.customer_write_range(302) == (0, 65535)
        engine_demo.start_simulation()
        token = engine_demo.session_token
        result = engine_demo.write_customer_register(302, "7", session_token=token)
        assert result["result"] == "已发送（不读回）"
        engine_demo.poll()
        assert 302 not in engine_demo.customer_samples   # 只写：不轮询读取
        # 值确实写进 PLC（直接读原始寄存器核实）
        assert engine_demo.client.read_words(302, 1)[0] == 7

    def test_protected_address_stays_readonly_even_if_flagged(self, engine_demo):
        engine_demo.set_customer_watch(8050, "模拟输出", "读写")   # DA 硬件观察点
        assert engine_demo.customer_write_range(8050) is None
        engine_demo.start_simulation()
        result = engine_demo.write_customer_register(8050, "1",
                                                     session_token=engine_demo.session_token)
        assert result["result"] == "拒绝"
        assert "禁止经客户通道写入" in result["reason"]

    def test_profile_range_narrows_watch_range(self, engine_demo):
        # 演示档案声明 D260 可写 0–4000；条目自带 0–100 → 取交集
        engine_demo.set_customer_watch(260, "设定压力", "读写", 0, 100)
        assert engine_demo.customer_write_range(260) == (0, 100)
        engine_demo.start_simulation()
        result = engine_demo.write_customer_register(260, "101",
                                                     session_token=engine_demo.session_token)
        assert result["result"] == "拒绝"
        assert "允许范围 0–100" in result["reason"]

    def test_conflicting_ranges_refuse_send(self, engine_demo):
        # 条目范围与档案范围无交集（4001–65535 vs 0–4000）→ 不可发送
        engine_demo.set_customer_watch(260, "设定压力", "读写", 4001, 65535)
        assert engine_demo.customer_write_range(260) is None


class TestCsvImport:
    def test_import_basic_and_aliases(self, engine_demo):
        csv_text = "\n".join([
            "地址,名称,权限,最小,最大",
            "D300,设定压力,读写,0,4000",
            "D301,命令字,只写",
            "D302,过程值,RO",
            "303,缺省权限行",
        ])
        result = engine_demo.import_customer_watches_csv(csv_text)
        assert result["imported"] == 4
        assert result["skipped"] == []
        assert result["total"] == 4
        assert engine_demo.customer_watches[300].name == "设定压力"
        assert engine_demo.customer_watches[300].access == "读写"
        assert (engine_demo.customer_watches[300].minimum,
                engine_demo.customer_watches[300].maximum) == (0, 4000)
        assert engine_demo.customer_watches[301].access == "只写"
        assert engine_demo.customer_watches[302].access == "只读"   # RO 别名
        assert engine_demo.customer_watches[303].access == "读写"   # 缺省权限
        assert any(op["action"] == "导入监控CSV" and op["result"] == "成功"
                   for op in engine_demo.events)

    def test_import_skips_invalid_rows_with_reasons(self, engine_demo):
        csv_text = "\n".join([
            "地址,名称,权限,最小,最大",
            "D500,正常,读写",
            "X999,地址无效,读写",
            "D501,超范围,读写,0,99999",
            "D502,负范围,读写,-5,100",
            "D503,倒挂,读写,100,50",
            "D504,权限错,看看",
            "D505," + "长" * 41 + ",读写",
            "D8512,超地址,读写",
        ])
        result = engine_demo.import_customer_watches_csv(csv_text)
        assert result["imported"] == 1
        reasons = {item["line"]: item["reason"] for item in result["skipped"]}
        assert reasons[3] == "地址无效"
        assert "0–65535" in reasons[4]
        assert "0–65535" in reasons[5]
        assert "范围下限大于上限" in reasons[6]
        assert "权限列无效" in reasons[7]
        assert "40" in reasons[8]
        assert "超出" in reasons[9]
        assert engine_demo.customer_watches[500].name == "正常"

    def test_import_upserts_existing(self, engine_demo):
        engine_demo.set_customer_watch(600, "旧名", "只读")
        engine_demo.import_customer_watches_csv("D600,新名,读写")
        assert engine_demo.customer_watches[600].name == "新名"
        assert engine_demo.customer_watches[600].access == "读写"
        assert engine_demo.customer_write_range(600) == (0, 65535)

    def test_import_caps_at_40(self, engine_demo):
        csv_text = "\n".join(f"D{700 + i},寄存器{i},只读" for i in range(44))
        result = engine_demo.import_customer_watches_csv(csv_text)
        assert result["imported"] == 40
        assert len(result["skipped"]) == 4
        assert result["skipped"][0]["reason"].startswith("超过监控上限")

    def test_import_partially_failed_logged(self, engine_demo):
        result = engine_demo.import_customer_watches_csv("D800,好行,读写\n坏行,坏行,读写")
        assert result["imported"] == 1 and len(result["skipped"]) == 1
        assert any(op["action"] == "导入监控CSV" and op["result"] == "部分成功"
                   for op in engine_demo.events)

    def test_imported_writable_register_sends(self, engine_demo):
        engine_demo.import_customer_watches_csv("D830,导入设定,读写,0,2000")
        engine_demo.start_simulation()
        result = engine_demo.write_customer_register(830, "1500",
                                                     session_token=engine_demo.session_token)
        assert result["result"] == "已读回"
        assert result["effective"] == 1500


class CountingTransport(LoopbackTransport):
    """记录 FC03 请求 (地址, 字数) 的回环传输，用于断言批量合并帧数。"""

    def __init__(self, device):
        super().__init__(device)
        self.fc03: list[tuple[int, int]] = []

    def write(self, data):
        if len(data) >= 6 and data[1] == 3:
            self.fc03.append((int.from_bytes(data[2:4], "big"),
                              int.from_bytes(data[4:6], "big")))
        super().write(data)


class TestBatchWatchPoll:
    """监控表批量刷新（R12 批量接口一帧覆盖全表）与手动输入块复用。"""

    def _setup(self, sink=None):
        device = VirtualPLC(DEFAULT_DEMO_PROFILE)
        transport = CountingTransport(device)
        engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE, sink=sink, transport=transport)
        engine.apply_settings(demo=True, version_address=196, station=1)
        engine.connect()
        return engine, transport

    def _watch_v005_block(self, engine):
        # V005 监控表形态：300..315 + 318..335（316/317 不在表中，间隙 ≤2）
        for address in list(range(300, 316)) + list(range(318, 336)):
            engine.set_customer_watch(address, f"D{address}", "只读")

    def test_one_frame_covers_whole_table_and_emits_once(self):
        events = []
        engine, transport = self._setup(sink=events.append)
        self._watch_v005_block(engine)
        emitted = sum(1 for e in events if e.get("type") == "customer_values")
        engine.poll()
        # 间隙 ≤2（距离≤3）合并：34 个监控点合并为覆盖 300..335 的单帧 FC03
        assert (300, 36) in transport.fc03
        assert sum(1 for addr, _ in transport.fc03 if 300 <= addr <= 335) == 1
        # 34 点全部有值，customer_values 整表在 poll 内只追加发射一次
        assert len(engine.customer_samples) == 34
        assert all("value" in engine.customer_samples[a] for a in engine.customer_watches)
        assert sum(1 for e in events if e.get("type") == "customer_values") == emitted + 1
        # 回归：样本 wall 必须是 ISO 字符串（界面按 [11:19] 切片显示；传浮点会
        # 让 Tk 渲染每拍 TypeError，监控表永久停在"待读取"并冻结事件循环）
        assert all(isinstance(engine.customer_samples[a].get("wall"), str)
                   for a in engine.customer_watches)

    def test_scattered_watches_split_into_runs(self):
        engine, transport = self._setup()
        for address in (100, 101, 102, 200, 205, 206, 207):
            engine.set_customer_watch(address, f"D{address}", "只读")
        engine.poll()
        # 100..102 一帧；200 与 205..207 之间距离 5 > 3 不合并；
        # 200 单点；205..207 一帧
        assert (100, 3) in transport.fc03
        assert (200, 1) in transport.fc03
        assert (205, 3) in transport.fc03
        assert len(engine.customer_samples) == 7

    def test_slave_exception_falls_back_to_per_point(self):
        engine, transport = self._setup()
        self._watch_v005_block(engine)

        class FlakyClient:
            def __init__(self, inner):
                self.inner = inner
                self.batch_attempts = 0

            def read_words(self, address, count):
                if count > 1 and 300 <= address <= 335:
                    self.batch_attempts += 1
                    raise SlaveException(3, 2)   # 区段含未定义地址的从机表现
                return self.inner.read_words(address, count)

            def __getattr__(self, name):
                return getattr(self.inner, name)

        engine.client = FlakyClient(engine.client)
        engine.poll()
        assert engine.state == State.CONNECTED            # 回退成功，不进 FAULT
        assert engine.client.batch_attempts == 1          # 每轮只尝试一次批量
        assert len(engine.customer_samples) == 34
        assert all("value" in engine.customer_samples[a] for a in engine.customer_watches)

    def test_manual_inputs_reuse_batch_block(self):
        engine, transport = self._setup()
        for address in (318, 319, 320, 321):
            engine.set_customer_watch(address, f"D{address}", "读写")
        # V005 输入映射形态（script_projects）：X0→D320，D8030→D110
        engine.manual_inputs = {"X0": {"logical": "D320", "injection": "D320"},
                                "D8030": {"logical": "D110", "injection": "D330"}}
        engine.state = State.MANUAL
        engine.poll()
        assert (318, 4) in transport.fc03                 # 监控块一帧覆盖
        assert (320, 1) not in transport.fc03             # D320 回读复用块，无独立事务
        assert (110, 1) in transport.fc03                 # 块外地址仍单点读
        assert engine.effective_x[0] == 0 and engine.effective_ad[0] == 0
