# L01S water standard rerun V002

> Customer demo runbook (3 steps: offline script test → GX Works2 download → delivery):
> [demo/water-supply-standard/README.md](../../demo/water-supply-standard/README.md).
> Current program version is **V006** (see `versions/V006/`, `lab-tests/V006/` and the notes below).

User requested a full standard workflow redo after the V001 process audit.
Current stages and actual evidence are in workflow.md and evidence/events.jsonl.
Do not copy V001 test results into this run.

requirements.md is the frozen behavior/interface. Independent S1 precedes new S2
source. Simulator/static results and hardware/vendor results are distinct.
Use lab-tests/MAIN.csv and COMMENT.csv only after independent S3 passes.
The user's fresh V002 manual-download confirmation is recorded in manual_download.json.

No sensors or actuators are connected. This case demonstrates fixed-point PI
(derivative zero), pressure scaling, sleep/wake and guarded output routing.

2026-10-22 S6: PlatformIO executed two complete batches of 28 independently
frozen bench supplements. Both batches: 24 PASS, 4 UNVERIFIED, no proven program
or infrastructure failure. The second batch improves deadline sampling under
independently frozen RED/GREEN fixtures, without changing PLC source or any
expectation/tolerance. Final repository tool regression: 78 passed.

Original 55 full-scan cases remain hardware UNVERIFIED. The four supplemental
UNVERIFIED results cover integral deadline, two-cycle timing, cancel timing and
exact jitter waveform; saturation plateau, routing and jitter recovery are
separately observed. This is a scoped bench demonstration, not a V1 release.

Latest Chinese report: Doc/bench-V002/Validation-Report_CN.md.
Customer four-piece folder: delivery/V002-bench-demo/four-piece-set/ (legacy copy in delivery-docs/V002-bench-demo/).
Evidence: evidence/hil02/run01/ and run02/, plus independent reviews and exit check.
Final CPU RUN, original force flags restored, application stopped, D193=0,
M0/M10/M11/D120/D154/Y0/D8050/D8051 all zero. Both serial ports closed.

Reproduce in the existing PLCWeave environment: choose a new custom_hil_output
in platformio.ini, then explicitly select PlatformIO's bench target. Existing
evidence directories are rejected. Default target remains simulate; upload
remains a manual-download gate. Do not run against connected loads.

2026-10-23 bench check: a read-only probe at 21:25 (zero writes) found the PLC
was **not** running V002 (D196=4, D202=1, fingerprint 29415/10550, no heartbeat).
The operator re-flashed V002 (518 GX steps / 176 instructions); at 22:09 the
identity gate passed: D196=2, D197=31, D200=28642, D201=27104, D202=2, D198
advancing. A soft-element smoke loop then passed: D190=1/D102=60/D1056=1250/
D193=1/D191=1 -> M0=1, Y0=1, D100=50, D154=2102, D8050=1681; D194=12345 ->
D195=12345; D192=1 -> all outputs zero. No case verdict was issued.

Measured on the bench: scan period ~0.244 ms (4096 scans/s) and write ACK
~28 ms. The 10 ms scan model does not apply to scan-count conversions; 100 ms
timer semantics are unaffected.

2026-10-23 S6 v3 batch (soft-element injection + output readback + COM5 STOP/RUN):
53 of 55 frozen cases executed — 30 PASS, 23 UNVERIFIED (every compared item
matched; running PI instants and timer edges left unverified), 0 PROGRAM_FAIL.
This includes the ten first-scan saved-SV cases (real STOP/RUN), the 5-23 s timer
cases, the 100 ms jitter case and both 340 s counter-wrap cases. Evidence:
evidence/s6-v3/SUMMARY.md; raw runs in evidence/s6-v3/run-v3-*/.

Remaining: STD-017/018 need an ADC override hook in a V003 program (writing
D8030 is overwritten by the ADC within 50 ms — measured), see
Doc/S6-plan-V003.md section 8.

2026-10-24 V003 built for exactly that: D1071=1 with D190=0 substitutes the
parallel AI0 bench input D1070 for D8030; D1071=0 keeps the real AI0 path
unchanged. Program version 3, suite 3, fingerprint [7757,-31026], 182
instructions; local S3 is 55/55 SIM_PASS and the GX CSV check is PASS.
Flash lab-tests/V003/MAIN.csv + COMMENT.csv; identity then reads
D196=3,D197=31,D200=7757,D201=-31026,D202=3.

V003 has been flashed and re-run in full: **55 cases, 31 PASS, 24 UNVERIFIED,
0 PROGRAM_FAIL**. STD-018 passes all 224 comparisons through the parallel AI0
input; STD-017 passes every compared item (running PI instants stay UNVERIFIED).
All ten first-scan cases, both 340 s wrap cases and the 100 ms jitter case pass.
The V002 results above remain bound to V002 and are not reused for V003.
Evidence: evidence/s6-v3/SUMMARY-V003.md.

Customer bench kit (program + frozen suite + scripts + English procedure) is
packaged at delivery/V003-bench-kit/ and
delivery/l01s-water-standard-V003-bench-kit.zip (13 files, hashed manifest).

The revised S6 method (L01S default profile) is in docs/S6-HIL-V2.md; the
project rollout plan, case classes and run03/run04/run05 schedule are in
Doc/S6-plan-V003.md. Probe evidence: evidence/s6-v3/readonly-probe-20261023.json
and evidence/s6-v3/soft-element-smoke-20261023.json.

2026-11-08 V005 fix (batch interface D300–D335, self-latch bug fixed): after
three HIL rounds the final batch run-v5-full-fix2 reached **31 PASS /
31 UNVERIFIED / 0 PROGRAM_FAIL** on all 62 frozen cases (STD-005), reviewed by
four independent-context agents (0 blockers). UNVERIFIED items are scoped
(round-3 summary §2/§5): running-PI phase values, ±1-tick deadline sampling,
the STD-031 simulator-oracle family and system words. GUI bench-tool subset
runs on 2026-11-10 (4 × 10 cases, 3 PASS / 7 UNVERIFIED each) exercised the
in-development GUI runner. Open follow-ups: S1 revision of the STD-031 family
expectations, gxwlib timer-reset modeling fix, GUI feature completion.

Customer bench kit (program + frozen suite + batch runner + English docs +
evidence summary, 20 files, hashed manifest) is packaged at
delivery/V005-fix-bench-kit/ and
delivery/l01s-water-standard-V005-fix-bench-kit.zip.
