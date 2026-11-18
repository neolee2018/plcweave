# Output State Table — L01S Water Demo (V003)

Bench: HBDTECH L01S-16M-4AD2DA, empty isolated bench (no sensors, no VFD, no load).
Program: V003, `D196=3, D197=31, D200=7757, D201=-31026, D202=3`.
Link: COM7 Modbus RTU, station 1, 9600/8/N/1. All values are register readbacks.

| Time | Phase | M0 Run | M10 Pre-sleep | M11 Sleep | Y0 Output | D154 Freq (0.01 Hz) | D8050 AO0 (0-4000) | What it means |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 0.8 s | P1 Stopped | 0 | 0 | 0 | **0** | 0 | 0 | Drive stopped; run lamp OFF; analog reference 0 |
| 7.2 s | P2 Running at 5.0 bar | 1 | 0 | 0 | **1** | 2102 | 1681 | Run latched; lamp ON; 21.02 Hz reference, AO 4.20 V |
| 19.2 s | P3 Pre-sleep at 5.8 bar | 1 | 1 | 0 | **1** | 2000 | 1600 | Pre-sleep; lamp stays ON; frequency forced to 20.00 Hz |
| 24.5 s | P3 Sleep latched | 1 | 0 | 1 | **0** | 0 | 0 | Sleep; lamp OFF; frequency and AO forced to 0 |
| 31.2–39.2 s | P4 Sleep held | 1 | 0 | 1 | **0** | 0 | 0 | Sleep remains latched in the dead band |
| 42.3 s | P5 Wake at 5.0 bar | 1 | 0 | 0 | **1** | 2101 | 1680 | 3 s wake delay completed; lamp ON again |
| 49.6 s | P6 Stop | 0 | 0 | 0 | **0** | 0 | 0 | Stop wins; all outputs zero |
| 50 s | P7 Cleanup | 0 | 0 | 0 | **0** | 0 | 0 | Application stopped, output disabled, zero readback |

## Notes

- **Y0** is the PLC run-permit output (M0=1, D193=1, D154>0). A lamp or relay wired to Y0
  follows this column: ON at 7.2 s, OFF at 24.5 s, ON at 42.3 s, OFF at 49.6 s.
- **D8050 (AO0)** is the 0–10 V frequency reference for a VFD (0–4000 counts). It is an analog
  signal, not a lamp. No VFD was connected during this run.
- There is no dedicated "VFD running" lamp in the program. Real VFD run feedback would need the
  drive's status contact wired to a PLC input, which this bench does not have.
- `M0` stays 1 during sleep; `M10` and `M11` are mutually exclusive; stop overrides everything.
- Raw data: `evidence/s6-v3/output-demo-20261024.csv` (115 samples) and `.json`.

## One-line summary for the video

> The PLC latches run on the start request, lights Y0 and outputs a 21 Hz reference; a sustained
> 5.8 bar drives it into pre-sleep at 20 Hz, then sleep with all outputs at zero; dropping back to
> 5.0 bar wakes it after 3 s and Y0 comes back on; a stop request clears everything.
