# L01S Water Demo — V003 Bench Kit

Contents: the V003 PLC program (GX CSV + source), the frozen 55-case suite, and
two Python tools to verify the bench and reproduce the output states.

Quick start:

1. Read `Doc/Bench-Test-Procedure_EN.md` first (safety, ports, flashing).
2. `pip install -r requirements.txt`
3. Flash `Program/MAIN.csv` + `Program/COMMENT.csv`, RUN the PLC.
4. `python run_output_demo.py --port COM7` — watch Y0 and the printed timeline.
5. `python run_hil_v3.py --cases STD-016,STD-024,STD-048 --output run-demo`

Identity to verify after flashing: D196=3, D197=31, D200=7757, D201=-31026,
D202=3, with D198 advancing. The scripts refuse to write if this does not match.

Bench only: no pump, no VFD, no load. Register readback does not certify
electrical levels, real pressure control or scan-level timing.
