# Output State Table — L01S Water Demo (V005 fix)

Bench: HBDTECH L01S-16M-4AD2DA, empty isolated bench (no sensors, no VFD, no load).
Program: V005 fix, identity `D300=5, D301=31, D302=-10264, D303=-21461, D304=5`.
Link: RS485 Modbus RTU, station 1, 9600/8/N/1 — status FC03 D300–D319,
commands FC16 D320–D335. All values are register readbacks.

Timeline below uses the default parameters (saved SV D325=60 → 6.0 bar; wake
pressure D326=51 → 5.1 bar; sleep delay D327=100 → 10.0 s; wake delay D328=30
→ 3.0 s; no-flow speed D329=2000 → 20.00 Hz) with test PV injection
(`D322=1`, PV driven by `D330`) and physical route enabled (`D323=1`).

| Time | Phase | M0 Run | M11 Sleep | Y0 Output | D154 Freq (0.01 Hz) | D8050 AO0 (0–4000) | What it means |
|---:|---|---:|---:|---:|---:|---:|---|
| 0 s | Stopped | 0 | 0 | **0** | 0 | 0 | Application stopped; run lamp OFF; analog reference 0 |
| 1 s | Running, PV < SV | 1 | 0 | **1** | PI output, ≥2000 | freq × 4/5 | Run latched; lamp ON; frequency setpoint from the PI tick |
| ≥ 10 s at PV ≥ SV | Sleep latched | 1 | 1 | **0** | 0 | 0 | Sleep-delay timer D314 reached clamp(D327); outputs zeroed |
| + 3 s at PV < 51 | Woke | 1 | 0 | **1** | PI output, ≥2000 | freq × 4/5 | Wake-delay timer D315 reached clamp(D328); PI resumes |
| Stop command | Stopped | 0 | 0 | **0** | 0 | 0 | Stop wins; all outputs zero, cleanup verified |

## Notes

- **Y0** = M0 AND D323=1 AND D154>0. A lamp or relay on Y0 follows the table:
  ON while running, OFF in sleep and when stopped.
- **AO0 (D8050)** is the 0–10 V frequency reference (0–4000 counts = frequency
  × 4/5). It is an analog signal; no VFD was connected during bench runs.
- **V005 has no pre-sleep phase** (the V003 `M10` stage was removed): sleep is
  entered directly from normal running when PV ≥ SV **or** frequency ≤ no-flow
  speed (D329) has held continuously for the sleep delay.
- **Wake requires PV strictly below the wake pressure** (D326/D160); equality
  (the dead band) keeps sleep latched. Leaving the below-W region resets D315.
- **One-scan cancellation resets the timers**: a single non-qualifying scan
  restarts the delay counter (D314/D165, D315/D166); counters never accumulate
  across separate qualifying intervals and saturate at their display maximum.
- **D307 status bitmap**: bit0 run, bit1 sleep, bit2 sleep-timing, bit3
  wake-timing, bit4 test, bit5 enable.
- Running-PI values (D311/D312/D319) depend on the 100 ms PI-tick phase; host
  polling cannot judge them step-by-step. They are compared only at zero
  (stopped/sleep) — the same R07 scoping used by the frozen suite.
- Raw data: `Evidence-Summary/SUMMARY-V005-fix-HIL-round3.md` (round-3 batch,
  62 cases) and the four GUI subset runs of 2026-11-10 listed there.
