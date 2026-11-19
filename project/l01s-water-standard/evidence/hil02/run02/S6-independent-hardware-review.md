# Independent S6 hardware evidence review — run02

Decision: **ACCEPT_SCOPED_BENCH_EVIDENCE**. Task PW-20261022-V002-HIL02. Reviewer independent-s6-review.

All **28** frozen supplemental procedures actually executed: **24 PASS, 4 UNVERIFIED**, zero PROGRAM_FAIL or TEST_INFRA_ERROR. The four UNVERIFIED procedures are SUP-ZERO-SATURATION, SUP-TIMER-TWO-CYCLES, SUP-TIMER-CANCEL and SUP-JITTER-ACTUAL-SCHEDULE. All original **55** cases remain a capability-only UNVERIFIED audit; their hardware scan waveforms were not replayed.

Independent raw audit checked 8,269 trace records, 5,311 transactions, 394 verified input writes, 2,477 reconstructed reads, 192 identity-gated CPU force operations and 27 true CPU restarts. All 933 stable scalar assertions across 121 observations and seven event intervals were independently recomputed. Discrepancies: 0. Frozen qualification, capture-policy, candidate and report hashes match.

First full frequency qualified within the unchanged 39,800–40,200 ms tolerance. The final accumulator/output plateau and output gate observations passed. The independently frozen capture refinement collected 6 near-deadline D120 reads, including one complete 30000 response before 50,200 ms and its second response after the deadline. It correctly retained UNVERIFIED for the deadline pair; no tolerance or expectation was changed.

The six sleep/wake event intervals still overlap the lower tolerance boundary, so neither PASS nor PROGRAM_FAIL is proven. Post-event stable state observations passed. Jitter recovery passed its sampled stable observations, while the exact 100 ms waveform and full trajectory remain UNVERIFIED. Run01 and its independent review remain unchanged in the run01 archive. No further rerun is needed to chase a PASS.

Cleanup confirms CPU RUN, restored original control flags, application stopped, zero accumulator/frequency/Y0/AO0/AO1 observations, reported closed ports and absent owned lock. This review used only files and created no serial connection or GUI. No full HARDWARE_PASS, same-scan safety, exact PI recurrence, electrical, plant, power-loss retention or binary-readback claim is supported.

A subsequent read-only exit check was also audited independently: 17 trace records contain only read operations; the snapshot was reconstructed from raw Modbus responses and the COM5 identity frame checksum/data were decoded. CPU RUN, stop request 1, enable 0, zero stopped outputs, restored control flags, reported closed ports and absent lock were confirmed. No writes were issued by that check.
