# README bilingual/public-use independent review

task_id: PW-20261022-README-R4  
owner: readme_bilingual_review  
deadline: 10 minutes  
started: 2026-10-22 (fresh independent reviewer context)  
completed_utc: 2026-10-22T15:46:23.070717+00:00  
resources: read-only repository inspection, short-lived Python/PowerShell child processes; output limited to this report. No serial port, GUI, PLC, system installation or credential access. No subagent.

## Input versions

| File | SHA-256 |
| --- | --- |
| README.md | 26eb045fd74d754462f69cd30cfb6d09ee612c53d9f603563a5063aad75ca662 |
| README.zh-CN.md | 719ba2f5dc7b0ae392d9fbc1d3456b565c159cfcb0964e7f61033181fbf8e9b7 |

## Actual checks

- Independently read both complete READMEs; compared against pyproject.toml, vendor/gxwlib/pyproject.toml, vendor/gxwlib/Cargo.toml and rust-toolchain.toml. CPython >=3.13, Rust >=1.93 / rustup 1.93.0, maturin/PyO3 native build and package extras match the inspected metadata. Vendor-first installation correctly reflects that the main package does not declare gxwlib as an install dependency.
- Compared all 10 PowerShell/sh/ini fenced executable blocks after removing comment-only lines: exactly equivalent across the two languages. In particular, installation, freeze-before-source, simulation, selected-file packaging, PlatformIO and optional HIL commands agree.
- Checked every relative Markdown link in both files: all exist (language counterpart, MD reference, runtime boundaries, blueprint, roadmap, LICENSE, NOTICE and THIRD_PARTY_NOTICES).
- Scanned both READMEs for absolute local user/internal workspace paths: none found. Generic external-project path examples are explicitly illustrative. No private sibling repository is required by their installation route. Source provenance is distinguished from an installation dependency.
- Read AGENTS.md, repository skills/plc-program-development/SKILL.md and MD reference. Both READMEs preserve separate customer project folders, MD-only initial authoring, exact-byte S1 freeze before PLC source, four distinct independent fresh-context agents (main agent excluded), incomplete-review handling, version/hash scope and project-local delivery folder plus ZIP.
- Read CLI, projects.py, testing.py, markdown_suite.py, hil.py, tools/plcweave.ps1, tools/pio-platform/builder/main.py, tools/sync_plc_skill.py and tools/build_runtime.py. Six CLI choices and documented output locations align; chosen-file smoke evidence is explicitly distinguished from formal two-CSV/two-PDF delivery; uploader fails closed; preflight is read-only; HIL requires explicit isolated-bench authorization and identity/manual-download evidence; no automatic download or RUN/STOP action is advertised.
- Confirmed README clearly labels the current execution subset, Windows-only adapter/helper, unvalidated POSIX source-install route and planned/unsupported hardware capability. Separate simulation/protocol/hardware/electrical validation levels are retained in both languages.
- Executed existing-venv native import successfully: CPython 3.13.2, gxwlib._core import succeeded. Executed repository wrapper --help successfully, displaying the six documented commands and flags.
- Parsed the README MD test example directly in memory using the real parser (mocked Path.read_text; no customer files created): V001, scan_ms=10, watch=[M0], 1 case. This checks example schema validity, not simulation acceptance.

## Findings and conclusion

No blocking mismatch found. PASS for bilingual consistency and the reviewed documentation/public source-install instructions at the exact hashes above.

Observed environment limitation: direct existing-venv `python -m plcweave --help` initially reported No module named plcweave, while repository-wrapper help succeeded. The current pre-existing venv has the native runtime but has not installed this checkout as a Python package. Both READMEs already prescribe editable main-package installation and explain source imports, so this is not a documentation defect. This reviewer did not install packages, run the full test suite, perform a clean-room install, execute the quickstart simulation or qualify any hardware. No such acceptance is claimed.

## Cleanup

All commands completed; no background process, serial connection, GUI project, lock or temporary customer artifact was created. Python bytecode writes were disabled for dynamic checks. Only this review report was written by this reviewer. No user process or shared service was changed.
