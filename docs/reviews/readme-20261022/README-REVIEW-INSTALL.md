# README independent installation review — R1/4

- task_id: PW-20261022-README-R1
- owner: readme_install_review
- deadline: 20 minutes from delegation
- scope: source installation reproducibility and actual local runtime/CLI smoke checks
- status: PASS for Windows standard CPython 3.13 source-install instructions; limitations below apply

## Actual inputs and environment

Read root pyproject.toml, vendor/gxwlib/pyproject.toml, Cargo.toml, rust-toolchain.toml, tools/build_runtime.py. Exact SHA-256 values are in README-REVIEW-INSTALL-inputs.log. Tested standard CPython 3.13.2, Windows x64, Py_GIL_DISABLED=0, existing MSVC/Rust toolchain (1.93.0 installed). No system software was installed.

## Actual checks

1. Created dedicated local/readme-install-review virtual environment, without using project .venv.
2. Ran ensurepip --upgrade and pip install --upgrade pip. Both exited 0. Initial sandbox restrictions prevented fetching index packages; pip remained 24.3.1. This did not block the subsequent successful builds.
3. Initial pip install ./vendor/gxwlib was blocked while downloading maturin by sandbox network WinError10013, before Rust compilation. Repeated with approved network access.
4. pip install ./vendor/gxwlib successfully built and installed gxwlib-0.1.0-cp313-abi3-win_amd64.whl from repository source in 42.2 seconds. Wheel SHA-256: 695ed42ef824e746f095fb5116280984d41649e064eaecb720e085ca1a17402f. CARGO_TARGET_DIR reused this repository target compilation cache; no existing installed gxwlib binary was copied.
5. pip install -e ".[test]" succeeded in 26.9 seconds, installing plcweave and pytest.
6. Removed PYTHONPATH from smoke-check subprocess environment and confirmed gxwlib import resolves inside the dedicated venv.
7. Generated temporary UTF-16 runtime CSV, compiled it with profile=fx3u, and executed two real scans. Sequence LDI M0; OUT M0; LD M0; OUT Y0; END produced (scan=1,time=10ms,M0=True,Y0=True), then (scan=2,time=20ms,M0=False,Y0=False), matching explicit assertions. Temporary CSV directory removed by TemporaryDirectory cleanup.
8. python -m plcweave --help and installed Scripts/plcweave.exe --help both exited 0, exposing init/freeze/package/simulate/preflight/hil.
9. pip check exited 0: no broken requirements.

## Findings and limits

- Public first-install instructions must install vendored gxwlib first; PyPI gxwlib is not an acceptable replacement for the repository extension.
- Need standard CPython 3.13+, locked Rust 1.93.0, platform C/C++ linker/build prerequisites, and network access (or independently prepared build dependency caches).
- tools/build_runtime.py is an existing offline developer helper assuming repository .venv and Cargo caches, not a public fresh-install recipe.
- This review exercised Windows CPython 3.13.2 only; it did not install system toolchains, test Linux/macOS/Python 3.14, connect hardware, or claim a complete regression suite pass.
- Independent venv is intentionally retained for root's final README example verification; root owns its later removal. Successful subprocesses all exited; no GUI/PLC/serial resources or persistent service was created. Every launched installation/check subprocess used a 300-second timeout.

## Final document version and conclusion

Read both final documents end to end, concentrating on prerequisites, installation commands, isolated-environment use, import/CLI commands, vendor-first ordering, offline-helper limitations, source completeness and validation claims.

- README.md SHA-256: 26eb045fd74d754462f69cd30cfb6d09ee612c53d9f603563a5063aad75ca662
- README.zh-CN.md SHA-256: 719ba2f5dc7b0ae392d9fbc1d3456b565c159cfcb0964e7f61033181fbf8e9b7
- The two versions give equivalent installation commands. They match the successful dedicated-venv source installation above after substituting the deliberately isolated venv path.
- Correctly distinguish standard CPython from PyPy/free-threaded Python, state the vendor Rust toolchain pin and Windows native build requirements, install vendored runtime before editable toolkit, avoid global Python packages, and explain ensurepip/full-interpreter/script-policy alternatives.
- Missing system toolchain installation is documented through official sources and host-permission limits; this review did not execute system installation or winget commands because the toolchains already existed.
- Correctly avoid claiming Linux/macOS validation, a fresh offline installation, a validated automatic downloader, or device/electrical verification.
- Test commands in README must still be run by the coordinating agent; this R1 review itself does not claim their complete regression result.

Conclusion: PASS within this review's installation/CLI/runtime scope. No blocking installation-document defect found. Other workflow, full-example, isolation and delivery reviews remain independent.

Completed: 2026-10-22T23:41:56.743911+08:00. All subprocesses launched by this review have exited. Temporary smoke data was removed. The dedicated venv and repository Cargo target cache are intentionally retained under root ownership for follow-up validation/cleanup; no shared/user process was closed.
