# Demo — one prompt, full PLCWeave workflow

This folder is the **first-run demo** for people who just cloned the repository. It runs a small,
**fixed** L01S scenario through the real workflow: requirements → frozen tests → program → simulation →
manual download → S6 sampling → a checked delivery ZIP. It does not collect custom process
requirements; use a separate project and the S0 interview for that.

- One-prompt entry (installs everything first, repository root): [../PROMPT.md](../PROMPT.md)
- 中文流程：[START-HERE.md](START-HERE.md)
- 复制给 Agent 的提示词：[PROMPT.md](PROMPT.md)
- 演示场景源：[scenario/](scenario/)

## What it demonstrates

| Stage | Evidence produced |
| --- | --- |
| S0/S1 | `requirements.md` (fixed demo scenario), `test_cases.md`, `s1-freeze.md` (frozen before source) |
| S2/S3 | `source.fxil`, `MAIN.csv` (GX Works2 list dialect; vendor import not executed), `COMMENT.csv`, simulation report and trace |
| S4/S5 | candidate with build identity and exported CSV |
| S6 | `confirm-flash` + `confirm-bench` gates, `preflight` + sampled HIL report; untested items stay UNVERIFIED |
| S7 | `delivery/<version>/` and ZIP with six requested deliverables + manifest |

The demo program is deliberately safe: start/stop latch, a 3-second delayed output and runtime
counters, using soft elements and an isolated `Y0`. It does **not** connect a pump, sensor or load.

## Quick start

```powershell
# 1. Fresh clone? Give the one-prompt in ../PROMPT.md to your agent — it installs and runs
#    everything. Already installed? Run the flow manually (no hardware, fully local):
./tools/plcweave.ps1 demo start demo-run --not-connected
./tools/plcweave.ps1 simulate project/demo-run
./tools/plcweave.ps1 demo status project/demo-run
./tools/plcweave.ps1 demo deliver project/demo-run --version V001
```

With a real isolated bench, follow D4/D5 in [START-HERE.md](START-HERE.md) (install `.[hil]`
serial extras first): download with GX Works2, confirm explicitly, confirm the bench/485/RUN
state, then run `preflight` and `hil --isolated-bench` before `demo deliver`.

## Honest limits

- Polling cannot certify every-scan timing, single-scan pulses, terminal voltage/current, a connected
  plant or power-loss retention. Those stay `UNVERIFIED` even when sampling checks pass.
- A failed HIL attempt is reported as “no valid case results” and never as PASS; an absent run is
  reported as “not executed”.
- The demo targets the L01S serial profile. Changing model or wiring requires a new review; do not
  copy its addresses to another PLC.
- The delivery summary computes completion as 20 (requirements/freeze) + 30 (simulation) +
  40 (HIL sampling, only with flash/bench/cleanup confirmation) + 10 (packaging), and separates
  “demo acceptance” from “formal acceptance”; the demo never certifies formal/electrical acceptance.
