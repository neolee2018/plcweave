"""V006 行为验证（本地逐扫描仿真，非 GX Works / 非实机）。

覆盖：首扫默认值（唤醒 4.0 bar / 最大压力 8.0 bar）、超压封锁、回差自动解锁、
最大压力钳位与 D316 镜像、超压报警位 D307 bit7。
用法：PYTHONPATH=src .venv/Scripts/python.exe project/l01s-water-standard/verify_v006_behavior.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import gxwlib

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "lab-tests/V006/runtime.csv"
OUT = ROOT / "evidence/simulation/v006-behavior"


def raw_for(tenths: int) -> int:
    """0.1 bar 期望值 → 原始 AI 码（D100 = (D110+12)//25）。"""
    return tenths * 25 - 12


def sample_state(snapshot) -> dict:
    bits = snapshot.devices
    words = snapshot.words if hasattr(snapshot, "words") else {}
    return {
        "D100": words.get("D100"), "D154": words.get("D154"), "D307": words.get("D307"),
        "D316": words.get("D316"), "D326": words.get("D326"), "D336": words.get("D336"),
        "D175": words.get("D175"), "D176": words.get("D176"), "D8050": words.get("D8050"),
        "M0": bits.get("M0"), "M40": bits.get("M40"), "Y0": snapshot.output("Y0"),
    }


def main() -> int:
    compiled = gxwlib.compile_program(
        gxwlib.load_csv(str(CSV), device_profile="fx"), profile="fx3u")
    report: dict = {"environment": "local_instruction_simulator", "source_csv": str(CSV),
                    "steps": [], "checks": []}

    def check(name: str, actual, expected, ok: bool) -> None:
        report["checks"].append({"name": name, "actual": actual, "expected": expected,
                                 "status": "PASS" if ok else "FAIL"})

    sim = gxwlib.Simulator(compiled, scan_period_ns=100_000_000)
    sim.set_word_devices({"D322": 1})          # 1 = 注入 D330
    first = sample_state(sim.step())
    report["steps"].append({"case": "first_scan", **first})
    check("first scan D326 (wake 4.0 bar)", first["D326"], 40, first["D326"] == 40)
    check("first scan D336 (max 8.0 bar)", first["D336"], 80, first["D336"] == 80)
    check("mirror D316 = clamped max", first["D316"], 80, first["D316"] == 80)
    check("release threshold D176 = max-5", first["D176"], 75, first["D176"] == 75)

    # 启动 + 物理输出使能，PV 注入 4.0 bar
    sim.set_word_devices({"D320": 1, "D323": 1, "D330": raw_for(40)})
    running = {}
    for _ in range(6):
        running = sample_state(sim.step())
    report["steps"].append({"case": "running_4bar", **running})
    check("running M0", running["M0"], True, bool(running["M0"]))
    check("running frequency > 0", running["D154"], ">0", (running["D154"] or 0) > 0)
    check("running Y0 on", running["Y0"], True, bool(running["Y0"]))
    check("running no overpressure bit", running["D307"], "bit7=0",
          not (int(running["D307"] or 0) & 128))

    # 推到 8.1 bar（81 > 80）→ 封锁
    sim.set_word_devices({"D330": raw_for(81)})
    tripped = {}
    for _ in range(3):
        tripped = sample_state(sim.step())
    report["steps"].append({"case": "pv_8.1bar_trip", **tripped})
    check("trip: PV 81", tripped["D100"], 81, tripped["D100"] == 81)
    check("trip: M40 set", tripped["M40"], True, bool(tripped["M40"]))
    check("trip: frequency zero", tripped["D154"], 0, tripped["D154"] == 0)
    check("trip: Y0 off", tripped["Y0"], False, not bool(tripped["Y0"]))
    check("trip: AO0 zero", tripped["D8050"], 0, tripped["D8050"] == 0)
    check("trip: D307 bit7 set", tripped["D307"], "bit7=1",
          bool(int(tripped["D307"] or 0) & 128))

    # 边界：恰好 8.0 bar 不触发（严格大于）
    sim.set_word_devices({"D330": raw_for(80)})
    edge = sample_state(sim.step())
    report["steps"].append({"case": "pv_8.0bar_edge", **edge})
    check("edge: PV 80 keeps trip (release needs <=75)", edge["M40"], True, bool(edge["M40"]))

    # 回落到 7.4 bar（74 <= 75）→ 自动解锁并恢复出力
    sim.set_word_devices({"D330": raw_for(74)})
    released = {}
    for _ in range(4):
        released = sample_state(sim.step())
    report["steps"].append({"case": "pv_7.4bar_release", **released})
    check("release: PV 74", released["D100"], 74, released["D100"] == 74)
    check("release: M40 cleared", released["M40"], False, not bool(released["M40"]))
    check("release: frequency restored", released["D154"], ">0", (released["D154"] or 0) > 0)
    check("release: D307 bit7 cleared", released["D307"], "bit7=0",
          not (int(released["D307"] or 0) & 128))

    # 钳位：写 0 → 1.0 bar；写 200 → 16.0 bar
    sim.set_word_devices({"D336": 0})
    clamp_low = sample_state(sim.step())
    report["steps"].append({"case": "max_setting_0", **clamp_low})
    check("clamp low D175", clamp_low["D175"], 10, clamp_low["D175"] == 10)
    check("clamp low mirror D316", clamp_low["D316"], 10, clamp_low["D316"] == 10)
    sim.set_word_devices({"D336": 200})
    clamp_high = sample_state(sim.step())
    report["steps"].append({"case": "max_setting_200", **clamp_high})
    check("clamp high D175", clamp_high["D175"], 160, clamp_high["D175"] == 160)

    failed = [c for c in report["checks"] if c["status"] != "PASS"]
    report["status"] = "PASS" if not failed else "FAIL"
    report["note"] = ("Local instruction-level simulation only; not GX Works, "
                      "not PLC hardware, not HMI verified.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "behavior.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "checks": len(report["checks"]),
                      "failed": failed}, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
