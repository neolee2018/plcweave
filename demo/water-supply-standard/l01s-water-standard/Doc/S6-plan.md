# V002 S6 preparation and outstanding gates

This is a plan, not a hardware test result. No V002 serial access has occurred.

1. New manual download confirmation must match current source/test SHA256.
2. Read-only COM7 preflight verifies D196=2,D197=31,D200=28642,D201=27104,D202=2 and heartbeat.
3. Source manifest mismatch or old PLC image blocks writes.
4. Exact-10ms and clock-phase tests require suitable capture/stimulus capability. Legacy host endpoint replay is blocked for this rich suite. A qualified sampled adapter must call the same TraceOracle and expose missing full-scan/verified-input capability as UNVERIFIED. It is not yet a validated V002 HIL backend.
5. Initialization tests need separately recorded COM5 STOP/RUN. STOP disables COM7 on the prior sample; do not attempt recovery through COM7.
6. All hardware connections use bounded operations/try-finally; application ends stopped, output disabled and zero readback.
7. ADC injection cases are local_only, not hardware ADC writes. Real voltage/current/plant and power loss remain unverified.

| Case | Scope | Initial words |
|---|---|---|
| STD-001 | bench | {"D190": 0, "D191": 1, "D192": 1, "D193": 1, "D194": 123, "D261": 0} |
| STD-002 | bench | {"D261": -32768} |
| STD-003 | bench | {"D261": -1} |
| STD-004 | bench | {"D261": 9} |
| STD-005 | bench | {"D261": 10} |
| STD-006 | bench | {"D261": 11} |
| STD-007 | bench | {"D261": 159} |
| STD-008 | bench | {"D261": 160} |
| STD-009 | bench | {"D261": 161} |
| STD-010 | bench | {"D261": 32767} |
| STD-011 | bench | {} |
| STD-012 | bench | {} |
| STD-013 | bench | {} |
| STD-014 | bench | {} |
| STD-015 | bench | {} |
| STD-016 | bench | {} |
| STD-017 | local_only | {} |
| STD-018 | local_only | {} |
| STD-019 | bench | {} |
| STD-020 | bench | {} |
| STD-021 | bench | {} |
| STD-022 | bench | {} |
| STD-023 | local_only | {} |
| STD-024 | bench | {} |
| STD-025 | bench | {} |
| STD-026 | bench | {} |
| STD-027 | bench | {} |
| STD-028 | bench | {} |
| STD-029 | bench | {} |
| STD-030 | bench | {} |
| STD-031 | bench | {} |
| STD-032 | bench | {} |
| STD-033 | bench | {} |
| STD-034 | bench | {} |
| STD-035 | bench | {} |
| STD-036 | bench | {} |
| STD-037 | bench | {} |
| STD-038 | bench | {} |
| STD-039 | bench | {} |
| STD-040 | bench | {} |
| STD-041 | bench | {} |
| STD-042 | bench | {} |
| STD-043 | bench | {} |
| STD-044 | bench | {} |
| STD-045 | bench | {} |
| STD-046 | bench | {} |
| STD-047 | bench | {} |
| STD-048 | bench | {} |
| STD-049 | bench | {} |
| STD-050 | bench | {} |
| STD-051 | bench | {} |
| STD-052 | bench | {} |
| STD-053 | bench | {} |
| STD-054 | bench | {} |
| STD-055 | bench | {} |
