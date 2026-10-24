# PLCWeave

**Test-driven PLC engineering for humans and AI agents.**

English | [简体中文](README.zh-CN.md)

Markdown requirements and tests → supported FX instruction execution → independent verification → controlled hardware sampling → traceable delivery. The first execution subset targets FX3U/HBDTECH L01S. This is an engineering toolkit under development, not a complete PLC simulator or certified production controller.

## 1. Install

### Prerequisites

| Component | Requirement |
| --- | --- |
| Python | Standard GIL-enabled CPython **3.13+**; 3.13 is recommended. The vendored binding does not support PyPy or free-threaded Python. |
| Rust | **1.93+**, Cargo and a native linker. The vendor's `rust-toolchain.toml` pins rustup to **1.93.0**. |
| Windows build tools | MSVC C++ Build Tools, Desktop development with C++, and a compatible Windows SDK. |
| Source | The complete repository, including `vendor/gxwlib`, `src`, `tools`, and `skills`. |

Clone the public repository, or extract its source archive:

```text
git clone https://github.com/neolee2018/plcweave.git
cd plcweave
```

Run commands from the directory containing `pyproject.toml`. Do not fetch missing files from a private sibling project.

Install missing system prerequisites using the official [Python](https://www.python.org/downloads/), [Rust/rustup](https://www.rust-lang.org/tools/install/), and [Windows Rust/MSVC](https://learn.microsoft.com/en-us/windows/dev-environment/rust/setup) instructions. Windows package-manager options include `winget install --exact --id Python.Python.3.13` and `winget install --exact --id Rustlang.Rustup`; the C++ workload/SDK must also be installed. Reopen the terminal afterward. Agents must respect host installation/elevation permissions.

### Windows / PowerShell

Use a dedicated venv; shell activation and global Python-package installation are unnecessary:

```powershell
py -3.13 --version
rustc --version
cargo --version
# With rustup, provision the vendor's requested toolchain/components:
rustup toolchain install 1.93.0 --profile minimal --component rustfmt --component clippy

py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m ensurepip --upgrade
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install ./vendor/gxwlib
./.venv/Scripts/python.exe -m pip install -e ".[test]"

./.venv/Scripts/python.exe -c "import gxwlib; from gxwlib import _core; print(_core.__file__)"
./.venv/Scripts/python.exe -m plcweave --help
New-Item -ItemType Directory -Force local | Out-Null
./.venv/Scripts/python.exe -m pytest -q tests --basetemp=local/pytest-readme
```

Do not overwrite an unrelated existing `.venv`. If `py` is unavailable, use the intended CPython executable's full path. Rustup commands are unnecessary when a compatible standalone Rust toolchain is already configured.

**Install the vendored runtime first.** PLCWeave alone does not install it. The upstream PyPI package with the same name may lack this repository's extensions; do not substitute it. Pip uses the vendor's [maturin configuration](https://www.maturin.rs/installation) to compile the native binding and initially needs network access for build dependencies/crates. No internal drives, original source project, company services, or `tools/import_runtime.py` are needed.

`tools/plcweave.ps1` selects the repository venv, configures source imports/UTF-8, and restores the caller's environment. If host policy blocks unsigned PowerShell scripts, use `./.venv/Scripts/python.exe -m plcweave ...` instead; do not change global execution policy.

### Linux / macOS

Install standard CPython 3.13 with venv support and Rust plus GCC/Clang/linker (Linux) or Xcode Command Line Tools (macOS). See the [official Rust guide](https://doc.rust-lang.org/book/ch01-01-installation.html). Then:

```sh
python3.13 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
rustup toolchain install 1.93.0 --profile minimal --component rustfmt --component clippy
.venv/bin/python -m pip install ./vendor/gxwlib
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -c 'import gxwlib; from gxwlib import _core; print(_core.__file__)'
.venv/bin/python -m plcweave --help
mkdir -p local
.venv/bin/python -m pytest -q tests --basetemp=local/pytest-readme
```

Verified on 2026-10-24 on Debian 13 (Linux aarch64), CPython 3.13, Rust 1.93.0: vendored build, full test suite and the no-hardware example pass. On Debian/Ubuntu install the C toolchain first (`sudo apt install build-essential`, otherwise cargo fails with ``linker `cc` not found``); if `python3.13 -m venv` reports that ensurepip is unavailable, install `python3.13-venv` or create the venv with `--without-pip` and bootstrap pip with `get-pip.py`. macOS has not been validated. On POSIX, replace the Windows CLI wrapper below with `.venv/bin/python -m plcweave` and create the shown UTF-8 files with an editor/agent file tool. The current PlatformIO adapter and offline development helper are Windows-specific.

Public toolkit tests use synthetic fixtures and do not require customer `project/` contents. Customer-specific integration tests remain in their private project directories. Record actual passed/failed/skipped counts; do not copy a private workspace's counts.

## 2. First run: no hardware

This example checks installation and the CLI. It does not contact a PLC, certify a customer program, or replace independent reviews. If `project/quickstart` exists, choose another name and update every path; do not delete existing evidence.

### A. Create the project and write tests before source

```powershell
./tools/plcweave.ps1 init quickstart
```

Only `requirements.md`, `test_cases.md`, and `README.md` are created. For a user-selected external folder: `init my-project --directory D:/PLCProjects/my-project`. Internal customer folders must be under `project/`.

Write the requirements and test **before creating `source.fxil`**:

```powershell
@'
# Requirements
R01: In virtual RUN, M0 shall be 1 on every observed scan.
R02: M0 stays within 0..1. No physical I/O is used.
'@ | Set-Content -Encoding utf8 project/quickstart/requirements.md

@'
# Test cases
## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0 |

## Invariants
| device | expected |
| --- | --- |
| M0 | 0..1 |

## TC-001: RUN indication
### Initial
| device | value |
| --- | --- |

### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | M0=1 | M0=1 | Observe two complete scans |
'@ | Set-Content -Encoding utf8 project/quickstart/test_cases.md

./tools/plcweave.ps1 freeze project/quickstart
```

`s1-freeze.md` binds both MD files' exact bytes. Draft/empty cases, unknown fields, ambiguous authoring sources, and an initial freeze attempted after source creation are rejected. The [MD format reference](.agents/skills/plc-program-development/references/markdown-cases.md) defines the tables. Tests are parsed in memory; no parallel test JSON/YAML authoring file is generated.

### B. Implement, then execute the frozen test

```powershell
@'
#meta
project: Quickstart
#instructions
LD M8000
OUT M0
END
#comments
M0 Virtual RUN indication
'@ | Set-Content -Encoding utf8 project/quickstart/source.fxil

./tools/plcweave.ps1 simulate project/quickstart
```

Expected: `TC-001 PASS`, final `SIM_PASS`, exit 0. This basic suite produces `candidate/V001/` inside the project: `MAIN.csv`, `COMMENT.csv`, `runtime.csv`, `simulation_report.json`, `simulation_trace.csv`. Rich independent-oracle suites currently default to `evidence/simulation/latest/`. Execution rechecks frozen inputs before returning. Never edit the freeze to make a failing test pass.

### C. Package smoke-test evidence

```powershell
./tools/plcweave.ps1 package project/quickstart --version smoke-V001 --file candidate/V001/MAIN.csv --file candidate/V001/COMMENT.csv --file candidate/V001/simulation_report.json
```

Expected: `project/quickstart/delivery/smoke-V001/` and `project/quickstart/delivery/quickstart-smoke-V001.zip`. The folder contains the selected files plus `MANIFEST.md` with SHA-256 hashes; the ZIP contains the same contents. Existing versions are rejected.

This is a **smoke evidence package**, not a formal customer delivery. Formal FX/L01S delivery requires reviewed `MAIN.csv`, `COMMENT.csv`, a test/setup/full-register-map PDF, and a same-source annotated instruction-list PDF, explicitly selected for packaging. The six-command CLI does not automatically generate complete manuals or download device programs.

## 3. Development workflow

| Stage | Work and evidence |
| --- | --- |
| S0 | Write `requirements.md`: model, I/O/address facts, behavior, faults, timing, reset, acceptance level and field authorization. Check measurement capability early. |
| S1 | Independently write `test_cases.md` covering normal/boundary/fault/recovery behavior. Complete required reviews, then freeze to `s1-freeze.md` before writing the new source. |
| S2 | Write `source.fxil`, export formats and execute supported instructions. Unknown instructions/forms/addresses must block, never become silent NOPs. |
| S3 | Compare actual execution traces/assertions; reviewers inspect evidence. Fix program defects or tooling defects separately. S2 cannot change frozen expectations. |
| S4 | Prepare a reviewable candidate with its actual validation level. Keep drafts in MD; generate formal presentation documents when delivery is needed. |
| S5/S6 | Follow the applicable authorized vendor/manual-download and bench route. Record what was actually tested; insufficient capture precision remains UNVERIFIED. |
| S7 | Run affected regressions/dependencies, complete reviews, create a project-local delivery folder plus ZIP, verify hashes, and release task-owned resources. |

**Four independent reviewers:** at S1 freeze, S3/major changes, S6 conclusions, and final-delivery review gates, use four distinct agents with fresh contexts. The main agent coordinates/fixes and does not count. Give each only relevant original artifacts, versions/hashes, acceptance criteria and resource boundaries—not the whole main conversation or a desired verdict.

Perspectives: requirements/tests; program/execution/verdicts; tooling/failure paths/identity/cleanup; isolation/documentation/delivery/reproducibility. Batch reviewers if concurrency is limited. Failed/unavailable reviewers mean incomplete review, not PASS. Do not impersonate four reviewers or silently waive the gate. Save actual checks/results in `reviews/<gate>/`; recheck affected findings after fixes. Reuse unchanged evidence only with matching version/hash and an explicit scope.

Separate `STATIC_PASS`, `SIM_PASS`, vendor checks, hardware observations and electrical/load tests. Core verdict distinctions are `PASS`, `PROGRAM_FAIL`, `TEST_INFRA_ERROR`, `UNVERIFIED`; commands also have their own summary statuses. `PROTOCOL_READ_PASS` from preflight proves neither application behavior nor electrical correctness.

```text
skills/ src/ tools/ tests/ vendor/ docs/      # toolkit, tests and documentation
project/
  customer-project/                         # ignored by public Git
    requirements.md  test_cases.md  s1-freeze.md
    source.fxil
    Doc/  evidence/  reviews/
    delivery/<version>/
    delivery/customer-project-<version>.zip
```

Every customer gets an independent folder; explicit external directories are supported. Customer artifacts never belong in toolkit code, tests, docs, or skills. New drafts are MD-only; legacy frozen JSON evidence can be read without rewriting it. Actual execution reports/traces may use JSON/CSV. Package only selected project deliverables—not environments, secrets, other customers, or the whole repository.

### Supported instruction subset (FX3U profile)

| Area | Executes in simulation | Not supported (compilation blocks) |
| --- | --- | --- |
| Bit logic | LD, LDI, AND, ANI, OR, ORI, OUT, SET, RST, ANB, ORB, MPS, MRD, MPP, END | Pulse contacts/outputs, STL/SFC, jumps, subroutines, interrupts |
| Timers/counters | T and C contacts, constant-preset OUT, RST | Variable presets, 32-bit and high-speed counters |
| Words | MOV, ADD, SUB, MUL, DIV (nonzero literal divisor), AND=/</<=/>/>= on signed 16-bit | 32-bit arithmetic, arithmetic flags, PID, indexed/indirect addressing |
| Devices | X/Y0–177 (octal), M0–7679, M8000–8511, T, C, D0–7999 (D8000–8511 as a plain word image) | Peripheral behaviour behind special registers (UART, ADC, DAC), power-cycle retention |

Anything outside this table is rejected, never silently turned into a NOP. Details: [runtime boundaries](docs/RUNTIME-CHANGES.md).

## 4. AI-agent execution instructions

Give an agent this repository and the following task:

> Read AGENTS.md, .agents/skills/plc-program-development/SKILL.md and its MD reference first. Identify OS, Python ABI/version, Rust and native compiler. Install missing prerequisites within host permissions; create/use a dedicated .venv; install ./vendor/gxwlib before .[test]. Actually run imports, CLI help, tests and the no-hardware example. Record commands, versions, failures and results; dependency errors do not justify PLC logic changes. Public installation requires no company services, sibling repository, customer case or globally installed skill. Create a fresh project/ subfolder unless the user specifies an external folder. Author MD requirements/tests, arrange four independent fresh-context reviewers at required gates, freeze before source, then execute and compare real traces. Never change expectations to fit implementation. Separate simulation/protocol/hardware/unverified results. Do not access devices or change RUN/STOP without field authorization and known mappings. Preserve previous evidence. Build the final project-local delivery directory and ZIP, verify hashes, and clean only owned resources. If a reviewer, prerequisite, permission, instruction or capture capability is unavailable, report the exact blocked step; do not fabricate completion.

The workflow skill lives in `.agents/skills/plc-program-development/`, the standard project-skill location: Codex discovers it automatically when started inside this repository (or invoke it with `$plc-program-development`), and AGENTS.md/CLAUDE.md tell other agents to read it before any PLC task. No global installation is needed. `tools/sync_plc_skill.py` updates an **existing legacy skill**, not a fresh general-purpose skill install. Hindsight/ZERO references apply only in configured company workspaces; public users need neither those services nor credentials.

## 5. Optional PlatformIO and hardware

### PlatformIO: current adapter is Windows-specific

Local simulation does not need PlatformIO. To use its task orchestration, install it into the project venv (tested baseline 6.1.19):

```powershell
./.venv/Scripts/python.exe -m pip install "platformio==6.1.19"
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) 'local/pio-core'
```

After initial MD drafting, create `project/quickstart/platformio.ini`:

```ini
[platformio]
default_envs = fx_demo
platforms_dir = ../../local/pio-platforms

[env:fx_demo]
platform = file://../../tools/pio-platform
custom_workspace = ../..
```

```powershell
./.venv/Scripts/python.exe -m platformio run --project-dir project/quickstart -t simulate
# If local platform source changes, refresh its installed copy before rerunning:
./.venv/Scripts/python.exe -m platformio pkg install --project-dir project/quickstart --platform file://../../tools/pio-platform --force
```

Relative paths assume that layout. External projects need absolute `platform = file://<toolkit-path>/tools/pio-platform`, absolute `custom_workspace`, and a deliberate cache location. See [PlatformIO installation guidance](https://docs.platformio.org/en/latest/core/installation/methods/pypi.html).

Default task: simulate. Preflight: read-only. Explicit bench: requires a project-local, independently qualified `custom_hil_script`, fresh `custom_hil_output`, and isolated-bench authorization. No generic qualified bench script is supplied for every customer. **Upload intentionally fails closed: no validated L01S application compiler/downloader is provided.** The adapter never treats the PLC as a generic MCU to replace its runtime firmware.

### Hardware prerequisites

```powershell
./.venv/Scripts/python.exe -m pip install -e ".[hil]"
./tools/plcweave.ps1 preflight project/my-project
./tools/plcweave.ps1 hil project/my-project --isolated-bench
```

These are gated commands, not a generic device tutorial. Configure a supported adapter and reviewed model/register map first. The current built-in L01S path uses COM7, station 1, 9600/8/N/1; there is no automatic port/model discovery. New MD cases need matching `build_identity.json`; HIL also needs a current `manual_download.json` binding source/test hashes and actual operator confirmation/time. No CLI generates these automatically. The legacy endpoint HIL rejects full-scan relationship suites; use a qualified sampled adapter.

SIM_PASS is not hardware acceptance. Polling cannot establish every-scan safety, terminal voltage/current, power-loss retention or a connected plant's performance. Boundaries: [runtime](docs/RUNTIME-CHANGES.md), [blueprint](docs/BLUEPRINT.md), [roadmap](docs/ROADMAP.md).

## 6. Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing pip | Run the selected venv Python's `-m ensurepip --upgrade`; keep using the same interpreter for pip. |
| Missing gxwlib / _core | Build/install `./vendor/gxwlib` in that venv; check Python ABI, Rust, native compiler/linker and logs. Do not substitute an unrelated wheel. |
| Missing plcweave | Install `-e ".[test]"`; use the intended venv or wrapper. Source-only execution needs PYTHONPATH=src. |
| Rust/MSVC/linker failure | Install missing compiler/workload/SDK, reopen terminal, retry the failed build; do not edit PLC expectations. |
| Download/permission error | Resolve the exact dependency's network/proxy/host permission issue and keep logs; do not disable certificate verification or claim an offline install succeeded. |
| Draft/changed freeze/dual sources rejected | Complete the contract or create a reviewed revision, without silently falling back to JSON or rewriting old freezes. |
| PlatformIO cannot find a new task | Refresh its installed local-platform copy as above; check source/version. |
| Insufficient capture precision | Keep UNVERIFIED, identify the missing measurement capability, and avoid widening tolerances/repeating unrelated full batches. |

`tools/build_runtime.py` is a Windows **offline development helper** requiring an existing venv, cached Rust crates and compiler—not a fresh installer. PDF generation needs separately selected rendering/document tools. The base install supplies neither proprietary engineering software nor vendor licenses.

## License

Original PLCWeave code: [Apache-2.0](LICENSE). Attribution: [NOTICE](NOTICE), [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). Vendored gxwlib: MIT with retained nested licenses/notices; preserve them when redistributing. Historical `docs/runtime-provenance.json` records origin, not an installation dependency. The no-hardware workflow needs no customer programs, proprietary manuals, credentials, GX Works2 installation or company services. PLCWeave is not affiliated with or certified by Mitsubishi Electric.
