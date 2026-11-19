# GUI Bench-Tool Subset Runs — 2026-11-10

Four GUI-driven runs of a fixed 10-case subset of the frozen STD-005 suite,
executed on the bench PLC (COM11, 9600/8N1, station 1) with the V005 fix
program. Purpose: exercise the in-development GUI bench tool (script
selection, multilingual labels, batch polling) against the real device; no
frozen expectation was changed and no verdict was promoted.

Per-run verdicts (identical subset, consistent across all four runs):

| Case | Title | Verdict |
|---|---|---|
| STD-001 | First scan rejects preloaded requests and defaults external controls | UNVERIFIED |
| STD-011 | Start latches, requests persist, stop dominates simultaneous commands | UNVERIFIED |
| STD-016 | Signed raw clamp and every rounding boundary class | PASS |
| STD-031 | Sleep-delay equality at SV, below adjacent value cancels, timer restarts | UNVERIFIED |
| STD-033 | Sleep persists above wake pressure; dead band equality does not wake | UNVERIFIED |
| STD-036 | Large negative error/full-scale cannot wrap PI output | UNVERIFIED |
| STD-048 | Echo accepts all signed words on the next executed scan | PASS |
| STD-056 | Parallel start terminal starts, latches, and releases cleanly | PASS |
| STD-059 | Sleep delay parameter D327 shortens the delay to 3 s | UNVERIFIED |
| STD-062 | No-flow speed D329 sleeps a barely-turning pump below SV | UNVERIFIED |

UNVERIFIED items follow the same round-3 scoping classes (phase-sensitive PI
values, ±1-tick deadline sampling, STD-031 oracle family); they are scoped
limitations of host polling, not program failures — consistent with the full
batch result of 0 PROGRAM_FAIL.

Raw reports (per run): `report.json` + `progress.json`, 78 writes each:

- `evidence/s6-v3/gui-20261110-113616-bacf86f0/`
- `evidence/s6-v3/gui-20261110-115718-475af225/`
- `evidence/s6-v3/gui-20261110-122056-1fb4af97/`
- `evidence/s6-v3/gui-20261110-124012-e6933f6f/`

These subset runs supplement (not replace) the round-3 full batch
`run-v5-full-fix2` (62/62 cases). The full-batch verdicts in
`SUMMARY-V005-fix-HIL-round3.md` remain the reference result for this kit.
