# Independent review 2 — program, execution and verdicts

Current final result: **PASS (2026-10-26)** for the hashes in the last incremental re-review; initial history is retained below.

- Reviewer: `/root/review_execution`, independent context, main agent not counted.
- Task ID: review-two-phase-2; owner: reviewer 2; date: 2026-10-24; scope: two-phase tool changes. Resource deadline: this bounded review turn; resources: own logs directory only, no serial clients or hardware, no GUI/process ownership.
- Initial verdict (2026-10-24): **CHANGES_REQUIRED** for the original reviewed input versions below. Latest focused conclusion is appended under 2026-10-26.
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

## Focused re-review — 2026-10-26

- Reviewer: same independent reviewer `/root/review_execution`; this follow-up closes the relevant findings and does not count as an additional independent reviewer.
- Task ID: review-two-phase-2-recheck-20261026; owner: reviewer 2; time bound: this review turn; resources: own `logs/review-two-phase-2` only. Completed without device/GUI/background-process ownership.
- **Current verdict: PASS for the reviewed local tool/execution scope and SHA256 inputs listed below.** R2-1, R2-2 and R2-3 are CLOSED. No new blocking code issue was found in this focused review. The 2026-10-24 findings above remain as the initial historical record.
- Git HEAD: `be13030ee2143e2c1956254f1c660a6c0fb4a9fe`. The reviewed working tree additionally contains modifications to `src/plcweave/projects.py`, `src/plcweave/workflow.py` and `tests/test_workflow.py`; HEAD alone does not identify the final reviewed content, so the SHA256 table is authoritative for this result. Ongoing skill/document synchronization is outside this focused code re-review.
- Environment boundary: actual local interpreter runs and synthetic hardware clients only; **no actual PLC HIL, vendor compile/import, serial connection, physical I/O, electrical or load PASS is claimed**.

### Checks actually executed

With `PYTHONPATH=src` and the repository `.venv/Scripts/python.exe`:

1. `-m pytest tests/test_workflow.py -p no:cacheprovider --basetemp=logs/review-two-phase-2/recheck-20261026 -q`: **31 passed in 11.61 s**, including both failing-core mutations, start release/hold, simultaneous-button stop priority, nonzero reset, changed-suite identity, cancellation, final-read timeout, missing input echo, cleanup/close failures, archive manifest differentiation and transient publication lock.
2. `-m pytest tests/test_markdown_projects.py tests/test_hil_guards.py tests/test_hil_candidate_identity.py -p no:cacheprovider --basetemp=logs/review-two-phase-2/related-20261026 -q`: **20 passed in 0.34 s**. These cover project isolation/delivery, frozen Markdown execution and tamper rejection, actual Bench identity/write gating and sampled read batching.
3. Independent additional executable probes: `logs/review-two-phase-2/probes-20261026.py`, retained results `logs/review-two-phase-2/probes-20261026/results.json`. This script creates only synthetic test projects in this review's own log directory and changes no implementation.
4. Read current reset handling, contract fingerprint generation, download/current-build validation, sampled HIL verdict/cleanup paths, `_publish` and delivery rollback. Initial attempt to include nonexistent `tests/test_projects.py` collected no tests; corrected immediately to the existing related test paths above. This was a command-selection issue, not a failing project test.

### Closure evidence

| Finding | Independent observed result | Conclusion |
| --- | --- | --- |
| R2-1: zero simulator defaults differed from nonzero HIL reset | Old counterexample with omitted D1001 and incorrect expectation M0=1 now returns LOCAL_FAIL, with PROGRAM_FAIL in **both** local variants. Correcting only the frozen test expectation to M0=0 yields SIM_PASS in both variants and PASS through the real run_hil orchestration with the synthetic latch. Current simulate applies design reset, runs reset scans and checks reset expectations before case inputs. | CLOSED |
| R2-2: changed frozen suite reused PLC identity | Independent 20 ms/30 ms suite builds retain identical canonical control-code hash but have different contract hashes and PLC fingerprint words. A real Bench instance supplied with the old build's synthetic register reads rejects verification against the new fingerprint; subsequent D1000 write is rejected and client write count remains **0**. Contract includes the frozen input hashes; host-side full hashes and explicit operator receipt remain. | CLOSED |
| R2-3: ZIP revalidation fixture violated project hierarchy | Committed extraction fixture now uses project/extracted; actual workflow test including ZIP integrity, content and extracted-build validation passes. Related delivery/project tests also pass. | CLOSED |

