# L01S Water Standard — Independent S1 Test Cases (STD-002)

S0 requirements SHA-256: `aafc680c5d7cfe8dc2d47826e5cfc2316c6fc19fbbd581d0a934e46d34a4f282`. All 55 cases are MUST. Each case starts from zero memory, seeds initial_words, executes an explicit10ms boot, then applies external writes. No PLC implementation was read or executed by S1.

## Execution and interpretation

Apply step writes once before execution. invariant is checked every postscan sample; expect only at step end. Preserve complete watched trace, applied external-input shadow and actual M8012. All10 relationship invariants are mandatory acceptance assertions. Missing oracle/observation is UNVERIFIED and blocks SIM_PASS. Exact100ms intervals span one observed clock rising edge; no50ms phase is assumed.

Bench prerequisites: verify identity before any write, confirm isolated equipment, verify register mapping/read-only transport, and control CPU initialization/reset per case. bench permits only specified bench input writes; local_only ADC image cases must never write physical ADC registers. Hardware polling cannot prove one-scan or exact tick assertions; mark them UNVERIFIED unless equivalent independently proven capture exists. Register-image testing does not verify electrical output, sensors/pumps, power-loss retention or GX.

## Requirement coverage

| Requirement | MUST cases |
|---|---|
| R01 | STD-001, STD-011, STD-012, STD-013, STD-014, STD-015, STD-019, STD-020, STD-021, STD-022, STD-023, STD-038, STD-039, STD-040, STD-041, STD-042, STD-043, STD-047, STD-049, STD-052, STD-053, STD-054 |
| R02 | STD-016, STD-017, STD-018, STD-019, STD-020, STD-021, STD-022, STD-023, STD-036, STD-044, STD-052, STD-053, STD-054 |
| R03 | STD-001, STD-002, STD-003, STD-004, STD-005, STD-006, STD-007, STD-008, STD-009, STD-010, STD-024, STD-025, STD-028, STD-035, STD-037, STD-051 |
| R04 | STD-031, STD-032, STD-033, STD-034, STD-035, STD-036, STD-037, STD-038, STD-039, STD-040, STD-041, STD-042, STD-044, STD-045, STD-047, STD-052, STD-053, STD-054 |
| R05 | STD-033, STD-034, STD-037, STD-038, STD-039, STD-040, STD-041, STD-046, STD-047, STD-051, STD-052, STD-053, STD-054 |
| R06 | STD-026, STD-029, STD-031, STD-032, STD-033, STD-034, STD-044, STD-045, STD-046, STD-055 |
| R07 | STD-026, STD-027, STD-028, STD-029, STD-030, STD-031, STD-033, STD-035, STD-036, STD-038, STD-039, STD-040, STD-041, STD-044, STD-050, STD-055 |
| R08 | STD-001, STD-011, STD-019, STD-020, STD-021, STD-022, STD-023, STD-026, STD-029, STD-030, STD-032, STD-033, STD-038, STD-039, STD-040, STD-041, STD-042, STD-043, STD-044, STD-052, STD-053, STD-054, STD-055 |
| R09 | STD-001, STD-048, STD-049, STD-050, STD-055 |
| R10 | STD-001 |

## Independent full-trace oracle contract

### REL-01 — state_output_consistency

At each postscan sample: M10 and M11 cannot both be1; either implies M0=1. If M0=0, M0/M10/M11/D120/D154/Y0/D8050/D8051 all0. If M11=1 then M0=1,M10=0,D120=D154=Y0=D8050=0. If M10=1 then M0=1,M11=0,D120=0,D154=2000. If M0=1 and M10=M11=0 then 2000<=D154<=5000. Invalid D190 always implies stopped vector that same scan.

### REL-02 — physical_routing

enabled := D193==1 and M0==1 and D154>0. Y0=int(enabled); D8050=(D154*4)//5 if enabled else0; D8051=0. Evaluate on each final scan image, including transitions, never endpoint-only.

### REL-03 — scaling_settings

If D190 in{0,1}, raw = D1056 if1 else D8030; expectedPV=(clamp(signed16(raw),0,4000)+12)//25; D100==expectedPV. D102=clamp(inputD102,10,160); D260=D102-2; D262=(D102*85)//100. D261 changes only first-scan invalid replacement or explicit external write. External request/input words persist unless explicitly written, except R09 first-scan defaults.

### REL-04 — independent_pi_recurrence

