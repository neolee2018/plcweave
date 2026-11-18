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
    expected = "7eee2d2878b4508fee1169297a9a8f8df0d5b98e091a4e18cb1d1d33fc96aa09"
    if digest != expected or identity["source_sha256"] != digest:
        raise ValueError("压力工程源文件已变化，请更新脚本接管映射后再运行")
    return {
        "name": "L01S Water Standard V6 / edition 31 (batch interface)", "source_sha256": digest,
        "version_address": 300,
        "identity": ((300, 6), (301, 31), (302, 58223), (303, 53576), (304, 6)),
        # R02/R12: AD0 -> D330 -> selected raw D110 (consumed in test mode D322=1).
        "inputs": [{"physical": "D8030", "logical": "D110", "injection": "D330"},
                   # GUI virtual terminals wired to the program's own command words
                   # (level requests; only value 1 asserts): X0 start, X1 stop.
                   {"physical": "X0", "logical": "D320", "injection": "D320"},
                   {"physical": "X1", "logical": "D321", "injection": "D321"}],
        # 界面标注：本次脚本启用了哪些点位、各自功能（tag 为点位牌下方小字，须 ≤4 字符）
        "io": {
            "X0": {"zh": "启动请求", "en": "Start", "tag_zh": "启动", "tag_en": "Start"},
            "X1": {"zh": "停止请求", "en": "Stop", "tag_zh": "停止", "tag_en": "Stop"},
            "AD0": {"zh": "压力信号注入", "en": "PV inject", "tag_zh": "注入", "tag_en": "PV"},
            "Y0": {"zh": "泵运行输出", "en": "Pump output", "tag_zh": "泵", "tag_en": "Pump"},
            "DA0": {"zh": "频率输出 0–50Hz", "en": "Freq out 0–50Hz", "tag_zh": "频率", "tag_en": "Freq"},
        },
        # 单位/量程注释 + 归一化类型（GUI 表格"单位 / 量程"列与读数换算）。
        "watch_notes": {
            300: ("版本 · 6", ""), 301: ("版次 · 31", ""),
            302: ("指纹 0", ""), 303: ("指纹 1", ""), 304: ("套件版本 · 6", ""),
            305: ("心跳 · 100ms", ""), 306: ("扫描计数", ""),
            307: ("状态位图 · bit0运行 bit1休眠 bit6满量程 bit7超压", ""),
            308: ("bar · 0–16.0", "bar01"), 309: ("bar · 1.0–16.0", "bar01"),
            310: ("bar · 唤醒压力", "bar01"), 311: ("Hz · 0–50.00", "hz"),
            312: ("AO0 raw · 0–4000", ""), 313: ("AO1 raw", ""),
            314: ("s · 休眠计时×0.1", "sec01"), 315: ("s · 唤醒计时×0.1", "sec01"),
            316: ("bar · 最大压力生效值", "bar01"), 317: ("回显响应", ""), 318: ("raw · 0–4000", ""),
            319: ("PI 积分 · 0–30000", ""),
            320: ("布尔 · 0/1（启动）", ""), 321: ("布尔 · 0/1（停止）", ""),
            322: ("枚举 · 0=硬件 1=测试", ""), 323: ("布尔 · 0/1（输出使能）", ""),
            324: ("bar · 1.0–16.0", "bar01"), 325: ("bar · 1.0–16.0", "bar01"),
            326: ("bar · 唤醒压力设定（默认4.0）", "bar01"),
            327: ("s · 休眠延时×0.1（1–60）", "sec01"),
            328: ("s · 唤醒延时×0.1（0.5–30）", "sec01"),
            329: ("Hz · 不出水速度（20–30）", "hz"),
            330: ("raw 0–4000 ≡ 0–16.0 bar", "pv_bar"),
            331: ("raw 0–4000 ≡ 0–16.0 bar", "pv_bar"),
            332: ("布尔 · 0/1", ""), 333: ("回显请求", ""),
            334: ("布尔 · 0/1（并联启动）", ""), 335: ("布尔 · 0/1（并联停止）", ""),
            336: ("bar · 最大压力设定（默认8.0）", "bar01"),
        },
        # 英文显示名/注释：只在界面语言非中文时替换 Name 与"单位 / 量程"列；
        # 记录、CSV 导入导出仍用上面的中文权威文本。
        "watch_names_en": {
            300: "Program version", 301: "Edition", 302: "Fingerprint 0",
            303: "Fingerprint 1", 304: "Suite version", 305: "Heartbeat",
            306: "Scan count", 307: "Status bitmap", 308: "Actual pressure",
            309: "Online setpoint", 310: "Wake pressure", 311: "Frequency",
            312: "AO0 raw", 313: "AO1 raw", 314: "Sleep timer", 315: "Wake timer",
            316: "Max pressure", 318: "Selected input", 319: "PI integral", 320: "Start request",
            321: "Stop request", 322: "Input mode test/HW",
            323: "Output enable", 324: "Online setpoint",
            325: "Saved setpoint", 326: "Wake pressure set",
            327: "Sleep delay ×0.1s", 328: "Wake delay ×0.1s",
            329: "Dry-run speed ×0.01Hz", 330: "Analog input raw",
            331: "Parallel AI raw", 332: "Parallel AI enable", 333: "Echo request",
            334: "Parallel start", 335: "Parallel stop", 336: "Max pressure set",
        },
        "watch_notes_en": {
            300: "Version · 6", 301: "Edition · 31", 302: "Fingerprint 0",
            303: "Fingerprint 1", 304: "Suite version · 6",
            305: "Heartbeat · 100ms", 306: "Scan count",
            307: "Bitmap · bit0 run, bit1 sleep, bit6 full-scale, bit7 overpressure",
            308: "bar · 0–16.0", 309: "bar · 1.0–16.0", 310: "bar · wake pressure",
            311: "Hz · 0–50.00", 312: "AO0 raw · 0–4000", 313: "AO1 raw",
            314: "s · sleep timer ×0.1", 315: "s · wake timer ×0.1",
            316: "bar · max pressure", 317: "Echo response", 318: "raw · 0–4000",
            319: "PI integral · 0–30000", 320: "bool · 0/1 (start)",
            321: "bool · 0/1 (stop)", 322: "enum · 0=hardware 1=test",
            323: "bool · 0/1 (output enable)", 324: "bar · 1.0–16.0",
            325: "bar · 1.0–16.0", 326: "bar · wake pressure set (default 4.0)",
            327: "s · sleep delay ×0.1 (1–60)", 328: "s · wake delay ×0.1 (0.5–30)",
            329: "Hz · dry-run speed (20–30)",
            330: "raw 0–4000 ≡ 0–16.0 bar", 331: "raw 0–4000 ≡ 0–16.0 bar",
            332: "bool · 0/1", 333: "Echo request",
            334: "bool · 0/1 (parallel start)", 335: "bool · 0/1 (parallel stop)",
            336: "bar · max pressure set (default 8.0)",
        },
        # 监控表：状态块 + 命令块全量（批量读 D300..D336 一帧覆盖）。
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
                    (316, "最大压力生效值", "只读", 10, 160),
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
                    (335, "并联停止端子", "读写", 0, 1),
                    (336, "最大压力设定", "读写", 10, 160)],
    }


def prepare_arguments(script: Path, args: list[str]) -> list[str]:
    args = list(args)
    if project_adapter(script) and not any(arg == "--output" or arg.startswith("--output=") for arg in args):
        args += ["--output", datetime.now().strftime("gui-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]]
    return args
