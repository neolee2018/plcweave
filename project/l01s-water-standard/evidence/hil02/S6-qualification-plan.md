# V002 S6 independent qualification plan

Task `PW-20261022-V002-HIL02`; owner `independent-s6-qualification`.
Frozen before the new adapter or any batch stimulus. The machine-readable
authority for this plan is `S6-qualification-plan.json`. This is test
infrastructure design, not a hardware result. The agent owns no serial port;
COM5/COM7 remain exclusively with the root executor.

The same frozen 55 MUST cases are retained: 52 bench, 3 local-only
(STD-017/018/023). Source, requirements, tests and freeze remain unchanged.
The original TraceOracle is called unchanged with `full_scan_trace=false` and
`verified_applied_inputs=false`; every applicable relation remains UNVERIFIED.
No polling result upgrades this to full-scan, electrical or HARDWARE_PASS.

## Evidence and quality

The independently inspected read-only baseline shows 37-watch read spans of
436.6716–442.1032 ms. Identity is 2/31, fingerprint 28642/27104, suite 2 on
both transports. Those spans cannot reproduce 10 ms/20 ms/100 ms actions or
precise endpoints. Read blocks and words are not atomic.

- Q0: failed transport/address/identity or proven failed stimulus is
  TEST_INFRA_ERROR; fix the tool, not the PLC.
- Q1: raw polling without a qualified timing/input chain is UNVERIFIED.
- Q2: an S1-derived stable scalar, independently verified held inputs, and
  the latest two equal complete observations inside the original allowed
  window and after settling qualify a scalar PASS or PROGRAM_FAIL.
- Q3: a conservatively bracketed event qualifies only under unchanged S1
  tolerances. Uncertainty remains part of the evidence, never extra tolerance.
- Supplemental convergence: extended observations are separately named,
  linked to S1, and cannot replace the original assertion or its timepoint.

Stability is a contract classification, never inferred from the actual value.
Normal PI D120/D154 and enabled AO depend on tick phase; equal repeated values
alone do not make exact endpoint comparison valid. D198/D199 are diagnostics,
not exact clocks. M10/M11 and state outputs also become ineligible near a timer
edge or if stretched earlier inputs can have accumulated enough real time.
Stopped outputs, fixed test-input scaling, initialized settings and independently
reached saturation plateaus can provide useful stable observations.

## Frozen pure interfaces

`evaluate_checkpoint(expectation, observations, *, quality,
stable_devices=(), phase_sensitive_devices=())` returns one result per device,
including missing/ineligible devices, with `device`, `expected`, `status`,
and `reason`. Each observation has `values`, `start_ms`, `end_ms`.
Quality fields are transport_ok, identity_ok, applied_inputs_verified,
settled_after_ms and checkpoint_window_ms. The original expectation and raw
evidence must not be mutated. One reading, a read crossing the window, a missing
value, a changing final pair or a phase-sensitive exact endpoint is UNVERIFIED.

`evaluate_timing_interval(*, trigger_ms, transition_ms, expected_ms)` returns
elapsed interval `[transition_lo-trigger_hi, transition_hi-trigger_lo]`.
PASS requires the entire interval inside the frozen acceptance interval;
PROGRAM_FAIL requires strict disjointness and a qualified stimulus chain.
Overlap (including a touching boundary) or a missing event is UNVERIFIED.
Sleep remains 4900..5100 ms, wake 2900..3100 ms and first full frequency
39800..40200 ms. Trigger bracket starts at the triggering write request and
ends at first effective D100/M10 confirmation; the event bracket starts at the
last unchanged poll request and ends at first changed poll response.

## Executable supplemental procedures

The JSON freezes 28 procedures with source-case references, inputs, expected
values and observation scope. Ten test initialized SV/default steady states
after true STOP/RUN. Others cover fixed clamp/rounding, active and saved SV,
command and invalid-mode inhibition, signed echo, zero-pressure first full
frequency plus saturation, D193 routing at that plateau, two sleep/wake cycles,
cancel-and-restart timing, and the actual jitter schedule/recovery. These are
additional register demonstrations. First-scan uniqueness, same-scan response,
PI recurrence and exact jitter timing remain explicitly unverified.

Each procedure starts from defaults/true CPU restart except the plateau gate
test, which must preserve its prerequisite saturation state. D261 is set before
STOP/RUN. CPU control checks expected identity, fingerprint and suite through
COM5; STOP disables Modbus, so recovery never relies on COM7. Both request/ACK
and read request/response intervals are recorded. Batches have deadlines and
finally restore CPU RUN, application stop, D193=0 and read-back zero outputs,
then close both ports. Incomplete cleanup is TEST_INFRA_ERROR.

## Independent fixture and acceptance record

`tests/test_sampled_backend.py` freezes positive stable evidence, stable actual
errors, legal phase-delayed values, missing/late/non-atomic observations, event
interval arithmetic and preservation of all original relation results.
`tests/test_cpu_v2_identity.py` accepts V002 and prevents a CPU frame after
any version, edition, fingerprint or suite mismatch. These tests use no serial
ports and read no PLC source. Their initial failures are retained separately.

Only a qualified PROGRAM_FAIL returns to S2. Ambiguous observations stay
UNVERIFIED. Final independent review must inspect raw traces, identity,
stimulus timing and cleanup, not only a summary report. No electrical or plant
validation is claimed.

Governance: Hindsight searched. Parent ZERO wake succeeded at snapshot1288
with underlying STALE; child credential access was restricted and no secret
was printed. No process, connection, lock or GUI resource was created by this
independent design/fixture work.

## Final execution projection decision

Independent qualification chooses capability audit for **all 55 original cases**
and actual execution of the **28 separately frozen supplemental procedures**.
Each original result states capability_only, retains every scalar assertion as
UNVERIFIED and calls the unchanged TraceOracle with false capabilities. Three
local-only cases remain explicit. The report must say that the original 55
hardware waveforms were not replayed. This avoids converting stretched serial
input histories into misleading original-case execution claims.

STD-049 and STD-055 each specify 340 seconds to cross a counter boundary under
a 10 ms local scan. On a substantially faster real CPU, waiting that wall time
without full-scan capture cannot prove the same counter sequence. Those waits
are omitted by this independent pre-execution decision; their missing scan
proof remains UNVERIFIED. Stable saturation/liveness demonstrations are linked
separately. The 1800-second batch budget is a resource bound and never an
assertion tolerance.
