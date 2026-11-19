# Independent Markdown contract review

- task_id: PW-20261022-MD-PROJECTS-R1
- owner: review_md_contract
- deadline: 30 minutes
- status: PASS — all identified findings independently closed on final rerun
- resources: this review created files only under logs/; no serial port, GUI, PLC, customer evidence, or credentials were accessed.
- startup: Hindsight search completed. ZERO is offline for this reviewer because its private credential read was denied by the sandbox; no credential content was printed or opened directly.

## Findings

1. **P1: empty checks can produce SIM_PASS.** Native Markdown containing a case/step but no global invariant, step invariant, or step expectation freezes successfully and actually simulates as SIM_PASS. This certifies no expected behavior. Reproduced by `test_empty_assertions_cannot_report_pass` in logs/review_md_probes.py.
2. **P1: imported Markdown suites bypass strict field checking.** A `plcweave-suite` block with schema_version=1 and an unknown step assertion key (`must_not_happen`) freezes and simulates as SIM_PASS while ignoring that key. parse_markdown returns the JSON mapping directly; validate_suite returns early for schema1. Reproduced by `test_imported_suite_unknown_step_assertion_rejected`.
3. **P2: duplicate case metadata silently overwrites prior values.** Two priority entries (MUST, then SHOULD) are accepted with the latter replacing the former. Suite metadata and initial words already reject duplicates, so case metadata should do so too. Reproduced by `test_duplicate_case_metadata_rejected`.

## Executed checks

- Existing tests: `.venv/Scripts/python.exe -m pytest tests/test_markdown_projects.py tests/test_independent_validation.py -q --basetemp=logs/review-md-pytest-20261022 --tb=short`, with PYTHONPATH=src: **22 passed**.
- Independent adversarial probes: `.venv/Scripts/python.exe -m pytest logs/review_md_probes.py -q --basetemp=logs/review-md-probes-20261022 --tb=short`, with PYTHONPATH=src: **3 failed** (the three findings above).
- Initial attempts without PYTHONPATH and with the system pytest temp folder were environment setup failures, then corrected. They do not count as product test failures.
- Existing passing checks include native MD simulation, both frozen-file tamper checks, no ambiguous MD/JSON fallback, no freeze overwrite, reject source before initial freeze, and numeric-schema legacy simulation compatibility.

## Cleanup

All commands completed. No background process, GUI, device connection, port, or lock was created. Synthetic project inputs and simulation artifacts remain under task-owned logs/review-md-* for reproducibility; no customer frozen input was changed. Implementation was not modified. Root was notified of blocking failures and the exact rerun command.

## Additional independently reproduced finding

4. **P1: an imported block silently overrides native executable tables in the same file.** A native table expects M0=0, then a valid imported block expects M0=1. With actual M0=1 the entire suite reports SIM_PASS, ignoring the visible native expectation. One MD must not contain two independently meaningful authoring forms with silent precedence. Reproduced by `test_import_block_cannot_override_native_executable_tables`; probes expanded to **4 failed**. Root notified.

## Second review after root corrections

- Re-ran original four independent probes plus existing Markdown and independent-validation tests: **27 passed**. The original four findings are resolved.
- Expanded independent boundaries: **4 passed, 4 failed**. Remaining findings:
  5. **P2: ambiguous schema types accepted.** Imported schema_version=true and schema_version=1.0 freeze successfully because Python equality treats both as 1. A schema identifier should have an explicit supported type.
  6. **P1: duplicate keys in imported JSON are silently overwritten.** Duplicate step expect keys (first M0=0, second M0=1) are accepted by ordinary json.loads; the first asserted behavior disappears before model validation.
  7. **P1: nonbinary external bit writes are coerced.** Native write X0=2, watch X0, expect X0=1, source containing only END: actual simulation reports TC1 PASS/SIM_PASS. testing.simulate converts non-D writes through bool(value). Invalid input is silently transformed into a valid value. Reproduction evidence: logs/review-md-bit-exec-x0. M0 input writes instead fail in the engine because set_inputs only accepts X; that separate probe was not a false pass.
- These expanded tests remain in logs/review_md_probes.py. Root was notified. Review remains BLOCKED pending correction and re-execution.


## Final independent decision — PASS

All seven identified findings (eight probe invocations because schema types are parameterized) are closed. The final implementation validates both native table and imported Markdown through `_validate_model`, rejects unsupported/ambiguous schema types, rejects duplicate imported object keys before mapping construction, rejects duplicate metadata and mixed native/import authoring, rejects cases without executable checks, rejects unknown executable fields, and rejects nonbinary bit input values.

Actual final independent runs, with PYTHONPATH=src:

- `.venv/Scripts/python.exe -m pytest logs/review_md_probes.py -q --basetemp=logs/review-md-final-probes-20261022 --tb=short`: **8 passed**.
- `.venv/Scripts/python.exe -m pytest logs/review_md_probes.py tests/test_markdown_projects.py tests/test_independent_validation.py -q --basetemp=logs/review-md-final-20261022 --tb=short`: **31 passed**.

Native MD freeze, real simulator execution, frozen-file tamper protection, ambiguous-source rejection, legacy scalar JSON compatibility, and all independently raised malformed-input paths were actually exercised. No claim is made here about hardware, GUI, document synchronization, or full delivery readiness; those are outside this review assignment. Historical BLOCKED entries above preserve the review trail and are superseded by this final decision.

Cleanup: all commands exited normally, no task-owned background resources remain. Only logs/ was written by this reviewer; synthetic test evidence remains there for audit. Permanent test copies under tests/ were created by root, not this reviewer.

Algorithm Hash                                                             Path
--------- ----                                                             ----
SHA256    48D8FEF550AF86B5F2DD1330DD651C963EBD07C781B5B3C479797649419FAA7E F:\000-HBDTECH-Neo\103-plcweave\src\plcweave…
SHA256    A446E02C57666CF0CA14E3602AFA5329E22E29532E0F830D5572C4FD5C49B7B3 F:\000-HBDTECH-Neo\103-plcweave\src\plcweave…
SHA256    D58C5713A2980B190835A61F5CAF5F7F6C578893C80A12D88EB78320D41C4ED3 F:\000-HBDTECH-Neo\103-plcweave\src\plcweave…