Observe actual M8012 input image on every scan, including boot. Rising edge iff current1 and previous0; do not assume50ms phase (environment correction: initial high may begin t0). Track independent A starting0. Stop/pre-sleep/sleep force A0 and frequency respectively0/2000/0. Entering normal from stopped/pre-sleep/sleep sets A0,f2000; skip PI on transition scan, and update only on a subsequent rising edge. On eligible rising edge, e=D102-D100; A=clamp(A+e,0,30000); increment=clamp(10*e+A//10,0,3000); f=2000+increment. All other normal scans hold previous A,f even if input or SV changes. Assert D120==A and D154==f every scan. Read frozen requirements and this recurrence only; never execute/translate S2 source to obtain expected values.

Frozen parameters: `{"clock": "M8012", "frequency_base": 2000, "increment_max": 3000, "increment_min": 0, "integral_divisor": 10, "integral_max": 30000, "integral_min": 0, "proportional_factor": 10, "skip_transition_scan": true}`.

### REL-05 — continuous_timers

Independently accumulate continuous running-not-sleeping PV>=D260 duration, reset on any below-threshold scan/stop/invalid. Sleep transition permitted only elapsed4900..5100ms (scan timestamp uncertainty<=10ms), requires pre-sleep first. In sleep track continuous PV<=D262; reset on any above-threshold scan/stop/invalid. Wake transition permitted only elapsed2900..3100ms. Sleep must persist in dead band. A transition MUST occur by upper bound if continuously qualifying. Track both timers afresh for every cycle; include one-scan cancellations. Qualification uses current clamped settings. Detect wake event even when SV10 means wake/pre thresholds overlap; do not demand durable normal state at overlapping thresholds.

Frozen parameters: `{"sleep_delay_ms": {"max": 5100, "min": 4900}, "timestamp_uncertainty_ms": 10, "wake_delay_ms": {"max": 3100, "min": 2900}}`.

### REL-06 — first_crossing_and_monotonicity

Measure first D154==5000 relative to first started normal scan; 39800<=elapsed<=40200ms. Throughout uninterrupted PV0 normal operation D120,D154 never decrease; A never exceeds30000, frequency never exceeds5000; by50.2s A30000 and f5000. Low-pressure normal run cannot enter sleep/pre-sleep.

Frozen parameters: `{"first_full_frequency_ms": {"max": 40200, "min": 39800}, "integral_saturated_by_ms": 50200}`.

Case filter: STD-029.

### REL-07 — diagnostics

From second observed postscan sample, signed16(D199_current-D199_previous)==1, including32767->-32768. Heartbeat D198 must change at100ms intervals (allow10ms timestamp quantization; no assumed numeric increment or initial value); no interval>110ms after initial startup. D195 equals externally supplied D194 on the next executed scan. D196=2,D197=31,D202=2 on every sample; D200/D201 remain stable.

Frozen parameters: `{"counter_delta_per_scan": 1, "counter_width_bits": 16, "heartbeat_interval_ms": 100, "timestamp_uncertainty_ms": 10}`.

### REL-08 — independent_fingerprint

S3 independently obtains final instruction list excluding dedicated BEGIN_IDENTITY/END_IDENTITY block; normalize exactly documented canonical algorithm supplied by S2, hash SHA256 and decode first4 bytes as two little-endian uint16 then signed16. Compare observed D200/D201 to those values and externally record full source/test hashes. Require specification-compatible canonicalization; do not merely call/trust S2 fingerprint checker. No fingerprint value known to S1 because S2 has not started. Hardware identity must be read and match BEFORE any test writes; mismatch TEST_INFRA_ERROR, not PROGRAM_FAIL.

Frozen parameters: `{"byteorder": "little", "bytes": 4, "excluded_block": ["BEGIN_IDENTITY", "END_IDENTITY"], "fingerprint_words": ["D200", "D201"], "hash": "sha256", "signed_word_width": 16}`.

### REL-09 — command_state_oracle

Only signed word1 asserts start/stop. Stop wins even with start held1; start latches run after request is removed. Invalid mode clears run and latches restart inhibit. Inhibit clears only after a valid-mode scan observes D191=0; a subsequent valid-mode D191=1 can start. D191=0 observed only during invalid mode does not clear inhibit. Valid-mode recovery while start remains1 must stay stopped. Stop/pre-sleep/sleep outputs clear in the same applied scan. Do not use implementation state flags as oracle inputs.

### REL-10 — serial_and_engine_gate

First scan M8196=M8125=1,D8120=signed16(0xE081)=-8063,D8121=1. S3 must verify static unknown instruction/address detection and independently run deliberate unsupported-instruction/address fixtures against the execution tool (not this candidate) to prove BLOCKED/UNSUPPORTED, never silent NOP. Missing serial observation or parser/engine capability is UNVERIFIED/TEST_INFRA_ERROR, cannot be called PASS. Physical serial protocol remains separate from register-image initialization.

## Reproducible cases

### STD-001 — First scan rejects preloaded requests and defaults external controls

Priority: MUST. Requirements: R01, R03, R08, R09, R10. Injection: normal_step. Scope: bench.
Initial words: `{"D190": 0, "D191": 1, "D192": 1, "D193": 1, "D194": 123, "D261": 0}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D190": 1, "D191": 0, "D192": 0, "D193": 0, "D194": 0, "D195": 0, "D196": 2, "D197": 31, "D202": 2, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "D8120": -8063, "D8121": 1, "M0": 0, "M10": 0, "M11": 0, "M8125": 1, "M8196": 1, "Y0": 0}` |
| 2 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-002 — Saved SV first scan -32768

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": -32768}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 60, "D261": 60}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-003 — Saved SV first scan -1

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": -1}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 60, "D261": 60}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-004 — Saved SV first scan 9

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 9}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 60, "D261": 60}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-005 — Saved SV first scan 10

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 10}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 10, "D120": 0, "D154": 0, "D260": 8, "D261": 10, "D262": 8, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 10, "D261": 10}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-006 — Saved SV first scan 11

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 11}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 11, "D120": 0, "D154": 0, "D260": 9, "D261": 11, "D262": 9, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 11, "D261": 11}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-007 — Saved SV first scan 159

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 159}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 159, "D120": 0, "D154": 0, "D260": 157, "D261": 159, "D262": 135, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 159, "D261": 159}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-008 — Saved SV first scan 160

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 160}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 160, "D120": 0, "D154": 0, "D260": 158, "D261": 160, "D262": 136, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 160, "D261": 160}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-009 — Saved SV first scan 161

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 161}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 60, "D261": 60}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-010 — Saved SV first scan 32767

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{"D261": 32767}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D102": 60, "D120": 0, "D154": 0, "D260": 58, "D261": 60, "D262": 51, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 100 | `{}` | `{"D102": 60, "D261": 60}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-011 — Start latches, requests persist, stop dominates simultaneous commands

