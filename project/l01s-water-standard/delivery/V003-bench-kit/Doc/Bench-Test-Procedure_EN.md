# L01S Water Demo — Bench Test Procedure (V003)

This kit lets you flash the V003 program, verify its identity, watch the output
states change, and run the frozen test cases against a real L01S PLC.

**Safety first.** Use an isolated bench PLC only: no pump, no VFD, no load, no
mains wiring on the outputs. Y0 and AO0 may be observed with a lamp or a meter;
never connect a live drive or actuator while running these scripts.

## 1. Kit contents

| Path | What it is |
|---|---|
| `Program/MAIN.csv`, `Program/COMMENT.csv` | GX Works2 / compatible instruction-list import (UTF-16 LE, 182 instructions) |
| `Program/source.fxil` | Readable source of the same program |
| `test_cases.json` | 55 frozen test cases (suite STD-003) |
| `build_identity.json` | Expected identity words and source hash |
| `run_output_demo.py` | Output-state demonstration (stop / run / pre-sleep / sleep / wake / stop) |
| `run_hil_v3.py` | Case runner: soft-element injection + output readback |
| `summarize_v3.py` | Merges run reports into `SUMMARY.md` |
| `Doc/Output-State-Table_EN.md` | The expected output timeline |
| `requirements.txt` | Python dependencies |

## 2. Hardware and ports

| Item | Value |
|---|---|
| PLC | HBDTECH L01S-16M-4AD2DA (4 AI / 2 AO) |
| Programming port | COM5, 9600 / 7E1 (only needed for the STOP/RUN cases) |
| Modbus port | COM7, RS485, station 1, 9600 / 8N1 |
| Y0 | Run-permit output; a lamp or relay here follows the run state |
| AO0 (D8050) | 0–4000 counts = 0–10 V frequency reference for a VFD |
| AI0 (D8030) | Real analog input; not writable over Modbus |

The program keeps `D190=1` (test input `D1056`) by default. V003 adds a parallel
AI0 bench input: `D1071=1` with `D190=0` uses `D1070` instead of the hardware ADC,
so the analog path can be exercised without a signal source. `D1071=0` leaves the
real AI0 path untouched.

## 3. Flash and verify

1. Import `Program/MAIN.csv` + `Program/COMMENT.csv` into the L01S project and
   download through COM5 (manual download; no automatic uploader is included).
2. Run the PLC.
3. Verify the identity before any test write:

```python
from pymodbus.client import ModbusSerialClient
c = ModbusSerialClient(port="COM7", baudrate=9600, bytesize=8, parity="N",
                       stopbits=1, timeout=0.5, retries=0)
c.connect()
print([c.read_holding_registers(196, count=7, device_id=1).registers])
```

Expected: `D196=3, D197=31, D200=7757, D201=53010(-31026 signed), D202=3`,
and `D198` must keep advancing. If the identity differs, stop: the PLC is not
running this program, and the scripts will refuse to write.

## 4. Watch the outputs (2 minutes)

```bash
python run_output_demo.py --port COM7
```

The script prints one line per state change and writes a CSV/JSON timeline to
`evidence/s6-v3/`. Expected timeline:

| Time | Phase | M0 | M10 | M11 | Y0 | D154 | D8050 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.8 s | Stopped | 0 | 0 | 0 | 0 | 0 | 0 |
| 7.2 s | Running at 5.0 bar | 1 | 0 | 0 | 1 | ≈2107 | ≈1685 |
| 19.3 s | Pre-sleep at 5.8 bar | 1 | 1 | 0 | 1 | 2000 | 1600 |
| 24.6 s | Sleep latched | 1 | 0 | 1 | 0 | 0 | 0 |
| 42.4 s | Wake at 5.0 bar | 1 | 0 | 0 | 1 | ≈2101 | ≈1680 |
| 49.6 s | Stop | 0 | 0 | 0 | 0 | 0 | 0 |

A lamp on Y0 must be ON at 7.2 s, OFF at 24.6 s, ON at 42.4 s, OFF at 49.6 s.

## 5. Run the frozen cases

```bash
# stable / command cases, no STOP/RUN needed
python run_hil_v3.py --cases STD-016,STD-024,STD-048,STD-019,STD-011 --output run-demo

# analog clamp/rounding through the parallel AI0 input
python run_hil_v3.py --cases STD-017,STD-018 --output run-ai0

# first-scan cases need a real STOP/RUN on COM5
python run_hil_v3.py --restart --cases STD-001,STD-002,STD-003 --output run-init
```

Each run creates `evidence/s6-v3/<output>/report.json` and `progress.json`.
Existing output names are rejected; choose a new one.

## 6. Verdicts

| Verdict | Meaning |
|---|---|
| PASS | Every assertion of that case was compared on hardware and matched |
| UNVERIFIED | Compared values matched, but a running PI/analog instant or a timer edge cannot be certified by 29 ms polling |
| PROGRAM_FAIL | A stable quantity differs from the frozen expectation |
| TEST_INFRA_ERROR | Port, identity, or transport failure — fix the setup, not the program |

Host polling takes about 29 ms per transaction at 9600 baud, so values that
change every 100 ms (running D120/D154/D8050) are intentionally left UNVERIFIED
instead of being guessed. This is a measurement limit, not a program defect.

## 7. Troubleshooting

| Symptom | Check |
|---|---|
| `Identity mismatch` | Wrong program flashed, or PLC in STOP. Re-flash V003 and RUN. |
| `Cannot open COM7` | Port number, USB-RS485 driver, or the port is used by another program |
| Modbus silent after a STOP | L01S disables Modbus in STOP; use COM5 to RUN again |
| Y0 lamp does not follow | Y0 output type (transistor vs relay), wiring, and `D193=1` |
| Values look stale | Increase the poll interval; check the heartbeat `D198` advances |

## 8. What this kit does not prove

Electrical output levels, real pressure control, VFD behavior, power-loss
retention and one-scan timing are outside this bench run. Register readback is
not an oscilloscope: for scan-level timing use the PLC-side edge latch planned
for V004 or an external logic analyzer.
