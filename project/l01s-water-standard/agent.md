# L01S V002 task rules

This is an isolated private case inside PLCWeave, not a new workspace project.
Read requirements.md, workflow.md, s0-freeze.json and applicable S1 freeze first.
Unique source: source.fxil. Never modify generated CSVs or frozen S1 expectations.
Tests independently designed before programming; S3 uses independent full-trace
checks. Any specification change records reason, owner, impact and suite revision.
Unsupported instructions halt the gate. Three non-improving iterations need a
diagnostic report. No reinterpretation of infrastructure errors as PLC defects.

Version V002 follows V001's process rejection. Do not reuse its pass results.
Use local private Git snapshots for stage audit, no remote/push. Track artifacts
and hashes; never put manuals, customer files or credentials in public root Git.

User overrides: no GX Works2; PlatformIO task orchestration; no validated automatic
application uploader, therefore manual download gate. Old download confirmation
does not authorize declaring this new image loaded. Empty isolated bench permits
controlled simulated inputs/RUN/STOP. No physical loads/plant attached.

Folders: Doc for document sources, lab-tests for candidate MAIN/COMMENT,
versions/V002 for frozen source/CSV/annotated source. A candidate is not final
release. GX/electrical/plant/power-loss gates remain honestly unverified.
Connection ownership uses try/finally, bounded subprocesses and exact-task cleanup.
