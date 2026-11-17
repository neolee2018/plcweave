# -*- coding: utf-8 -*-
"""监控列表 CSV 导出与往返（V0.4.3）。"""
import csv
import io

from plcweave.bench.contract import DEFAULT_DEMO_PROFILE
from plcweave.bench.engine import BenchEngine
from plcweave.bench.rtu import LoopbackTransport
from plcweave.bench.virtual import VirtualPLC


def make_engine():
    device = VirtualPLC(DEFAULT_DEMO_PROFILE)
    engine = BenchEngine(profile=DEFAULT_DEMO_PROFILE,
                         transport=LoopbackTransport(device))
    engine.apply_settings(demo=True, version_address=196, station=1)
    return engine


class TestCsvExport:
    def test_export_sorted_with_ranges(self, tmp_path):
        engine = make_engine()
        engine.set_customer_watch(300, "设定", "读写", 0, 4000)
        engine.set_customer_watch(260, "过程值", "只读")
        engine.set_customer_watch(310, "命令", "只写")
        text, count = engine.export_customer_watches_csv()
        assert count == 3
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == ["地址", "名称", "权限", "最小", "最大"]
        assert rows[1] == ["D260", "过程值", "只读"]              # 按地址排序；无范围列
        assert rows[2] == ["D300", "设定", "读写", "0", "4000"]
        assert rows[3] == ["D310", "命令", "只写"]

    def test_export_quoted_name_roundtrip(self):
        engine = make_engine()
        engine.set_customer_watch(400, "压力,设定", "读写", 0, 100)   # 名称含逗号
        text, _ = engine.export_customer_watches_csv()
        other = make_engine()
        result = other.import_customer_watches_csv(text)
        assert result["imported"] == 1
        assert other.customer_watches[400].name == "压力,设定"       # 引号往返不丢
        assert other.customer_watches[400].access == "读写"
        assert (other.customer_watches[400].minimum,
                other.customer_watches[400].maximum) == (0, 100)

    def test_export_empty_list(self):
        engine = make_engine()
        text, count = engine.export_customer_watches_csv()
        assert count == 0
        assert list(csv.reader(io.StringIO(text)))[0][0] == "地址"   # 仅表头
