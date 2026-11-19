# S2 static diagnostic — initial V002

Task PW-20261022-STANDARD-REDO; owner /root/s2_programmer. Initial source SHA256 9fb42991ee5c13a8cbb4b82b4596384ff583d266adc8379820b9f6e121b17e05; canonical SHA256 dd8d6508304f3d176929aa3bcfcedb0b3f3dfa0471e70729916218123259beeb; fingerprint [-29219,2149]. Frozen S0/S1 unchanged.

At the static compile checkpoint (2026-10-22T13:56:39.7887746+08:00), the runtime reported GXW_SIM_INCOMPLETE: Instruction program is incomplete; unsupported code and opaque regions cannot execute. Loaded runtime program `complete=False`; all three diagnostics were GXW_INSTRUCTION_UNSUPPORTED, Instruction or operand form is outside the supported syntax subset:

|Initial source line|Instruction|Runtime CSV byte offset|Span bytes|
|---|---|---|---|
|47|LDP M8012|3220|60|
|50|INC D198|3386|58|
|52|INC D199|3502|58|

The quoted runtime CSV source spans were decoded as UTF-16LE to identify each exact instruction. Temporary diagnostic/build CSVs were scoped to `evidence/s2-static-*` and `evidence/s2-diagnose-*`, removed in TemporaryDirectory cleanup. No dynamic case run was accepted, no unsupported instruction executed as NOP, and no execution core was modified. The failure is an engine syntax capability boundary, not evidence of a PLC behavioral defect.

Execution paused and root was notified. Proposed alternative uses supported basic instructions: `LD M8012 / ANI M3 / OUT M2` then unconditional `LD M8012 / OUT M3`, with first-scan `RST M3`; diagnostic increments become `ADD D198 K1 D198` and `ADD D199 K1 D199`. It preserves a global clock edge rather than a condition-gated edge. Word-wrap behavior remains for independent S3 to verify.

Root approved resuming S2 with that equivalent implementation choice under the user's existing authorization to record errors and iterate to delivery. This was a root engineering decision within the standing task scope, not a new user instruction or approval for hardware actions. No S0/S1 revision, unsupported fallback, simulator extension, port, GUI or serial access was involved. The three-round non-improvement rule remains active for subsequent real behavioral rounds. Static compile must pass before independent full-suite execution.