### New publication logic and exception behavior

- `_publish` was exercised through the committed transient-lock/no-overwrite test and independent persistent-lock probe. A continuously failing PermissionError causes exactly **5 rename attempts**, with scheduled delays **0.05 + 0.1 + 0.2 + 0.4 = 0.75 s**, then raises; the source remains and no destination is published. This measures the retry schedule, not an absolute upper bound on arbitrary filesystem operation latency.
- Independently forced archive publication failure after successful directory publication. The newly published version directory was removed, archive absent, owned `.package-*` staging removed, and original input unchanged. The committed pre-existing-destination test confirms refusal to overwrite and preservation of both pre-existing target and new source in this Windows environment.
- The workflow and packaging both use this bounded helper; `projects.py` remains included in BUILD tool hashes, so this behavior change invalidates an earlier build's tool binding rather than silently inheriting its acceptance.
- Current synthetic cancellation and timeout regressions verify report/trace preservation, no PASS after a final sample crosses the batch deadline, and cleanup/close handling. Missing consumption proof, cleanup failure and close failure remain TEST_INFRA_ERROR. The suite still distinguishes scalar PROGRAM_FAIL, evidence-limited UNVERIFIED, and qualified steady-state PASS. No broad claim of scan-exact or production hardware verification is introduced.

### Re-review input hashes (SHA256)

| File | SHA256 |
| --- | --- |
| `docs/PART-ONE.md` | `310f797286af6d69a3c801b0e1bea58343c7777c1f12afe81bec80c2becd3585` |
| `docs/PART-TWO.md` | `0f896bea36cbfda20e0bae6dbc802d6b8d9e0af1af455ff164bb9044393c3d2a` |
| `src/plcweave/workflow.py` | `42cf8cc7d27923cff2f6a5e4448267bde9b7eaec5cd5003be473156898c19f42` |
| `src/plcweave/variants.py` | `7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f` |
| `src/plcweave/testing.py` | `8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60` |
| `src/plcweave/hil.py` | `a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125` |
| `src/plcweave/validation.py` | `5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099` |
| `src/plcweave/markdown_suite.py` | `48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e` |
| `src/plcweave/fx.py` | `d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98` |
| `src/plcweave/projects.py` | `89d343847868a331e4854bd0f5eaee7230512fe1905cf515c0c81639d8d38653` |
| `tests/test_workflow.py` | `08333aefcca4653cc922b9dea58ecf7f0a8010abe39a97eb23366c8abb3f9354` |
| `tests/test_markdown_projects.py` | `0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f` |
| `tests/test_hil_guards.py` | `cb4074152379f146acb23376a8d2d491becfdba498b6a3cac7f9d4346af58bba` |
| `tests/test_hil_candidate_identity.py` | `8d7b7df4e6c98a0595b38bf2912927ae7e93df3159457892e5b53d0bb5dd6d1e` |
| engine binary (`_core.pyd`) | `21ebd9f071b3eafeff77f67bc22fcfe2829183047e45d2527b0f1f95816e9ff6` |

### Governance, cleanup and applicability

