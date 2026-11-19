# L01S Water Demo — V005 Fix Bench Kit

Contents: the **V005 fix** PLC program (self-latch bug fixed; batch Modbus
interface D300–D335), the frozen 62-case suite STD-005, the batch runner, the
bench documentation, and the round-3 hardware evidence summary.

## Verification status (as delivered)

| Level | Result | Evidence |
|---|---|---|
| Frozen suite (bench HIL, soft-element injection) | **31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL** (62 cases, 448 atomic FC16 writes, 2026-11-08, COM11) | `Evidence-Summary/SUMMARY-V005-fix-HIL-round3.md`, batch `run-v5-full-fix2` |
| Independent review (4 contexts) | 4/4 agree, 0 blockers | `Evidence-Summary/Reviews/reviewer-1..4` |
| GUI bench-tool subset runs (2026-11-10) | 4 runs × 10-case subset: 3 PASS / 7 UNVERIFIED each | project evidence `evidence/s6-v3/gui-20261110-*` |
| Electrical levels, real pressure loop, VFD, scan-level timing | **UNVERIFIED** — bench register readback only | by scope |

UNVERIFIED classes are scoped, not hidden: running-PI phase values (R07),
±1-tick deadline sampling variance (tick-mirror reclassification), the STD-031
simulator-oracle discrepancy (real PLC behaves per spec; the frozen
expectation itself is under S1 revision), and system words D8120/D8121
(recorded at batch checkpoint, never judged per-step).

## Identity after flashing

`D300=5, D301=31, D302=-10264, D303=-21461, D304=5`, heartbeat `D305`
advancing, `D8120=0xE081 (−8063)`, `D8121=1`. Source SHA-256
`13f396bcbece6cc4b01935ec17927f1ddc834ff40070cc6245921c52f9d595f9`
(`build_identity.json`); the runner refuses any write when identity does not
match. Manual download only — this kit contains no automatic uploader.

## Quick start

1. Read `Doc/Bench-Test-Procedure_EN.md` first (safety, ports, flashing).
2. `pip install -r requirements.txt`
3. Flash `Program/MAIN.csv` + `Program/COMMENT.csv`, RUN the PLC.
4. Verify identity per §3 of the procedure.
5. `python Runner/run_hil_v3.py --port COM11 --output run-full`

Bench only: no pump, no VFD, no load. Do not connect live loads.

## Known follow-ups (do not affect the delivered binaries)

1. S1 revision of the STD-031 family frozen expectations (simulator oracle
   timer-restart defect; the real PLC matches the spec).
2. gxwlib simulator timer-reset modeling fix + local re-simulation.
3. GUI bench tool: script selection, six-language labels, batch polling —
   in development; subset runs above were produced with it.
