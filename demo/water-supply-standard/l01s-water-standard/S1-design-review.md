# Independent S1 design review — STD-002

Identity: /root/s1_independent, fresh independent test-design agent. Task PW-20261022-STANDARD-REDO. No S2 program existed for this design stage; S2 has not started according to root coordination.

## Independence

Read only the frozen current requirements.md, s0-freeze.json, workflow.md and the3 authorized plc-program-development skill/template/SOP files. Did not read old/new PLC source, old tests, implementation engines, earlier reports, private/l01s-water, repository memory or private historical evidence. Did not run PLC simulation, serial, CPU control or GX. Python used only to serialize designed cases, verify schema/write permissions, calculate arithmetic expectations and hash artifacts. No outcomes are claimed here.

## Clarification before freeze

Raised P0 independently: level-start requests conflict with undefined new-start after invalid-mode recovery. Root explicitly accepted and revised S0 to revision2 before S1 freeze. Current interpretation requires a valid-mode zero then a later one. Invalid-mode zero alone is insufficient. Former requirements hash0d63d8594924339ad53c12b561a25e4a06b9e1921d3b9992405d38eba0dff3f1 is superseded; this suite binds only current hash7fdd5f7e380864c6ae1b25abfdd2289d98b176ea72fce9c14fc190d368892c4b.

Root also corrected its initial clock-phase briefing: initial M8012 may be high at t0; no50ms phase is assumed. The oracle uses actual observed rising edges and first20ms start steps precede the next edge after10ms boot. Exact100ms steps have one clock edge.

## Coverage and quality

55 MUST cases,10 mandatory independent relationship oracles. Four injection categories covered; signed raw and rounding boundaries; saved/online setpoint edges; strict equality/adjacent threshold checks; invalid command/mode/enable values; stop priority in all states; both timer cancellations including10ms glitches; nonaccumulating elapsed time; two complete sleep/wake cycles; integer division checkpoints; PI upper clamp and first saturation timing; full-scale/zero/jitter recovery; unused ADC independence; echo/counter wrap; serial/default/identity contract.

The scalar engine schema cannot express cross-register conditions, event timing, signed wrap, exact clock-based PI recurrence or identity fingerprint. All such assertions are explicit machine metadata in relationship_invariants and executable specifications in the English case document. S3 must implement/evaluate them independently and report assertion coverage; silently ignoring them cannot produce SIM_PASS.

PI arithmetic was independently derived: for SV60/PV50, tick n has A10n and frequency2100+n until a limit. For SV60/PV0 A=min(60n,30000); output2000+min(600+floor(A/10),3000), giving first5000 at tick400 and A cap at tick500. At SV60/PV57 error3 demonstrates floor(A/10) after accumulated errors3,6,9,12. Negative e cannot legally persist in normal state because pre-sleep starts at PV>=SV-2. Therefore tests drive negative-error input into pre-sleep and assert zero accumulator; they do not forge read-only D120. A negative-error PI-decrement branch is unreachable from this frozen interface and is not falsely claimed dynamically covered.

At minimum SV10, D260=D262=8. Wake may immediately reenter pre-sleep at equality. The oracle records a wake event and allows immediate pre-sleep; it does not require stable normal operation at overlapping thresholds.

## S3 acceptance and mutation checks

Run candidate through supported instruction interpreter; full frozen dictionary and relationship MUST assertions must pass. Supply independent fingerprint calculation and source/test hash binding. Demonstrate deliberately faulty programs rejected: missing stop priority; incorrect AO gate; PI every scan/incorrect integer divisor; accumulating timer across gaps; erroneous unused-channel source; immediate/silent unsupported NOP. Use isolated fixture variants without altering frozen suite. Unknown opcode/address is BLOCKED/TEST_INFRA_ERROR; missing oracle UNVERIFIED; healthy observed mismatch PROGRAM_FAIL. No S4 candidate before all local MUST assertions pass.

## Limitations and remaining verification

Dynamic suite is not electrical/physical validation, manufacturer compilation, private protocol validation or power-loss retention. Serial register observations prove initialized images only. Hardware polling cannot prove per-scan output/clock oracles. S3 must distinguish missing evidence from program failure. Fingerprint depends on later independent source canonicalization review; S1 cannot precompute an implementation hash before S2 exists. Static unknown-instruction/address enforcement is a required S3 tool-gate fixture, separate from dynamic candidate cases.

## Cleanup

No persistent processes, GUI project, connection, serial port or temporary file was created. Only the5 authorized S1 artifact files in this round directory are written.

## Final design-only audit

S3 reviewed fixed oracle enums and confirmed they are implementable without eval; REL-06 filter now uses stable case IDs, and PI/timer/identity parameters are explicit. Added invalid-mode stops in pre-sleep/sleep/wake-pending, dynamic wake threshold and active diagnostic wrap. Removed a read-only D195 initialization seed before final freeze; all initialization and external writes now obey the frozen bench whitelist. These are design-stage corrections made before S2 begins, without any implementation outcome feedback. Final suite:55 MUST cases,52 bench/3 local_only.

## S0 revision3 and final freeze

Second independent S1 boundary clarification: at SV10 both thresholds equal8, so R05 normal-wake wording needed an explicit overlap exception. Root revised S0 R05 before S2 started: at PV8, wake may immediately reenter pre-sleep and no minimum normal-state dwell is required. The previous draft freeze announcement was withdrawn when this need was identified. Former S1 attestation and freeze are retained unchanged in evidence/s1-before-overlap-clarification/ under explicit root authorization. S0 revision3 requirements SHA256: aafc680c5d7cfe8dc2d47826e5cfc2316c6fc19fbbd581d0a934e46d34a4f282. Only the requirements binding changed in test_cases.json; the55 cases, all expected values and10 relationship oracle definitions/parameters remained byte-equivalent as JSON values. No source execution or outcome feedback was used. Final case/oracle projection SHA256: ec29ba30d7e1b0def736749ef8a1c60d8edf0aa29708c620a67c2781885eb525.

The extra2 evidence copies were authorized after the initial5-artifact scope; no other process/connection/temp resources were created.
