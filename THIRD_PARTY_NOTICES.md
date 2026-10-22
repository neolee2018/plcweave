# Third-party notices

2026-10-22 首次执行核整合的来源、许可与修改范围如下。
厂商软件、SDK、授权文件和手册不随本项目分发。
# Runtime integration, 2026-10-22

`vendor/gxwlib/` is imported from local 102-plc-s2-engine commit
`7928b4de2b2a9d07f10e17568c62e981c5b50d55`, based on monozukuri-ai/gxwlib
`1e9a8d7542665e5015041d361e4bb86d7650714f`. Per-file pre-import hashes are in
`docs/runtime-provenance.json`. Original MIT, nested Apache-2.0, dependency notices
and third-party fixture licenses remain in that tree. The local S2 attribution is
retained in `vendor/gxwlib/HBDTECH-S2-NOTICE.md`.

PLCWeave modifications: `ir.rs`, `ladder/mod.rs`, `simulation/compile.rs`,
`simulation/scan.rs` and one stale Python test expectation. Added signed AND
comparisons, bounded SUB/MUL/DIV execution, an external D0..D8511 word image, and
corrected clock full-period semantics. See `docs/RUNTIME-CHANGES.md` for scope.
These changes do not establish vendor or hardware conformance.

Customer data and proprietary vendor manuals remain outside the public source
under ignored `project/` directories; their redistribution license has not been established.
The imported HBDTECH-S2-NOTICE.md is a historical attribution snapshot; relative
paths inside that notice refer to its original source repository.