Priority: MUST. Requirements: R01, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000, "D191": 1, "D193": 1, "D8050": 1600, "M0": 1, "M10": 0, "M11": 0, "Y0": 1}` |
| 3 | `{"D191": 0}` | 200 | `{"M0": 1, "M11": 0, "Y0": 1}` | `{}` |
| 4 | `{"D191": 1, "D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D191": 1, "D192": 1}` |
| 5 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0, "D192": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-012 — Non-one command words -32768 are unasserted

Priority: MUST. Requirements: R01. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D191": -32768, "D192": -32768}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D191": -32768, "D192": -32768}` |
| 3 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1}` |
| 4 | `{"D191": 0}` | 10 | `{}` | `{"M0": 1}` |
| 5 | `{"D192": -32768}` | 100 | `{"M0": 1, "M11": 0}` | `{}` |
| 6 | `{"D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-013 — Non-one command words -1 are unasserted

Priority: MUST. Requirements: R01. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D191": -1, "D192": -1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D191": -1, "D192": -1}` |
| 3 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1}` |
| 4 | `{"D191": 0}` | 10 | `{}` | `{"M0": 1}` |
| 5 | `{"D192": -1}` | 100 | `{"M0": 1, "M11": 0}` | `{}` |
| 6 | `{"D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-014 — Non-one command words 2 are unasserted

Priority: MUST. Requirements: R01. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D191": 2, "D192": 2}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D191": 2, "D192": 2}` |
| 3 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1}` |
| 4 | `{"D191": 0}` | 10 | `{}` | `{"M0": 1}` |
| 5 | `{"D192": 2}` | 100 | `{"M0": 1, "M11": 0}` | `{}` |
| 6 | `{"D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-015 — Non-one command words 32767 are unasserted

Priority: MUST. Requirements: R01. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D191": 32767, "D192": 32767}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D191": 32767, "D192": 32767}` |
| 3 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1}` |
| 4 | `{"D191": 0}` | 10 | `{}` | `{"M0": 1}` |
| 5 | `{"D192": 32767}` | 100 | `{"M0": 1, "M11": 0}` | `{}` |
| 6 | `{"D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-016 — Signed raw clamp and every rounding boundary class

Priority: MUST. Requirements: R02. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": -32768}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0, "D1056": -32768}` |
| 3 | `{"D1056": -1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0, "D1056": -1}` |
| 4 | `{"D1056": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0, "D1056": 0}` |
| 5 | `{"D1056": 12}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0, "D1056": 12}` |
| 6 | `{"D1056": 13}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1, "D1056": 13}` |
| 7 | `{"D1056": 24}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1, "D1056": 24}` |
| 8 | `{"D1056": 25}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1, "D1056": 25}` |
| 9 | `{"D1056": 37}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1, "D1056": 37}` |
| 10 | `{"D1056": 38}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 2, "D1056": 38}` |
| 11 | `{"D1056": 249}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 10, "D1056": 249}` |
| 12 | `{"D1056": 250}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 10, "D1056": 250}` |
| 13 | `{"D1056": 1237}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 49, "D1056": 1237}` |
| 14 | `{"D1056": 1238}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 50, "D1056": 1238}` |
| 15 | `{"D1056": 1250}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 50, "D1056": 1250}` |
| 16 | `{"D1056": 1449}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58, "D1056": 1449}` |
| 17 | `{"D1056": 1450}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58, "D1056": 1450}` |
| 18 | `{"D1056": 1462}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58, "D1056": 1462}` |
| 19 | `{"D1056": 1463}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 59, "D1056": 1463}` |
| 20 | `{"D1056": 3987}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 159, "D1056": 3987}` |
| 21 | `{"D1056": 3988}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160, "D1056": 3988}` |
| 22 | `{"D1056": 3999}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160, "D1056": 3999}` |
| 23 | `{"D1056": 4000}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160, "D1056": 4000}` |
| 24 | `{"D1056": 4001}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160, "D1056": 4001}` |
| 25 | `{"D1056": 32767}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160, "D1056": 32767}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-017 — AI0 selected instead of conflicting test input, AI1..3 unused

Priority: MUST. Requirements: R02. Injection: normal_step. Scope: local_only.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 4000, "D190": 0, "D191": 1, "D8030": 1250, "D8031": 4000, "D8032": -32768, "D8033": 32767}` | 100 | `{}` | `{"D100": 50, "D120": 10, "D154": 2101, "M0": 1, "M10": 0, "M11": 0}` |
| 3 | `{"D8031": 0, "D8032": 4000, "D8033": 0}` | 100 | `{}` | `{"D100": 50, "D120": 20, "D154": 2102}` |
| 4 | `{"D190": 1}` | 10 | `{}` | `{"D100": 160, "D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` |
| 5 | `{"D1056": 1250, "D8030": 0}` | 100 | `{}` | `{"D100": 50, "M0": 1, "M10": 0, "M11": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-018 — AI0 signed clamp/rounding independent of unused channels

Priority: MUST. Requirements: R02. Injection: normal_step. Scope: local_only.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D190": 0, "D8030": -32768, "D8031": -32768, "D8032": -32768, "D8033": -32768}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0}` |
| 3 | `{"D190": 0, "D8030": -1, "D8031": -1, "D8032": -1, "D8033": -1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0}` |
| 4 | `{"D190": 0, "D8030": 0, "D8031": 0, "D8032": 0, "D8033": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0}` |
| 5 | `{"D190": 0, "D8030": 12, "D8031": 12, "D8032": 12, "D8033": 12}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 0}` |
| 6 | `{"D190": 0, "D8030": 13, "D8031": 13, "D8032": 13, "D8033": 13}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1}` |
| 7 | `{"D190": 0, "D8030": 24, "D8031": 24, "D8032": 24, "D8033": 24}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1}` |
| 8 | `{"D190": 0, "D8030": 25, "D8031": 25, "D8032": 25, "D8033": 25}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1}` |
| 9 | `{"D190": 0, "D8030": 37, "D8031": 37, "D8032": 37, "D8033": 37}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 1}` |
| 10 | `{"D190": 0, "D8030": 38, "D8031": 38, "D8032": 38, "D8033": 38}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 2}` |
| 11 | `{"D190": 0, "D8030": 249, "D8031": 249, "D8032": 249, "D8033": 249}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 10}` |
| 12 | `{"D190": 0, "D8030": 250, "D8031": 250, "D8032": 250, "D8033": 250}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 10}` |
| 13 | `{"D190": 0, "D8030": 1237, "D8031": 1237, "D8032": 1237, "D8033": 1237}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 49}` |
| 14 | `{"D190": 0, "D8030": 1238, "D8031": 1238, "D8032": 1238, "D8033": 1238}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 50}` |
| 15 | `{"D190": 0, "D8030": 1250, "D8031": 1250, "D8032": 1250, "D8033": 1250}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 50}` |
| 16 | `{"D190": 0, "D8030": 1449, "D8031": 1449, "D8032": 1449, "D8033": 1449}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58}` |
| 17 | `{"D190": 0, "D8030": 1450, "D8031": 1450, "D8032": 1450, "D8033": 1450}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58}` |
| 18 | `{"D190": 0, "D8030": 1462, "D8031": 1462, "D8032": 1462, "D8033": 1462}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 58}` |
| 19 | `{"D190": 0, "D8030": 1463, "D8031": 1463, "D8032": 1463, "D8033": 1463}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 59}` |
| 20 | `{"D190": 0, "D8030": 3987, "D8031": 3987, "D8032": 3987, "D8033": 3987}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 159}` |
| 21 | `{"D190": 0, "D8030": 3988, "D8031": 3988, "D8032": 3988, "D8033": 3988}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160}` |
| 22 | `{"D190": 0, "D8030": 3999, "D8031": 3999, "D8032": 3999, "D8033": 3999}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160}` |
| 23 | `{"D190": 0, "D8030": 4000, "D8031": 4000, "D8032": 4000, "D8033": 4000}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160}` |
| 24 | `{"D190": 0, "D8030": 4001, "D8031": 4001, "D8032": 4001, "D8033": 4001}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160}` |
| 25 | `{"D190": 0, "D8030": 32767, "D8031": 32767, "D8032": 32767, "D8033": 32767}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D100": 160}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-019 — Invalid mode -32768 inhibits held-start recovery

Priority: MUST. Requirements: R01, R02, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{"M0": 1, "Y0": 1}` |
| 3 | `{"D190": -32768}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D190": -32768, "D191": 1}` |
| 4 | `{"D191": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D190": 1, "D191": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M11": 0, "Y0": 1}` |