- Required local Hindsight search executed successfully, as did ZERO wake. ZERO returned a current response marked `data_freshness.overall=STALE`; it was not used as verification evidence for this code conclusion. Review conclusions come from current source and actual local test/probe runs.
- No implementation, customer project, serial port, GUI, process, shared service or global temporary directory was modified by this reviewer. All tool commands completed. Review-owned synthetic projects and probe outputs are retained in the isolated log directory for reproducibility; no background resource remains to close.
- Current conclusion is limited to the listed final hashes. Relevant source changes require focused recheck. This report is one reviewer's local tool review; it does not replace the other independent reviews or a customer's required hardware acceptance.

## Final incremental re-review — 2026-10-26

- Reviewer: `/root/review_execution`, same independent reviewer, limited follow-up after the preceding PASS; no additional reviewer counted.
- Task ID: review-two-phase-2-final-20261026; owner: reviewer 2; duration bound: this review turn; resources: only own report and `logs/review-two-phase-2`. Completed with no serial, GUI or background resources.
- **Final current verdict: PASS for the local tool/execution scope and final hashes below.** No new blocking issue found. The earlier findings and both preceding review records are preserved. This final hash table supersedes the earlier hash tables for current applicability.
- Scope of new reads: `require_reviews` uses POSIX relative paths; failed partial design-freeze writes remove only the target created by that invocation and its owned baseline/freeze; revision validates all three historical MD files against the old frozen hashes, checks copied snapshots and emits distinct normalized diff lines. Demo SUMMARY uses one new replay project name, three offline commands and a separate explicitly gated optional hardware sequence; V002 delivery avoids overwriting the offline V001.

### Focused actual checks

1. Ran `.venv/Scripts/python.exe -m pytest tests/test_workflow.py -k "partial_design or revision_rejects or requirement_diff or old_frozen_content or stage_one_zip or both_versions_receive or changed_input" -p no:cacheprovider --basetemp=logs/review-two-phase-2/final-related-20261026 -q` with `PYTHONPATH=src`: **12 passed, 24 deselected in 2.99 s**. This covers partial-write cleanup; each corrupted historical MD; no-final-newline diff; old snapshots surviving a user edit; canonical review-path packaging/revalidation; changed input gates and new-download requirements. The final 36-test workflow suite was not unnecessarily rerun in full by this reviewer.
2. Ran `.venv/Scripts/python.exe -m pytest tests/test_demo.py::test_delivery_reproduction_commands_run_offline_in_a_new_project -p no:cacheprovider --basetemp=logs/review-two-phase-2/final-demo-20261026 -q`: **1 passed in 0.87 s**. This executes all three generated offline command arguments through the actual CLI into a new replay project, checks its delivery, confirms no manual download/hardware report was invented, and checks the optional hardware block's required confirmation arguments. No hardware command was executed.
3. Ran independent `logs/review-two-phase-2/final-binding-20261026.py` using actual workflow build/download/report functions and only a synthetic Bench for replay. The previous reviewed build is now rejected with `Build tools changed` before Bench construction and before an evidence-batch directory is created. A fresh build validates, records the current `demo.py` SHA256 in `tool_sha256`, stores all S1 review paths as POSIX, and returns synthetic HIL PASS with consistent BUILD/download/trace hashes. This confirms tool changes require a fresh candidate while preserving identity and report binding; it does not claim hardware acceptance.
4. `projects.py` differs from the preceding reviewed content only by trailing blank lines; its publication logic is unchanged. Previously executed persistent-lock and rollback probes remain applicable to that behavior.

### Final input hashes (SHA256)

