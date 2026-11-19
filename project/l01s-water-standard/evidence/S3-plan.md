# Independent S3 plan

Task PW-20261022-STANDARD-REDO; owner /root/s3_verifier.
Scope: local instruction simulation, frozen S1 contracts, independent trace
comparison, static format and execution gates, fingerprint, deliberate faults.
No serial connection, GX session, program download or hardware operation.

Inputs read before S2: frozen S0 revision 2, PLC-TDD skill/SOP/schema, current
runner/exporter, runtime API and repository tests. Historical private/l01s-water
programs and tests are excluded. S1 draft was reviewed solely for executability;
the comparator implementation starts after S1's final freeze announcement.

Each relationship produces its own assertion result and observation count.
Checks use every postscan image and a separate applied-input shadow. Unknown
contract fields/types fail closed. Missing observations or insufficient capture
capabilities produce UNVERIFIED, never a passing default. Simulated full traces
and hardware polling share a consumer but have distinct evidence capabilities.

Validation will include interior one-scan defects with correct final endpoints,
PI cadence/arithmetic faults, timer cancellation faults, mode/command faults,
AO gate/source faults and unsupported opcode/address fixtures. Full source,
test, engine and comparator hashes bind evidence; S0/S1 inputs remain read-only.

Baseline limit supplied by root: 22 repository tests pass; the complete upstream
suite has 5 failures / 92 passes / 2 skips due to extension-incompatible legacy
assumptions/stubs. These failures remain reported separately and will not be
hidden by changing their expected results.

Resource owner: this verifier's synchronous subprocesses and workspace-local
pytest temporary directory. Commands are bounded; no persistent helper or
shared service is created. Final cleanup and results are recorded separately.
