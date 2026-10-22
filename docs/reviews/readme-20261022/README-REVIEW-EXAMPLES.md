# README executable example review — R3

- task_id: PW-20261022-README-R3
- owner: readme_examples_review
- started: 2026-10-22T23:45:42.579449+08:00
- deadline: 20 minutes from assignment
- scope: README section 2 executable no-hardware walkthrough, platform caveats, repository links
- environment: Windows; existing repository .venv, CPython 3.13.2
- resources: F:\000-HBDTECH-Neo\103-plcweave\project\readme-review-r3-20261022-234542; bounded child PowerShell processes only; no GUI, serial, device, credentials or system install
- Hindsight: search completed before task
- ZERO: OFFLINE; official wake entry failed with PermissionError loading protected credentials; credentials not printed

## Inputs

- `README.md`: `26eb045fd74d754462f69cd30cfb6d09ee612c53d9f603563a5063aad75ca662`
- `README.zh-CN.md`: `719ba2f5dc7b0ae392d9fbc1d3456b565c159cfcb0964e7f61033181fbf8e9b7`
- `src/plcweave/__main__.py`: `3e78ab526dc4169204c0b4b25f3a7c738afd46708500a218413769b4a2fa5409`
- `src/plcweave/markdown_suite.py`: `48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e`
- `src/plcweave/testing.py`: `a446e02c57666cf0ca14e3602afa5329e22e29532e0f830d5572c4fd5c49b7b3`
- `src/plcweave/projects.py`: `a10133a1a9a3c47db4415717fe4d8cb27f04506dd3f10066f74ecea3f3e9c863`

## Execution

Both language versions contain the same four executable section-2 PowerShell blocks. The only substitution was every lowercase `quickstart` occurrence -> `readme-review-r3-20261022-234542`. No optional installation/hardware blocks were executed.

### Block 1 — exit 0

```text
F:\000-HBDTECH-Neo\103-plcweave\project\readme-review-r3-20261022-234542

```

Checked init created exactly three MD files and no source.

### Block 2 — exit 0

```text
project\readme-review-r3-20261022-234542\s1-freeze.md

```

Checked freeze contains both exact byte SHA-256 values and source is absent.

### Block 3 — exit 0

```text
TC-001 PASS
{"status": "SIM_PASS", "cases": 1}

```

Checked real report: `SIM_PASS`, TC-001 PASS, 2 complete scan samples, M0=1 at 10 ms and 20 ms. Frozen byte hashes remain unchanged.

```json
{
  "environment": "local_instruction_simulator",
  "engine_binary_sha256": "21ebd9f071b3eafeff77f67bc22fcfe2829183047e45d2527b0f1f95816e9ff6",
  "source_sha256": "742ca65c702df5f627e33d3df64430c744646ab8a184099008392c6f6b825219",
  "test_sha256": "0af1d8d0ac5382ffcdc72baa04e1f637358be0def2252bed0216b4c914698df8",
  "suite_version": "V001",
  "scan_ms": 10,
  "instruction_count": 3,
  "cases": [
    {
      "id": "TC-001",
      "status": "PASS",
      "scans": 2,
      "failures": [],
      "scalar_violation_count": 0
    }
  ],
  "limits": [
    "No vendor or hardware equivalence claimed",
    "ADC/DAC and UART are external register images",
    "No power-cycle retention model"
  ],
  "comparator_sha256": "d58c5713a2980b190835a61f5caf5f7f6c578893c80a12d88eb78320d41c4ed3",
  "status": "SIM_PASS"
}
```

```csv
case_id,step,time_ms,M0
TC-001,0,10,1
TC-001,0,20,1
```

### Block 4 — exit 0

```text
{"folder": "F:\\000-HBDTECH-Neo\\103-plcweave\\project\\readme-review-r3-20261022-234542\\delivery\\smoke-V001", "archive": "F:\\000-HBDTECH-Neo\\103-plcweave\\project\\readme-review-r3-20261022-234542\\delivery\\readme-review-r3-20261022-234542-smoke-V001.zip"}

```

## Package verification

Checked delivery folder contains exactly the three explicitly selected files plus MANIFEST.md. All three manifest SHA-256 values match both delivery and original candidate bytes. ZIP CRC check passes, member set matches exactly, and every ZIP member matches the delivery folder byte-for-byte.

```markdown
# Delivery manifest

| File | SHA256 |
| --- | --- |
| MAIN.csv | 63aad2b9557d74dae9702885c7a1ea642e05853eeedc708a2efba67360a3d129 |
| COMMENT.csv | 8a1fa2f1e7c9bec495658c9e94b50d0e2e2a9b0e4d07b47fb7d25c25a0f07764 |
| simulation_report.json | 81799ba6adc7af83219eb619f161093b046c0eaf9ea4d73ceb1296e4a013b84e |
```

- archive SHA256: `be15e735c8261dd6980ddd32a60f60e917d0e6b3967b8d5e180e3311b75539e4`

Additional read-only installed-module check: `local/readme-install-review/Scripts/python.exe -m plcweave --help` exit 0; all six commands listed. Environment was not modified.

## Documentation checks

- `README.md`: every local Markdown link resolves.
- `README.zh-CN.md`: every local Markdown link resolves.
- Both versions explicitly mark Linux/macOS source-install routes as not locally validated, identify Windows local validation, provide POSIX venv/CLI paths, and state PlatformIO/offline helper Windows specificity.
- No missing local links or executable example defects found.
- Scope limitation: this review did not reinstall dependencies, rebuild Rust, run optional PlatformIO/hardware commands, validate external website targets, or claim customer/hardware acceptance.

## Conclusion

PASS — README no-hardware walkthrough is executable as written on the existing Windows environment.

## Cleanup

PASS: exactly the owned project was removed; no project files, delivery archive or temporary child process remain. All child processes completed under timeout. No GUI/serial/device connections were allocated.

- finished: 2026-10-22T23:45:45.449054+08:00
