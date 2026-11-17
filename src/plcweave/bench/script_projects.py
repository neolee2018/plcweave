"""Explicit legacy project metadata, bound to its unchanged source and identity."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path


def project_adapter(script: Path) -> dict:
    if script.name != "run_hil_v3.py" or script.parent.name != "l01s-water-standard":
        return {}
    source = script.parent / "source.fxil"
    identity = json.loads((script.parent / "build_identity.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    expected = "13f396bcbece6cc4b01935ec17927f1ddc834ff40070cc6245921c52f9d595f9"
    if digest != expected or identity["source_sha256"] != digest:
        raise ValueError("压力工程源文件已变化，请更新脚本接管映射后再运行")
    return {
        "name": "L01S Water Standard V5 / edition 31 (batch interface)", "source_sha256": digest,
        "version_address": 300,
        "identity": ((300, 5), (301, 31), (302, 55272), (303, 44075), (304, 5)),
        # R02/R12: AD0 -> D330 -> selected raw D110 (consumed in test mode D322=1).
        "inputs": [{"physical": "D8030", "logical": "D110", "injection": "D330"},
                   # GUI virtual terminals wired to the program's own command words
                   # (level requests; only value 1 asserts): X0 start, X1 stop.
                   {"physical": "X0", "logical": "D320", "injection": "D320"},
                   {"physical": "X1", "logical": "D321", "injection": "D321"}],
        # 单位/量程注释 + 归一化类型（GUI 表格"单位 / 量程"列与读数换算）。
        "watch_notes": {
            300: ("版本 · 5", ""), 301: ("版次 · 31", ""),
            302: ("指纹 0", ""), 303: ("指纹 1", ""), 304: ("套件版本 · 5", ""),
            305: ("心跳 · 100ms", ""), 306: ("扫描计数", ""),
            307: ("状态位图 · bit0运行 bit1休眠", ""),
            308: ("bar · 0–16.0", "bar01"), 309: ("bar · 1.0–16.0", "bar01"),
            310: ("bar · 唤醒压力", "bar01"), 311: ("Hz · 0–50.00", "hz"),
            312: ("AO0 raw · 0–4000", ""), 313: ("AO1 raw", ""),
            314: ("s · 休眠计时×0.1", "sec01"), 315: ("s · 唤醒计时×0.1", "sec01"),
            316: ("保留", ""), 317: ("回显响应", ""), 318: ("raw · 0–4000", ""),
            319: ("PI 积分 · 0–30000", ""),
            320: ("布尔 · 0/1（启动）", ""), 321: ("布尔 · 0/1（停止）", ""),
            322: ("枚举 · 0=硬件 1=测试", ""), 323: ("布尔 · 0/1（输出使能）", ""),
            324: ("bar · 1.0–16.0", "bar01"), 325: ("bar · 1.0–16.0", "bar01"),
            326: ("bar · 唤醒压力设定", "bar01"),
            327: ("s · 休眠延时×0.1（1–60）", "sec01"),
            328: ("s · 唤醒延时×0.1（0.5–30）", "sec01"),
            329: ("Hz · 不出水速度（20–30）", "hz"),
            330: ("raw 0–4000 ≡ 0–16.0 bar", "pv_bar"),
            331: ("raw 0–4000 ≡ 0–16.0 bar", "pv_bar"),
            332: ("布尔 · 0/1", ""), 333: ("回显请求", ""),
            334: ("布尔 · 0/1（并联启动）", ""), 335: ("布尔 · 0/1（并联停止）", ""),
        },
        # 监控表：状态块 + 命令块全量（批量读 D300..D335 一帧覆盖）。
        "watches": [(300, "程序版本", "只读", None, None),
                    (301, "版次", "只读", None, None),
                    (302, "指纹字 0", "只读", None, None),
                    (303, "指纹字 1", "只读", None, None),
                    (304, "套件版本", "只读", None, None),
                    (305, "心跳", "只读", None, None),
                    (306, "扫描计数", "只读", None, None),
                    (307, "状态位图", "只读", None, None),
                    (308, "实际压力", "只读", 0, 160),
                    (309, "在线设定压力", "只读", 10, 160),
                    (310, "唤醒压力", "只读", 0, 160),
                    (311, "频率", "只读", 0, 5000),
                    (312, "AO0 raw", "只读", 0, 4000),
                    (313, "AO1 raw", "只读", None, None),
                    (314, "休眠计时", "只读", None, None),
                    (315, "唤醒计时", "只读", None, None),
                    (318, "已选输入 raw", "只读", None, None),
                    (319, "PI 积分", "只读", None, None),
                    (320, "启动请求", "读写", 0, 1),
                    (321, "停止请求", "读写", 0, 1),
                    (322, "输入模式 1=测试 0=硬件", "读写", 0, 1),
                    (323, "物理输出使能", "读写", 0, 1),
                    (324, "在线设定压力", "读写", 10, 160),
                    (325, "保存设定压力", "读写", 10, 160),
                    (326, "唤醒压力设定", "读写", 0, 160),
                    (327, "休眠延时 ×0.1s", "读写", 10, 600),
                    (328, "唤醒延时 ×0.1s", "读写", 5, 300),
                    (329, "不出水速度 ×0.01Hz", "读写", 2000, 3000),
                    (330, "模拟压力输入 raw", "读写", 0, 4000),
                    (331, "并联 AI raw", "读写", 0, 4000),
                    (332, "并联 AI 使能", "读写", 0, 1),
                    (333, "回显请求", "读写", 0, 65535),
                    (334, "并联启动端子", "读写", 0, 1),
                    (335, "并联停止端子", "读写", 0, 1)],
    }


def prepare_arguments(script: Path, args: list[str]) -> list[str]:
    args = list(args)
    if project_adapter(script) and not any(arg == "--output" or arg.startswith("--output=") for arg in args):
        args += ["--output", datetime.now().strftime("gui-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]]
    return args
