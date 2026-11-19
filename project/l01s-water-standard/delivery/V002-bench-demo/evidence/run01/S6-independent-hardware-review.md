# Independent S6 hardware evidence review — run01

Decision: **ACCEPT_SCOPED_BENCH_EVIDENCE**. Task PW-20261022-V002-HIL02. Reviewer independent-s6-review.

All 28 frozen supplemental procedures actually executed: **24 PASS, 4 UNVERIFIED**, zero PROGRAM_FAIL or TEST_INFRA_ERROR. This is separate from the original 55 cases: all remain capability-only and UNVERIFIED; no original hardware scan waveform was replayed.

Independent raw-file audit checked 8,257 trace records, 5,305 transactions, 394 verified input writes, 2,471 reconstructed read snapshots, 192 identity-gated CPU force operations and 27 true CPU restarts. All 933 stable scalar assertions across 121 observations and seven event intervals were independently recomputed without discrepancies. SHA-256 bindings and frozen requirements/tests remain unchanged.

The first 5000 frequency observation brackets 39,914.085–40,057.998 ms, wholly within the unchanged 39,800–40,200 ms interval. The final accumulator/output plateau passed. The deadline cap check correctly remains UNVERIFIED: its only two D120 samples were 29940 at 50,078.884 ms and 30000 at 50,106.297 ms, insufficient for two equal complete observations by 50,200 ms. A further complete read could have captured useful evidence; run01 must retain its original result.

All six sleep/wake timing intervals overlap the lower tolerance boundary. Their UNVERIFIED verdicts are correct: serial trigger/poll uncertainty prevents proving either timely operation or a program defect. Jitter recovery passed its stable observations; the exact 100 ms waveform and full-scan safety trajectory remain UNVERIFIED.

Cleanup evidence confirms CPU RUN, original control flags restored, application stopped, D120/D154/Y0/AO0/AO1 zero, reported closed ports and absent owned serial lock. The reviewer never opened a serial connection or GUI. No electrical, plant, retention, binary-readback or full HARDWARE_PASS claim is supported.

A new independently frozen capture-only refinement may continuously poll D120 near the existing deadline and require the final two complete nonoverlapping 30000 observations before earliest-trigger + 50,200 ms. It must not extend tolerance, turn an early 29940 sample into failure, or relabel run01.
