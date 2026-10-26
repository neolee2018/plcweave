# Independent review 2 — program, execution and verdicts

- Reviewer: `/root/review_execution`, independent context, main agent not counted.
- Task ID: review-two-phase-2; owner: reviewer 2; date: 2026-10-24; scope: two-phase tool changes. Resource deadline: this bounded review turn; resources: own logs directory only, no serial clients or hardware, no GUI/process ownership.
- Verdict: **CHANGES_REQUIRED** for the reviewed input versions below.
- Boundary: real local interpreter and synthetic HIL orchestration were executed. No actual PLC, vendor compiler, physical terminal, electrical or load validation was performed. Synthetic review records and DummyBench reports are test fixtures, never customer or hardware acceptance evidence.

## Actual checks

1. Read `docs/PART-ONE.md`, `docs/PART-TWO.md`, the local workflow skill and the listed implementation/test files. Compared common-core generation, production I/O routing, identity/download gates and verdict aggregation against those targets.
2. Executed `.venv/Scripts/python.exe -m pytest tests/test_workflow.py -p no:cacheprovider --basetemp=logs/review-two-phase-2/pytest-temp -q` with `PYTHONPATH=src`: **18 passed, 1 failed** in 3.95 s. The first attempted run lacked the parent of the requested basetemp and produced 19 setup errors; creating this review's parent and rerunning resolved that environmental setup error.
3. Executed the independent counterexamples in `logs/review-two-phase-2/probes.py`, using the real local interpreter for both program variants and the real `run_hil` control flow with only `Bench` replaced by the tiny synthetic latch fixture. No device was opened. Observed reset discrepancy and unchanged PLC identity after a changed frozen suite, detailed below.

## Blocking findings

### R2-1 [P1] Simulation and HIL start the same frozen case from different injection defaults

Locations: `src/plcweave/workflow.py:196`, `src/plcweave/workflow.py:352`, `src/plcweave/testing.py:116`.

`run_hil` applies every declared `HIL reset` injection, waits, verifies reset expectations, and then overlays case initial values/step writes. `simulate` creates a fresh simulator with zero defaults and overlays only `initial_words`; the design reset is not provided. Omitted inputs therefore mean different values in the two phases, even with unchanged core, suite and environment semantics.

Reproduction: use the repository's synthetic design with `D1001=1` as stop/reset, but a single steady-state step `D1000=1`, expectation `M0=1`, leaving D1001 unwritten. Both local variants return SIM_PASS and build returns LOCAL_PASS; `run_hil` on the correct synthetic latch returns PROGRAM_FAIL, actual M0=0, because the runner correctly preserved stop=1. This mismatch is generated entirely by the tool's different test setup. It can misclassify setup differences as a program defect and direct the next action toward modifying the common core.

Required result: one explicit effective initial-input model for local HIL variant, mapped production variant and hardware replay, or reject under-specified cases before building; make reset expectations and timing semantics consistent. A regression should include a nonzero reset injection that is intentionally omitted from first-step writes.

### R2-2 [P2] Runtime suite identity is an unchecked manually supplied number

Locations: `src/plcweave/workflow.py:188`, `src/plcweave/variants.py:231`, `src/plcweave/hil.py:96` (identity comparison region).

The host BUILD manifest binds test SHA256, but runtime D202 is only `design.settings.suite_word`; no rule binds it to the frozen suite or prevents reuse. The canonical fingerprint excludes all identity instructions. An independently frozen revision changing every step from 20 ms to 30 ms while retaining the same common core and design produced identical complete `hil/source.fxil`, `identity.json`, fingerprint words and suite word. The read-only PLC identity gate therefore cannot distinguish those suite revisions. New host-side download receipt remains required, which limits the exposure, but does not establish the required PLC-side binding to the current suite.

Required result: derive the runtime suite/build identity from the current frozen suite and program inputs, or enforce a verifiable version/change rule so reusing a suite identifier cannot silently accept a changed suite. Retain full host hashes and explicit operator download confirmation.

