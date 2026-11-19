# Independent toolchain review R3

- task_id: PW-20261022-MD-PROJECTS-R3
- owner: review_toolchain
- deadline: 15 minutes
- started_utc: 2026-10-22T15:11:40.710105+00:00
- ended_utc: 2026-10-22T15:11:43.642693+00:00
- resource ownership: task-owned project fixture; temporary external folder; CLI child processes with 30s timeouts; mocked Bench. No GUI, serial, PLC, credentials or customer files used.
- environment: .venv Python 3.13.2 with PYTHONPATH=src and -X utf8. Initial review harness import/encoding setup failures were corrected without modifying implementation or installed environment.

## Results

- PASS: default CLI init
  - exit=0; stdout=F:\000-HBDTECH-Neo\103-plcweave\project\R3-c39b6168f1; stderr_last=[]
- PASS: initial draft MD only

- PASS: empty draft freeze blocked
  - exit=1; stdout=; stderr_last=['ValueError: Case is incomplete']
- PASS: init overwrite blocked
  - exit=1; stdout=; stderr_last=["FileExistsError: [WinError 183] 当文件已存在时，无法创建该文件。: 'F:\\\\000-HBDTECH-Neo\\\\103-plcweave\\\\project\\\\R3-c39b6168f1'"]
- PASS: non-project internal directory blocked
  - exit=1; stdout=; stderr_last=['ValueError: Customer folders inside the toolchain must be under project/']
- PASS: executable MD freezes
  - exit=0; stdout=F:\000-HBDTECH-Neo\103-plcweave\project\R3-c39b6168f1\s1-freeze.md; stderr_last=[]
- PASS: freeze before source

- PASS: actual CLI MD simulation
  - exit=0; stdout=TC-001 PASS
{"status": "SIM_PASS", "cases": 1}; stderr_last=[]
- PASS: simulation binds MD SHA

- PASS: no test/requirements JSON generated

- PASS: CLI package archive integrity
  - exit=0; stdout={"folder": "F:\\000-HBDTECH-Neo\\103-plcweave\\project\\R3-c39b6168f1\\delivery\\V001", "archive": "F:\\000-HBDTECH-Neo\\103-plcweave\\project\\R3-c39b6168f1\\delivery\\R3-c39b6168f1-V001.zip"}; stderr_last=[]
- PASS: version overwrite blocked
  - exit=1; stdout=; stderr_last=['FileExistsError: Delivery version already exists']
- PASS: missing manual download blocks HIL
  - exit=1; stdout=; stderr_last=["FileNotFoundError: [Errno 2] No such file or directory: 'F:\\\\000-HBDTECH-Neo\\\\103-plcweave\\\\project\\\\R3-c39b6168f1\\\\manual_download.json'"]
- PASS: authorization guard before serial
  - Bench calls=0
- PASS: stale identity before serial
  - {'environment': 'hardware_protocol_preflight', 'port': 'COM7', 'writes': 0, 'status': 'TEST_INFRA_ERROR', 'error': 'Build identity is stale for current source; no serial access', 'cleanup': 'serial_closed'}
- FAIL: new MD missing identity blocked before serial
  - Bench calls=1; report={'environment': 'hardware_protocol_preflight', 'port': 'COM7', 'writes': 0, 'status': 'TEST_INFRA_ERROR', 'error': 'SERIAL_SENTINEL', 'cleanup': 'serial_closed'}
- PASS: requirements tamper blocked
  - exit=1; stdout=; stderr_last=['ValueError: Frozen S1 input changed: requirements.md']
- PASS: ambiguous MD/JSON blocked
  - exit=1; stdout=; stderr_last=['ValueError: Ambiguous test sources: keep one authoritative suite']
- PASS: unsupported opcode blocked
  - exit=1; stdout={"status": "BLOCKED", "cases": 0}; stderr_last=[]
- PASS: external directory MD-only init
  - exit=0; stdout=C:\Users\MasterNeo\AppData\Local\Temp\PW-R3-external-_dk7u2l5\customer; stderr_last=[]
- PASS: legacy JSON CLI simulation
  - exit=0; stdout=legacy PASS
{"status": "SIM_PASS", "cases": 1}; stderr_last=[]
- PASS: cleanup
  - Only task-owned fixtures removed. Child CLI processes completed. Real serial constructor never executed.