D191=0 observed only in invalid mode cannot clear inhibit; valid-mode zero then later one is required by S0 revision 2.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-020 — Invalid mode -1 inhibits held-start recovery

Priority: MUST. Requirements: R01, R02, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{"M0": 1, "Y0": 1}` |
| 3 | `{"D190": -1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D190": -1, "D191": 1}` |
| 4 | `{"D191": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D190": 1, "D191": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M11": 0, "Y0": 1}` |

D191=0 observed only in invalid mode cannot clear inhibit; valid-mode zero then later one is required by S0 revision 2.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-021 — Invalid mode 2 inhibits held-start recovery

Priority: MUST. Requirements: R01, R02, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{"M0": 1, "Y0": 1}` |
| 3 | `{"D190": 2}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D190": 2, "D191": 1}` |
| 4 | `{"D191": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D190": 1, "D191": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M11": 0, "Y0": 1}` |

D191=0 observed only in invalid mode cannot clear inhibit; valid-mode zero then later one is required by S0 revision 2.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-022 — Invalid mode 32767 inhibits held-start recovery

Priority: MUST. Requirements: R01, R02, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{"M0": 1, "Y0": 1}` |
| 3 | `{"D190": 32767}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D190": 32767, "D191": 1}` |
| 4 | `{"D191": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D190": 1, "D191": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M11": 0, "Y0": 1}` |

D191=0 observed only in invalid mode cannot clear inhibit; valid-mode zero then later one is required by S0 revision 2.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-023 — Invalid mode blocks even simultaneous new start and output enable

Priority: MUST. Requirements: R01, R02, R08. Injection: normal_step. Scope: local_only.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D190": 2, "D191": 1, "D192": 0, "D193": 1}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 3 | `{"D190": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D191": 1}` | 20 | `{}` | `{"D154": 2000, "M0": 1, "Y0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-024 — Online active SV clamp recomputes both thresholds without saving

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D102": -32768}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 10, "D260": 8, "D261": 60, "D262": 8}` |
| 3 | `{"D102": -1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 10, "D260": 8, "D261": 60, "D262": 8}` |
| 4 | `{"D102": 9}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 10, "D260": 8, "D261": 60, "D262": 8}` |
| 5 | `{"D102": 10}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 10, "D260": 8, "D261": 60, "D262": 8}` |
| 6 | `{"D102": 11}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 11, "D260": 9, "D261": 60, "D262": 9}` |
| 7 | `{"D102": 59}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 59, "D260": 57, "D261": 60, "D262": 50}` |
| 8 | `{"D102": 60}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 60, "D260": 58, "D261": 60, "D262": 51}` |
| 9 | `{"D102": 61}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 61, "D260": 59, "D261": 60, "D262": 51}` |
| 10 | `{"D102": 159}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 159, "D260": 157, "D261": 60, "D262": 135}` |
| 11 | `{"D102": 160}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 160, "D260": 158, "D261": 60, "D262": 136}` |
| 12 | `{"D102": 161}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 160, "D260": 158, "D261": 60, "D262": 136}` |
| 13 | `{"D102": 32767}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{"D102": 160, "D260": 158, "D261": 60, "D262": 136}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-025 — Changing saved word online does not replace active SV

Priority: MUST. Requirements: R03. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D261": 42}` | 10 | `{}` | `{"D102": 60, "D260": 58, "D261": 42, "D262": 51}` |
| 3 | `{"D102": 100}` | 100 | `{}` | `{"D102": 100, "D260": 98, "D261": 42, "D262": 85}` |
| 4 | `{"D1056": 1250, "D191": 1}` | 100 | `{}` | `{"D102": 100, "D261": 42, "M0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-026 — Normal PI first two updates and hold between rising edges

Priority: MUST. Requirements: R06, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1}` | 20 | `{"D120": 0, "D154": 2000, "D8050": 0, "M0": 1, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 3 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |
| 4 | `{}` | 100 | `{}` | `{"D120": 20, "D154": 2102}` |
| 5 | `{"D193": 1}` | 100 | `{}` | `{"D120": 30, "D154": 2103, "D8050": 1682, "Y0": 1}` |

Each 100ms step spans exactly one actual rising M8012 edge; S3 also independently checks every scan against observed edges. No program was run to obtain these numbers.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-027 — Integer division PI fractional integral checkpoints e=3

Priority: MUST. Requirements: R07. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1425, "D191": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000}` |
| 3 | `{}` | 100 | `{}` | `{"D120": 3, "D154": 2030}` |
| 4 | `{}` | 100 | `{}` | `{"D120": 6, "D154": 2030}` |
| 5 | `{}` | 100 | `{}` | `{"D120": 9, "D154": 2030}` |
| 6 | `{}` | 100 | `{}` | `{"D120": 12, "D154": 2031}` |
| 7 | `{}` | 100 | `{}` | `{"D120": 15, "D154": 2031}` |
| 8 | `{}` | 100 | `{}` | `{"D120": 18, "D154": 2031}` |
| 9 | `{}` | 100 | `{}` | `{"D120": 21, "D154": 2032}` |
| 10 | `{}` | 100 | `{}` | `{"D120": 24, "D154": 2032}` |
| 11 | `{}` | 100 | `{}` | `{"D120": 27, "D154": 2032}` |
| 12 | `{}` | 100 | `{}` | `{"D120": 30, "D154": 2033}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-028 — PI uses latest online SV and persistent accumulator

Priority: MUST. Requirements: R03, R07. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{}` |
| 3 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |
| 4 | `{"D102": 80}` | 100 | `{}` | `{"D120": 40, "D154": 2304, "D260": 78, "D262": 68}` |
| 5 | `{"D102": 55}` | 100 | `{}` | `{"D120": 45, "D154": 2054, "D260": 53, "D262": 46}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-029 — Signal loss zero reaches full frequency in specified window and integral clamps

Priority: MUST. Requirements: R06, R07, R08. Injection: signal_loss. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 0, "D191": 1, "D193": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000}` |
| 3 | `{}` | 39700 | `{"M0": 1, "M10": 0, "M11": 0}` | `{"D154": {"max": 4999, "min": 2000}}` |
| 4 | `{}` | 600 | `{"M0": 1, "M10": 0, "M11": 0}` | `{"D154": 5000, "D8050": 4000}` |
| 5 | `{}` | 10500 | `{"D154": 5000, "D8050": 4000, "M0": 1, "M10": 0, "M11": 0}` | `{"D120": 30000}` |
| 6 | `{}` | 1000 | `{"D120": 30000, "D154": 5000, "D8050": 4000}` | `{}` |

e=60, A_n=min(60n,30000), f_n=2000+min(600+6n,3000). First full frequency at tick400 (39.8..40.2s after start); integral saturates tick500. S3 must measure first crossing, not just endpoint.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-030 — PI remains active while output gate disabled and exact routing floors

Priority: MUST. Requirements: R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{}` |
| 3 | `{"D193": 0}` | 100 | `{}` | `{"D120": 10, "D154": 2101, "D8050": 0, "Y0": 0}` |
| 4 | `{"D193": 1}` | 100 | `{}` | `{"D120": 20, "D154": 2102, "D8050": 1681, "Y0": 1}` |
| 5 | `{"D193": 0}` | 100 | `{}` | `{"D120": 30, "D154": 2103, "D8050": 0, "Y0": 0}` |
| 6 | `{"D193": 2}` | 100 | `{}` | `{"D120": 40, "D154": 2104, "D8050": 0, "Y0": 0}` |
| 7 | `{"D193": -1}` | 100 | `{}` | `{"D120": 50, "D154": 2105, "D8050": 0, "Y0": 0}` |
| 8 | `{"D193": 32767}` | 100 | `{}` | `{"D120": 60, "D154": 2106, "D8050": 0, "Y0": 0}` |
| 9 | `{"D193": -32768}` | 100 | `{}` | `{"D120": 70, "D154": 2107, "D8050": 0, "Y0": 0}` |
| 10 | `{"D193": 1}` | 100 | `{}` | `{"D120": 80, "D154": 2108, "D8050": 1686, "Y0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-031 — Pre-sleep equality, below adjacent value cancels, and timer restarts

Priority: MUST. Requirements: R04, R06, R07. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1425, "D191": 1}` | 100 | `{}` | `{"D120": 3, "M10": 0, "M11": 0}` |
| 3 | `{"D1056": 1450}` | 3000 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 4 | `{"D1056": 1425}` | 100 | `{"M0": 1, "M10": 0, "M11": 0}` | `{"D120": 3}` |
| 5 | `{"D1056": 1475}` | 3000 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 6 | `{"D1056": 1425}` | 100 | `{"M10": 0, "M11": 0}` | `{}` |
| 7 | `{"D1056": 1450}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 8 | `{}` | 400 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |

Total high time exceeds 5s before final interval. Timer must cancel rather than accumulate. Event oracle requires 4.9..5.1s continuously high before each sleep transition.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-032 — Pre-sleep does not complete at 4.8s; full-scale sleeps by 5.2s

Priority: MUST. Requirements: R04, R06, R08. Injection: full_scale_rush. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D1056": 4000}` | 4800 | `{"D120": 0, "D154": 2000, "D8050": 1600, "M0": 1, "M10": 1, "M11": 0, "Y0": 1}` | `{}` |
| 4 | `{}` | 400 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 5 | `{}` | 1000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-033 — Sleep persists above wake threshold and dead band, equality wakes

Priority: MUST. Requirements: R04, R05, R06, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1, "D193": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D1056": 1300}` | 4000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{"D100": 52}` |
| 4 | `{"D1056": 1425}` | 4000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 5 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{"D100": 51}` |
| 6 | `{}` | 400 | `{}` | `{"D154": {"max": 5000, "min": 2000}, "M0": 1, "M10": 0, "M11": 0, "Y0": 1}` |
| 7 | `{}` | 2000 | `{"M0": 1, "M10": 0, "M11": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-034 — Wake cancellation at adjacent above-threshold value and next-cycle reset

Priority: MUST. Requirements: R04, R05, R06. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D1056": 1275}` | 2000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 4 | `{"D1056": 1300}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 5 | `{"D1056": 1250}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 6 | `{}` | 400 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |
| 7 | `{"D1056": 1450}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 8 | `{}` | 400 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 9 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 10 | `{}` | 400 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |
| 11 | `{"D1056": 1250}` | 2000 | `{"M0": 1, "M10": 0, "M11": 0}` | `{}` |

Two complete sleep/wake cycles in one uninterrupted execution. Both timers must rearm and clear after cancellation/transition.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-035 — Changing SV changes pre-sleep threshold in same scan

Priority: MUST. Requirements: R03, R04, R07. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1}` | 100 | `{}` | `{"D120": 10, "M10": 0}` |
| 3 | `{"D102": 51}` | 10 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{"D260": 49, "D262": 43}` |
| 4 | `{"D102": 80}` | 10 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 0, "M11": 0}` |
| 5 | `{}` | 100 | `{}` | `{"D120": 30, "D154": 2303}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-036 — Large negative error/full-scale cannot wrap PI output

Priority: MUST. Requirements: R02, R04, R07. Injection: full_scale_rush. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D102": 10, "D1056": 0, "D191": 1}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |
| 3 | `{"D1056": 32767}` | 10 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{"D100": 160}` |
| 4 | `{}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-037 — SV lower and upper threshold boundaries remain operational

Priority: MUST. Requirements: R03, R04, R05. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D102": 10, "D1056": 175, "D191": 1}` | 100 | `{}` | `{"D100": 7, "M10": 0}` |
| 3 | `{"D1056": 200}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 4 | `{"D1056": 225}` | 3200 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 5 | `{"D1056": 200}` | 3200 | `{}` | `{"M0": 1, "M10": 1, "M11": 0}` |
| 6 | `{"D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D102": 160, "D1056": 3925, "D191": 0, "D192": 0}` | 10 | `{}` | `{}` |
| 8 | `{"D191": 1}` | 100 | `{}` | `{"D100": 157, "D260": 158, "D262": 136, "M10": 0}` |
| 9 | `{"D1056": 3950}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 10 | `{"D1056": 3425}` | 3200 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 11 | `{"D1056": 3400}` | 3200 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |

At SV10, wake threshold equals pre-sleep threshold (8); waking at equality may immediately reenter pre-sleep. Event oracle checks wake exists without requiring normal-state duration.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-038 — Stop same-scan overrides normal

Priority: MUST. Requirements: R01, R04, R05, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D191": 1, "D192": 1, "D193": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D191": 0, "D192": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 0, "M11": 0}` |
| 7 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-039 — Stop same-scan overrides pre_sleep

Priority: MUST. Requirements: R01, R04, R05, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D1056": 1450}` | 100 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` |
| 4 | `{"D191": 1, "D192": 1, "D193": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0, "D192": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 0, "M11": 0}` |
| 8 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-040 — Stop same-scan overrides sleep

Priority: MUST. Requirements: R01, R04, R05, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D1056": 1450}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 4 | `{"D191": 1, "D192": 1, "D193": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0, "D192": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 0, "M11": 0}` |
| 8 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-041 — Stop same-scan overrides wake_pending

Priority: MUST. Requirements: R01, R04, R05, R07, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D1056": 1450}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 4 | `{"D1056": 1250}` | 2000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 5 | `{"D191": 1, "D192": 1, "D193": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{}` | 200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 0, "D192": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 8 | `{"D1056": 1250, "D191": 1}` | 20 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 0, "M11": 0}` |
| 9 | `{}` | 100 | `{}` | `{"D120": 10, "D154": 2101}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-042 — Stop dominates a newly arriving full-scale condition

Priority: MUST. Requirements: R01, R04, R08. Injection: full_scale_rush. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 100 | `{}` | `{}` |
| 3 | `{"D1056": 4000, "D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{}` | 5200 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-043 — Enable gate toggles within normal/pre-sleep/sleep without starting application

Priority: MUST. Requirements: R01, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D193": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 3 | `{"D1056": 1250, "D191": 1}` | 100 | `{}` | `{"D8050": 1680, "Y0": 1}` |
| 4 | `{"D193": 0}` | 10 | `{}` | `{"D8050": 0, "M0": 1, "Y0": 0}` |
| 5 | `{"D1056": 1450, "D193": 1}` | 100 | `{"D120": 0, "D154": 2000, "D8050": 1600, "M0": 1, "M10": 1, "M11": 0, "Y0": 1}` | `{}` |
| 6 | `{"D193": 2}` | 100 | `{"D120": 0, "D154": 2000, "D8050": 0, "M0": 1, "M10": 1, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D193": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 8 | `{"D193": 0}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 9 | `{"D193": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-044 — Jitter 0/full-scale every100ms cannot accumulate sleep or deadlock

Priority: MUST. Requirements: R02, R04, R06, R07, R08. Injection: jitter. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 20 | `{}` | `{}` |
| 3 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 4 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 5 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 6 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 7 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 8 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 9 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 10 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 11 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 12 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 13 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 14 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 15 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 16 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 17 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 18 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 19 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 20 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 21 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 22 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 23 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 24 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 25 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 26 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 27 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 28 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 29 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 30 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 31 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 32 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 33 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 34 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 35 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 36 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 37 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 38 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 39 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 40 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 41 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 42 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 43 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 44 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 45 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 46 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 47 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 48 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 49 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 50 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 51 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 52 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 53 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 54 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 55 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 56 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 57 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 58 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 59 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 60 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 61 | `{"D1056": 0}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 0}` |
| 62 | `{"D1056": 4000}` | 100 | `{"M0": 1, "M11": 0}` | `{"M10": 1}` |
| 63 | `{"D1056": 1250}` | 2000 | `{"M0": 1, "M10": 0, "M11": 0, "Y0": 1}` | `{}` |

6 seconds of 100ms alternating signal loss/full scale; last high interval is canceled before five seconds. Require recovery to PV50 normal operation for at least2s.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-045 — Single-scan input glitches reset sleep qualification

Priority: MUST. Requirements: R04, R06. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 3 | `{"D1056": 1425}` | 10 | `{}` | `{"M10": 0, "M11": 0}` |
| 4 | `{"D1056": 1450}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 5 | `{}` | 400 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-046 — Single-scan wake-region exit resets wake qualification

Priority: MUST. Requirements: R05, R06. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 4 | `{"D1056": 1300}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 5 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 6 | `{}` | 400 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-047 — Stop during timer then restart does not reuse elapsed delay

Priority: MUST. Requirements: R01, R04, R05. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 3 | `{"D191": 0, "D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{"D192": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D191": 1}` | 4800 | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` | `{}` |
| 6 | `{}` | 400 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 7 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 8 | `{"D191": 0, "D192": 1}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 9 | `{"D1056": 1450, "D192": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 10 | `{"D191": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 11 | `{"D1056": 1275}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 12 | `{}` | 400 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-048 — Echo accepts all signed words on the next executed scan

Priority: MUST. Requirements: R09. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D194": 1}` | 10 | `{}` | `{"D194": 1, "D195": 1}` |
| 3 | `{"D194": 12345}` | 10 | `{}` | `{"D194": 12345, "D195": 12345}` |
| 4 | `{"D194": -1}` | 10 | `{}` | `{"D194": -1, "D195": -1}` |
| 5 | `{"D194": -32768}` | 10 | `{}` | `{"D194": -32768, "D195": -32768}` |
| 6 | `{"D194": 32767}` | 10 | `{}` | `{"D194": 32767, "D195": 32767}` |
| 7 | `{"D194": 0}` | 10 | `{}` | `{"D194": 0, "D195": 0}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-049 — Diagnostic signed counter wrap and heartbeat do not corrupt stopped outputs

Priority: MUST. Requirements: R01, R09. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{}` | 340000 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |

34,001 total scans from zero memory cross signed counter wrap. Assert modulo signed16 delta1 after each scan; no assumption about first-scan absolute counter.

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-050 — Diagnostics remain live during normal running without changing PI cadence

Priority: MUST. Requirements: R07, R09. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D194": -12345}` | 20 | `{}` | `{}` |
| 3 | `{}` | 2000 | `{}` | `{"D120": 200, "D154": 2120, "D195": -12345}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-051 — Online SV updates wake threshold while sleep remains latched

Priority: MUST. Requirements: R03, R05. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D1056": 1300}` | 2000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 4 | `{"D102": 62}` | 2800 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{"D260": 60, "D262": 52}` |
| 5 | `{}` | 400 | `{}` | `{"M0": 1, "M10": 0, "M11": 0}` |
| 6 | `{}` | 2000 | `{"M0": 1, "M10": 0, "M11": 0}` | `{}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-052 — Invalid mode same-scan clears pre_sleep and requires release/restart

Priority: MUST. Requirements: R01, R02, R04, R05, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1, "D193": 1}` | 100 | `{}` | `{"D120": 0, "D154": 2000, "M0": 1, "M10": 1, "M11": 0}` |
| 3 | `{"D190": 2}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{"D1056": 1250, "D190": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M10": 0, "M11": 0, "Y0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-053 — Invalid mode same-scan clears sleep and requires release/restart

Priority: MUST. Requirements: R01, R02, R04, R05, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1, "D193": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D190": 2}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 4 | `{"D1056": 1250, "D190": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M10": 0, "M11": 0, "Y0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-054 — Invalid mode same-scan clears wake_pending and requires release/restart

Priority: MUST. Requirements: R01, R02, R04, R05, R08. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1450, "D191": 1, "D193": 1}` | 5200 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` |
| 3 | `{"D1056": 1250}` | 2000 | `{"D120": 0, "D154": 0, "D8050": 0, "M0": 1, "M10": 0, "M11": 1, "Y0": 0}` | `{}` |
| 4 | `{"D190": 2}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 5 | `{"D1056": 1250, "D190": 1}` | 100 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 6 | `{"D191": 0}` | 10 | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` | `{}` |
| 7 | `{"D191": 1}` | 20 | `{}` | `{"M0": 1, "M10": 0, "M11": 0, "Y0": 1}` |

Result: __________  Evidence reference: __________  Reviewer/date: __________

### STD-055 — Diagnostic wrap during active PI cannot corrupt accumulator or outputs

Priority: MUST. Requirements: R06, R07, R08, R09. Injection: normal_step. Scope: bench.
Initial words: `{}`.

| Step | Write before execution | Duration ms | Every-scan invariant | End expectation |
|---|---|---:|---|---|
| 1 | `{}` | 10 | `{}` | `{"D120": 0, "D154": 0, "D8050": 0, "D8051": 0, "M0": 0, "M10": 0, "M11": 0, "Y0": 0}` |
| 2 | `{"D1056": 1250, "D191": 1, "D193": 1}` | 20 | `{}` | `{}` |
| 3 | `{}` | 340000 | `{"M0": 1, "M10": 0, "M11": 0, "Y0": 1}` | `{"D120": 30000, "D154": 5000, "D8050": 4000}` |

At PV50 error10 each100ms: accumulator saturates at tick3000. Full trace independent recurrence and routing cover signed D199 wrap while outputs are active.

Result: __________  Evidence reference: __________  Reviewer/date: __________

