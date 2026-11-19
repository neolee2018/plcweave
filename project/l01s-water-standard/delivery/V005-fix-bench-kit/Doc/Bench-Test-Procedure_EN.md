# L01S Water Demo — Bench Test Procedure (V005 fix)

This kit lets you flash the V005 fix program (self-latch bug fixed, batch
Modbus interface), verify its identity, and run the frozen 62-case suite
(STD-005) against a real L01S PLC.

**Safety first.** Use an isolated bench PLC only: no pump, no VFD, no load, no
mains wiring on the outputs. Y0 and AO0 may be observed with a lamp or a meter;
never connect a live drive or actuator while running these scripts.

## 1. Kit contents

| Path | What it is |
|---|---|
| `Program/MAIN.csv`, `Program/COMMENT.csv` | GX Works2 / compatible instruction-list import (UTF-16 LE) |
| `Program/source.fxil` | Readable source of the same program |
| `Program/Instruction-List-Paste.txt` | Plain instruction list for pasting into an IL editor |
| `test_cases.json` | 62 frozen test cases (suite STD-005) |
| `s1-freeze.json`, `s1-revision-V005.md` | Freeze binding and the V005 revision record |
| `build_identity.json` | Expected identity words and source hash |
| `Runner/run_hil_v3.py` | Case runner: batch command block (FC16) + status block (FC03) |
| `Evidence-Summary/` | Round-3 HIL verdict summary, GUI subset runs, four independent reviews |
| `requirements.txt` | Python dependencies |

## 2. Hardware and ports

| Item | Value |
|---|---|
| PLC | HBDTECH L01S-16M-4AD2DA (4 AI / 2 AO), station 1 |
| Programming port | COM5, 9600 / 7E1 (only for STOP/RUN cases) |
| Modbus port | COM11, RS485, 9600 / 8N1 (bench adapter; override with `--port`) |
| Y0 | Run-permit output (M0=1 AND D323=1 AND D154>0); lamp or relay |
| AO0 (D8050) | 0–4000 counts = 0–10 V frequency reference |
| AI0 (D8030) | Real analog input; not writable over Modbus |

V005 replaces per-register injection with two Modbus blocks:

- **Status block D300–D319** — one FC03 read per refresh (identity, heartbeat,
  scan counter, status bitmap, PV/SV/wake pressure, frequency, AO, tick
  counters, echo, selected raw, PI integral).
- **Command block D320–D335** — one FC16 write per group of writes. Level
  semantics; stop wins. FC06 per-word writes are legal but can create
  intermediate states; the runner writes the whole block atomically.

Bench-only injection: `D322=1` selects test PV `D330`; `D332=1` substitutes the
parallel bench input `D331` for the hardware AI0 in mode 0. `D332=0` keeps the
real AI0 path untouched. Parallel terminals: `D334`/`D335` OR into start/stop
with identical level semantics; releasing the invalid-mode inhibit requires
both sources at 0 in a valid mode.

## 3. Flash and verify

1. Import `Program/MAIN.csv` + `Program/COMMENT.csv` into the L01S project and
   download through COM5 (manual download; no automatic uploader is included).
2. Run the PLC.
3. Verify the identity through the status block before any test write:
   `D300=5, D301=31, D302=-10264, D303=-21461, D304=5`, with `D305` (heartbeat)
   advancing and `D8120=-8063 (0xE081)`, `D8121=1`. The runner refuses to write
   unless this matches `build_identity.json`.

## 4. Run the frozen suite

```bash
pip install -r requirements.txt
python Runner/run_hil_v3.py --port COM11 --output run-full        # all 62 cases
python Runner/run_hil_v3.py --cases STD-001,STD-016,STD-048 --output run-demo
```

The runner records raw observations, verdicts (PASS / PROGRAM_FAIL /
TEST_INFRA_ERROR / UNVERIFIED) and cleanup into the output folder. Running-PI
quantities (D311/D312/D319) are compared only when the drive is stopped or the
expectation is zero; deadline items off by one 100 ms tick are recorded as
UNVERIFIED with the tick-mirror evidence, never promoted to PASS.

## 5. Reference results (bench, 2026-11-08)

Round 3 on the fixed program (`run-v5-full-fix2`): **31 PASS / 31 UNVERIFIED /
0 PROGRAM_FAIL** across 62 cases, 448 atomic writes, cleanup confirmed. Four
independent-context reviewers agreed with the verdict (0 blockers). Full
detail: `Evidence-Summary/SUMMARY-V005-fix-HIL-round3.md`.

Register semantics: `Doc/Status-Command-Blocks_EN.md`. Expected bench states:
`Doc/Output-State-Table_EN.md`.

Bench only: no pump, no VFD, no load. Register readback does not certify
electrical levels, real pressure control or scan-level timing.