### R2-3 [P2] The committed workflow regression suite has a failing delivery revalidation test

Location: `tests/test_workflow.py:249` and `src/plcweave/projects.py:22`.

`test_stage_one_zip_contains_four_categories_two_programs_and_no_hardware_claim` extracts under `tmp_path/extracted`, then passes `workspace=tmp_path` to validate_build. Customer directories inside that workspace are restricted to project/, so `_location` rejects it with `ValueError: Customer folders inside the toolchain must be under project/`. ZIP creation/readability assertions succeeded before the failure. This is a test setup defect and does not by itself prove a ZIP content defect. Fix the extraction fixture to remain within the allowed project hierarchy (or explicitly external workspace) and rerun the committed check.

## Positive observations and limits

- Both variants are generated from the same parsed control-core list. Production substitutes physical inputs, routes declared outputs, and omits HIL initialization, injected inputs and identity/heartbeat instructions. The executed two-variant test confirms this for the synthetic supported subset; it is not vendor equivalence evidence.
- Unsupported core instructions and direct physical I/O access are blocked; high-word MUL resource overlap is explicitly checked. Local unknown instructions are not treated as NOP.
- BUILD binds author sources, frozen design, generated artifacts, S1 records, Python tool files and engine binary. Artifact/source changes block execution. Download receipts bind the selected build, HIL source/import file, operator, software string, compile success and RUN confirmation. Software is recorded as an operator-supplied string; no vendor compiler is invoked.
- HIL limits writes to declared injections and compares read-back logical input images against applied inputs. Outputs are sampled rather than written by the orchestrator. Identity failures produce no writes and always close the synthetic client in the executed regression.
- Comparator preserves missing values as UNVERIFIED, scalar mismatches as PROGRAM_FAIL. The workflow keeps continuously asserted invariants UNVERIFIED under polling, records communication errors as TEST_INFRA_ERROR, and does not upgrade production hardware coverage from the HIL result.
- Changed common core/build cannot inherit an old download receipt. New build IDs, explicit next-action guidance, and selection of one complete final HIL batch avoid assembling PASS from multiple versions. The tool does not itself run an unbounded repair/re-download loop.

## Inputs (SHA256)

| File | SHA256 |
| --- | --- |
| `docs/PART-ONE.md` | `5f63d0af6e3278a119e3dae3273d7c07f7dc767fa78935dc5e2cc43f40d1931e` |
| `docs/PART-TWO.md` | `3894fb7dc12da0160db3c3dc5c8da5020ccb35cad48bec406c111009be6e9aa6` |
| `src/plcweave/workflow.py` | `3636a6be825bc25057177449e7448d17490b32fb865d52c8ac10900f6d91f848` |
| `src/plcweave/variants.py` | `7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f` |
| `src/plcweave/testing.py` | `d497f27a50451cc03c40a419d07496e2c1d8dba937689f8729ac32d41155c692` |
| `src/plcweave/hil.py` | `a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125` |
| `src/plcweave/validation.py` | `5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099` |
| `src/plcweave/markdown_suite.py` | `48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e` |
| `src/plcweave/fx.py` | `d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98` |
| `src/plcweave/projects.py` | `61fbeb8e69c19d2a4f16ac8c5e738e51a805b7c134042e3f462833744e722fe4` |
| `tests/test_workflow.py` | `7a3806c820b67d24e0510f25fb3607c64147df1be34f79826242f194ca0319ba` |

## Resource cleanup and follow-up

- All executed commands returned; no background worker, serial port, lock or GUI application was opened by this reviewer. Temporary synthetic projects and probe script are retained only in `logs/review-two-phase-2` as diagnostic evidence. No global cleanup was attempted.
- Only this report and this review log directory were written. Relevant implementation or fixture changes require focused re-review and refreshed hashes; this conclusion does not automatically cover later edits.
