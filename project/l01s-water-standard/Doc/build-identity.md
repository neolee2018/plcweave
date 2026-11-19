# V002 build identity

The source is UTF-8 `source.fxil`. This specification is fixed before independent S3 recomputation. `check_build_identity.py --write` refreshes its identity constants and manifest; without `--write` it verifies them. S3 must independently recompute these values without importing/calling the S2 checker as its oracle.

Canonicalization is exact:

1. Decode UTF-8 (optional initial BOM ignored). Split into text lines, accepting CRLF or LF. Require exactly one exact `#instructions` line and a later exact `#comments` line. Only text between these lines participates.
2. Require exactly one exact standalone `// BEGIN_IDENTITY` and one later exact standalone `// END_IDENTITY` line in that region. Exclude both markers and their entire intervening block. The excluded block contains only `LD M8002`, `MOV K2 D196`, `MOV K31 D197`, `MOV K<signed16> D200`, `MOV K<signed16> D201`, `MOV K2 D202`, in that order; comments/blank lines have no effect. No other logic or diagnostic writes may be excluded.
3. For each retained line, remove `//` and all following characters. Discard blank lines. Split the remaining text on whitespace, uppercase every token, then join with exactly one ASCII space. No leading/trailing spaces remain.
4. Join normalized instructions with LF (`0A`), including one LF after the final `END`. Encode UTF-8. SHA-256 of these bytes is `canonical_sha256`.
5. Take digest bytes 0..3. Decode bytes 0..1 and 2..3 independently as little-endian 16-bit unsigned integers; values above 32767 are represented as value minus 65536. These signed words initialize D200 and D201.
6. `source_sha256` separately hashes every byte of the final full source file, including identity constants, comments, metadata and exact line endings. It does not hash a normalized source.

Manifest schema: `source_sha256` (hex string), `program_version`=2, `edition`=31, `suite_version_word`=2, `fingerprint_words` (two signed16 integers), `canonical_sha256` (hex string). Test and requirements hashes are independently bound in the frozen S1 and S3 records, not hidden in the source identity exclusion.

Before hardware test writes, read D196/D197/D200/D201/D202 and require exact match to the current manifest and manually confirmed V002 download. A mismatch is TEST_INFRA_ERROR. Fingerprint and operator confirmation correlate a build; they do not prove binary readback identity. This document does not authorize downloading or opening a serial port.
