# README workflow independent review

- task_id: PW-20261022-README-R2
- owner: readme_workflow_review
- deadline: 20 minutes from task start
- scope: English and Simplified Chinese public README workflow and AI onboarding rules
- status: PASS for documentation workflow scope; completed 2026-10-22 23:43 +08:00
- resources: read-only repository inspection; this log only; no device, GUI, serial, credential access or subprocess retained
- internal entry: Hindsight search succeeded; ZERO wake failed with PermissionError while its script tried to load credentials. ZERO live state is OFFLINE for this review; no fallback state inferred.

## Actual inspection

Read both rewritten READMEs completely, AGENTS.md, skills/plc-program-development/SKILL.md, references/markdown-cases.md, pyproject.toml, .gitignore, tools/plcweave.ps1, projects.py, markdown_suite.py, __main__.py, tools/pio-platform/builder/main.py and relevant status logic in testing.py/hil.py/validation.py. No project/customer files inspected. Actually ran `PYTHONPATH=src python -m plcweave --help`: exit 0 and the six documented commands/flags match. Did not run an install, smoke simulation, tests, PlatformIO, hardware or serial command; those validation claims are outside this review.

## Review criteria

1. requirements.md and test_cases.md remain the initial authoritative sources; first freeze precedes source.fxil; execution evidence may use machine formats.
2. Review nodes require four different fresh-context agents excluding the lead; failures/absence cannot pass.
3. Customer files use project/<name>/ or an explicitly selected external project directory, with independent projects and ignored customer content.
4. Formal delivery uses delivery/<version>/ plus a ZIP and hash manifest, explicit file selection and no overwrite.
5. PASS / PROGRAM_FAIL / TEST_INFRA_ERROR / UNVERIFIED remain separate; verification levels do not collapse into a hardware claim.
6. Public setup works from this repository with no company services or sibling repositories required.
7. Implemented CLI and limits are described accurately, including manual download and limited FX subset.

## Reviewed input SHA256

| Input | SHA256 |
| --- | --- |
| README.md | 26EB045FD74D754462F69CD30CFB6D09EE612C53D9F603563A5063AAD75CA662 |
| README.zh-CN.md | 719BA2F5DC7B0AE392D9FBC1D3456B565C159CFCB0964E7F61033181FBF8E9B7 |
| AGENTS.md | 8E173BDC7187CC79164F76E23C2EB601F621697CA21AEBC9829C06F894AA6A62 |
| skills/plc-program-development/SKILL.md | 7901084FA4996B9D1A8597BF2783B4D096C873E115BF3D7A49F691E8BFE4DF3C |
| skills/plc-program-development/references/markdown-cases.md | B67494703545703D3AA36823AB019063F2138312B7AA19EA90FA1D10EE6F0B2C |
| src/plcweave/__main__.py | 3E78AB526DC4169204C0B4B25F3A7C738AFD46708500A218413769B4A2FA5409 |
| src/plcweave/projects.py | A10133A1A9A3C47DB4415717FE4D8CB27F04506DD3F10066F74ECEA3F3E9C863 |
| src/plcweave/markdown_suite.py | 48D8FEF550AF86B5F2DD1330DD651C963EBD07C781B5B3C479797649419FAA7E |

## Findings and conclusion

No actionable workflow discrepancy found in these two README versions. PASS means this independent documentation review found the following accurately represented; it is not simulation, installation, hardware or customer-delivery acceptance.

| Criterion | Actual evidence and conclusion |
| --- | --- |
| MD authority and freeze order | Both READMEs instruct MD requirements/tests before source; markdown_suite.freeze_markdown rejects source.fxil already present, dual sources and an existing freeze. Both explain exact-byte binding, execution evidence formats, legacy compatibility and prohibition against altering expectations to fit source. PASS. |
| Four independent agents | Both specify four distinct fresh contexts, relevant raw material/hashes/criteria only, lead excluded, batching allowed, absent/failed review incomplete and findings stored in project reviews. PASS. |
| Isolation | Both place customer artifacts in independent project/ subfolders or explicitly selected external directories, exclude toolkit docs/tests/skills and preserve existing projects. This matches projects._location/create_project and .gitignore. PASS. |
| Formal delivery | Both distinguish the three-file smoke evidence package from formal MAIN.csv/COMMENT.csv/two PDFs. Both require selected project files, delivery/version folder plus ZIP, manifest hashes and no overwrite. This matches package_delivery; no automatic PDF generation is claimed. PASS. |
| Verdicts and levels | Both retain PASS/PROGRAM_FAIL/TEST_INFRA_ERROR/UNVERIFIED, distinguish command summaries such as SIM_PASS and PROTOCOL_READ_PASS, and deny equivalence to hardware/electrical acceptance. Matches inspected status logic. PASS. |
| Autonomous public onboarding | Both direct agents to local repository skill/reference, install vendor runtime first, actually inspect/run and report blockers, preserve evidence, and use no company services or sibling repository. Company hooks are explicitly scoped to configured company workspaces. PASS for instructions; installation execution not performed by this reviewer. |
| Implemented boundaries | Both list current six-command interface, limited FX subset, Windows-specific PlatformIO adapter, manual upload gate, identity/download-record needs, no automatic discovery or certified production control. PlatformIO upload code returns UNVERIFIED without serial/firmware operations. PASS. |
| Translation agreement | English and Chinese carry the same material workflow rules, smoke sample, status distinctions and hardware limitations. PASS. |

The no-hardware example is explicitly an installation smoke check and supplies no independent-review verdicts; neither README presents its smoke ZIP as a final customer delivery.

## Cleanup

No persistent process, temporary project, GUI, connection, serial handle or lock created. Only short-lived repository read commands and CLI help were run. This ignored log is the only file written by this reviewer. No cleanup action was needed and no shared/user resource was closed.