| File | SHA256 |
| --- | --- |
| `docs/PART-ONE.md` | `310f797286af6d69a3c801b0e1bea58343c7777c1f12afe81bec80c2becd3585` |
| `docs/PART-TWO.md` | `0f896bea36cbfda20e0bae6dbc802d6b8d9e0af1af455ff164bb9044393c3d2a` |
| `src/plcweave/workflow.py` | `43cc72d255193c3047ff6369ac55b434af334ea658aac678b1be91319ac4a020` |
| `src/plcweave/variants.py` | `7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f` |
| `src/plcweave/testing.py` | `8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60` |
| `src/plcweave/hil.py` | `a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125` |
| `src/plcweave/validation.py` | `5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099` |
| `src/plcweave/markdown_suite.py` | `48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e` |
| `src/plcweave/fx.py` | `d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98` |
| `src/plcweave/projects.py` | `0ab14695cd9eb2c6ed4937bab3158bbd57a6d98e56158d03612f7be5fd634b0c` |
| `tests/test_workflow.py` | `cbd5eeab9d67714b18fc3eb55191412a6c0a52451e85d8ada3e3f9f729f8d090` |
| `tests/test_markdown_projects.py` | `0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f` |
| `tests/test_hil_guards.py` | `cb4074152379f146acb23376a8d2d491becfdba498b6a3cac7f9d4346af58bba` |
| `tests/test_hil_candidate_identity.py` | `8d7b7df4e6c98a0595b38bf2912927ae7e93df3159457892e5b53d0bb5dd6d1e` |
| `src/plcweave/demo.py` | `eff8f13c870a08303090d0dd662ce8b16ad014cf40ea22c332cc9e6f77060b1e` |
| `tests/test_demo.py` | `b6268151a6a601c64ac737f48273fc5e5a7c53c7d2b5c8031ef56cce8a0b9c18` |
| engine binary (`_core.pyd`) | `21ebd9f071b3eafeff77f67bc22fcfe2829183047e45d2527b0f1f95816e9ff6` |

### Final boundaries and cleanup

Only the selected new checks were rerun; earlier unchanged program-generation, comparison, cancellation and identity findings retain the preceding evidenced scope. No PLC/vendor/physical I/O validation is claimed. All child commands completed, no port or user application was opened, and owned probe projects/results remain under the review log directory. Relevant later changes invalidate this final hash applicability and require only the affected follow-up checks.

## S1 exception-path-only follow-up — 2026-10-26

- Same independent reviewer `/root/review_execution`; task ID: review-two-phase-2-s1-final-20261026. Bounded read-only implementation follow-up; only this report and the owned hash snapshot were written.
- **Current verdict remains PASS for the preceding local execution/identity scope.** Actual read: diff and current body of `markdown_suite.freeze_markdown`, corresponding parameterized partial-freeze regression, and workflow tool-hash validation references. No additional execution test was run by this reviewer for this exception-only change; other reviewers' runs are not claimed here.
- The successful S1 content, source-before-freeze gate, no-overwrite exclusive open, hashes and parser remain unchanged. The new `created` flag becomes true only after successful exclusive file opening; write or close failure removes that invocation's partial `s1-freeze.md` and reraises. Existing freezes are rejected before opening and are preserved. The workflow's outer handler still removes its owned baseline when freeze creation raises. Parameterization now addresses both design-freeze and S1-freeze partial-write paths.
- No PLC instruction generation, comparator, execution, fingerprint derivation, download identity or report binding algorithm changed. `markdown_suite.py` remains included in `_tool_hashes`; its new hash intentionally invalidates an old candidate until rebuilt under current tools. The prior execution/identity conclusions therefore remain applicable to their unchanged algorithms, without treating a previously built candidate as current.
- Compared every file in the preceding final hash snapshot: **only the two files below changed**; all other final file hashes and the engine remain as previously listed. No full-suite rerun was warranted for this review scope.

| File | Final SHA256 (supersedes this file's earlier value) |
| --- | --- |
| `src/plcweave/markdown_suite.py` | `ed5f50aee5fe10452d208dd7620aa28b8c11bda2c5a6da6114eff5baaa16d4de` |
| `tests/test_workflow.py` | `7fdc38414f4f5385b4d1690ddaaba91876cc0360dcab8adbdd743ec920f8b763` |

No device/serial/GUI/background process was created. Final result does not claim physical or vendor validation. Initial history and prior executed results are retained.
