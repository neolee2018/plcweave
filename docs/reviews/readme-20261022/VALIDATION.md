# Bilingual README validation

- Scope: README.md (English) and README.zh-CN.md (Simplified Chinese), source installation, first-run tutorial and AI workflow.
- Four distinct fresh-context reviewers completed: installation, workflow, executable examples, bilingual/public-facing consistency. Per-review evidence and limits are in the four adjacent reports.
- Isolated Windows standard CPython3.13 venv: ensurepip, vendored gxwlib native source build, editable PLCWeave/test install, independent import location, CLI help and pip check passed. Existing OS-level Rust/MSVC and Cargo compilation cache were used; no installed gxwlib binary was copied.
- Actual documentation PowerShell tutorial: project init, MD-only authoring, freeze-before-source, two-scan SIM_PASS and evidence package passed; hashes, ZIP CRC and bytes checked. Synthetic project removed.
- Full current repository regression from the independently installed environment, without PYTHONPATH: 97 passed in 0.57s, 0 skipped. Public checkouts without private customer cases may skip optional integration tests; these local counts are not a claim about all hosts.
- Both documents: 10 executable code-block groups equivalent; all local Markdown links exist; no local username/internal drive dependency.
- No Linux/macOS, fresh OS prerequisite installation, PLC, serial, RUN/STOP, GUI, electrical or production acceptance was performed.
- Initial reviewer-notification usage-limit errors were recorded; subsequent completion was confirmed. They were not substituted for a review.

- README.md SHA256: `26eb045fd74d754462f69cd30cfb6d09ee612c53d9f603563a5063aad75ca662`
- README.zh-CN.md SHA256: `719ba2f5dc7b0ae392d9fbc1d3456b565c159cfcb0964e7f61033181fbf8e9b7`