## Finding

The new Markdown V001 project without build_identity.json reaches Bench construction in preflight: candidate_bench checks only suite_version == V001 for its legacy fallback. It therefore treats a fresh MD customer project as the legacy hardware candidate, which would attempt COM7. A mock construction sentinel proves the path without contacting hardware. Restrict fallback to explicit legacy JSON or require a build identity for MD projects.

## Scope and evidence

Actual gxwlib scan simulation and CLI delivery packaging executed; hardware guards were tested with mocks only. No hardware verification is claimed. Report is the only persistent review output.

## Source SHA256

- src/plcweave/projects.py: 56b1ae3d856dc9789c7b99a3e658e330a67298022dbdb22f0fb484b4b93a5e44
- src/plcweave/markdown_suite.py: 0ebd0535cc96a4bc0e81eb50c8b25b4d17dbca0a147b6a52c24ae196f6b4e242
- src/plcweave/testing.py: a446e02c57666cf0ca14e3602afa5329e22e29532e0f830d5572c4fd5c49b7b3
- src/plcweave/hil.py: 9e71223b92d5b7fc7b5baf6e79e55e3324057302b2ff4719cb10efe576387e61
- src/plcweave/__main__.py: 3e78ab526dc4169204c0b4b25f3a7c738afd46708500a218413769b4a2fa5409

## Final re-review after identity fix

- reviewed_utc: 2026-10-22T15:15:42.013549+00:00
- Result: PASS; previous blocker resolved.

- PASS: final CLI init MD only
- PASS: final CLI MD freeze
  - F:\000-HBDTECH-Neo\103-plcweave\project\R3-final-46d9cf9f\s1-freeze.md
- PASS: final CLI actual simulation
  - TC-001 PASS
{"status": "SIM_PASS", "cases": 1}
- PASS: final CLI package ZIP content matches folder
- PASS: still no authored test/requirements JSON
- PASS: FIXED: new MD V001 preflight rejects absent identity before serial
  - {'environment': 'hardware_protocol_preflight', 'port': 'COM7', 'writes': 0, 'status': 'TEST_INFRA_ERROR', 'error': 'New candidate requires build_identity.json; no serial access', 'cleanup': 'serial_closed'}
- PASS: FIXED: authorized MD HIL still requires identity before serial
  - Bench calls=0
- PASS: legacy JSON V001 identity fallback preserved
  - Only a mocked constructor was invoked
- PASS: legacy JSON actual CLI remains compatible
  - legacy PASS
{"status": "SIM_PASS", "cases": 1}
- PASS: final cleanup
  - All task-owned fixtures and subprocesses released; no real serial client constructed

Final source SHA256:

- src/plcweave/projects.py: a10133a1a9a3c47db4415717fe4d8cb27f04506dd3f10066f74ecea3f3e9c863
- src/plcweave/markdown_suite.py: 48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e
- src/plcweave/testing.py: a446e02c57666cf0ca14e3602afa5329e22e29532e0f830d5572c4fd5c49b7b3
- src/plcweave/hil.py: a724127e61460ce924558e0aef7d1dc30b4b67f56cc4c14df75669e3b39c1336
- src/plcweave/__main__.py: 3e78ab526dc4169204c0b4b25f3a7c738afd46708500a218413769b4a2fa5409

## Repository CLI wrapper verification

- reviewed_utc: 2026-10-22T15:16:46.519247+00:00
- First external-caller probe location under OS temporary directory was denied by the process sandbox before wrapper startup (Resolve-Path). Repeated using the explicitly writable visualization root.
- PASS: tools/plcweave.ps1 --help, exit=0; launched from unrelated external directory with PYTHONPATH/PYTHONUTF8 unset.
- PASS: tools/plcweave.ps1 simulate, exit=2; launched from unrelated external directory with PYTHONPATH/PYTHONUTF8 unset.
- Wrapper SHA256: 46199f744bfae2ec9733ab926e11181c1764e51171af63bd6834c686228c0c4e
- Task-owned external caller directories cleaned; no environment install, hardware access or customer files used.
- Final R3 verdict: PASS; original MD identity blocker fixed and actual CLI flow reverified.
