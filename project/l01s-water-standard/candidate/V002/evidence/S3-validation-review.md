# Independent S3 validation — V002 / STD-002

Owner: /root/s3_verifier. Task: PW-20261022-STANDARD-REDO.
This review covers the frozen S0 revision 3 and independently frozen S1 suite;
the S2 source was received only after S1 freeze. Historical V001 programs/tests
were not read or reused. S0/S1 expectations were not edited by S3.

The final machine verdict and exact hashes are in `S3-final-review.json`.
Local CLI and PlatformIO execute the same mandatory relationship consumer.
The simulation contains 55 MUST cases, 92,996 postscan samples, 10 relationship
oracles and all frozen scalar endpoints/ranges. Nine relations apply across all
cases; the first-frequency-crossing relation applies to STD-029. The complete
CSV was read back independently, each pre-execution applied input image checked
against the frozen scripts, and all relationship oracles evaluated again.

Observed evidence includes first full frequency after 39,990ms, two complete
sleep/wake cycles in STD-034 and STD-037, and signed scan-counter wrap in both
stopped STD-049 and running STD-055. Every sample checks command/state/routing,
raw scaling, settings persistence, independent integer PI recurrence, continuous
timer qualification/reset and diagnostics. Missing data, missing full-scan
capability, skipped capture, unknown schema fields/kinds or unimplemented
contracts cannot produce SIM_PASS. The old numeric-schema scalar path remains
covered by an actual simulation regression.

The skill CSV checker reports MAIN: 0 errors / 0 warnings; COMMENT: 0 errors /
1 nonblocking advisory. Its ten unused explicit comments describe seven
implicit paired arithmetic result words and three deliberately unused ADC
channels. The checker classifies this as PASS; the warning is retained.
The real execution tool independently rejects BOGUS, unsupported PID, D8512
and M99999 fixtures; no unknown instruction/address is treated as a NOP.

Seven deliberate source faults are rejected by their intended semantic oracle:
missing stop handling, wrong enable gate, incorrect PI divisor, PI on every scan,
timer running across interruptions, wrong ADC channel and a one-scan AO spike.
Every mutant uses the *identical frozen suite* and a freshly calculated identity;
all mutant fingerprint assertions pass. Thus rejection is behavioral rather
than an incidental old-identity mismatch. Sources, reports, complete traces,
per-oracle failure evidence and the reproduction script are retained under
`S3-mutations/`, `S3-semantic-mutations.json` and `S3-verify.py`.

Repository regression tests pass; the exact count is recorded in the final
machine review and `S3-infrastructure-tests.txt`. The supplied full-upstream
baseline remains 5 failures / 92 passes / 2 skips: old unsupported-instruction
expectations changed by the execution extension, a supported-instruction count
assumption, and an unupdated words/get_word stub. S3 has not changed those
expected results or claimed the full upstream suite is green. This is a scoped
local validation, not a blanket claim of upstream compatibility.

Initial orchestration retries concerned tool environment only: default global
PlatformIO cache access was denied, so the successful run used the workspace's
existing local/pio-core; an initial checker-output console encoding error was
rerun with explicit UTF-8. These did not require source or frozen-test changes.

Verification levels remain separate: STATIC_PASS and SIM_PASS are local gates.
GX checks are NOT_EXECUTED per the user's instruction. S3 opened no serial port,
performed no download, CPU command, Modbus read/write, GUI action or hardware
test. Physical AO voltage/current, pressure dynamics, actual peripheral protocol
and power-loss retention remain UNVERIFIED. The rich-suite S6 adapter must be
qualified before hardware replay; legacy endpoint HIL execution is explicitly
blocked for this schema. A new manual download must bind the current source,
suite and independently verified identity before any authorized bench replay.

All subprocesses were bounded. No helper service, GUI or connection was created.
Only this verifier's workspace-local pytest temporary directory is removed at
completion; business evidence and deliberate-fault fixtures remain archived.
