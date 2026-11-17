# Initial runtime integration

The pinned 102/gxwlib source is imported without changing the source project.
`runtime-provenance.json` was recorded before import and contains all 201 source
hashes and license/commit references. MIT and nested notices remain intact.

Added execution scope (FX3U profile): AND=, AND<, AND<=, AND>, AND>= on signed
16-bit constants/D words; SUB wraps to 16 bits; MUL writes low/high words; DIV
writes quotient/remainder with truncation toward zero. DIV currently permits only
a nonzero literal divisor. Both result words must fit. Unknown instruction/forms
still block compilation. Arithmetic flags and 32-bit arithmetic are not modelled.

D8000..D8511 is only an external word image. UART, ADC, DAC and model-specific
special-register behavior are not implemented by this extension. Writes to these
locations in a simulated program do not prove a peripheral was configured.

The original special-clock implementation used the labelled period as each half
period. A frozen regression case exposed the resulting half-speed periodic update. Independent
waveform tests were added, then M8011..M8014 half periods were corrected to
5ms/50ms/500ms/30s. Evidence: Mitsubishi SH-080169 appendix relay table:
https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080169/sh080169i.pdf
(the supported document URL is also recorded in the private validation report).
Initial clock phase remains a model choice, unverified against L01S hardware.

One imported upstream test still expected MOV syntax to be unknown. The same
failure was reproduced against unchanged 102's installed runtime. The test now
expects profile rejection for FX3G, which still cannot execute MOV. Frozen regression
requirements/expected outputs were not changed.

Vendor/GX and physical-device conformance remain UNVERIFIED. No native PID, pulse
execution, variable divisor, power-cycle retention or full PLC model is claimed.

Two oracle generalizations were added on 2026-10-24 (no expectation was relaxed):

- The `diagnostics` relation now reads D196/D197/D202 from the suite's
  `global_invariants` instead of hardcoding one project's version words. Projects
  without those entries keep the previous 2/31/2 fallback.
- `D1070`/`D1071` were added to the input image, and `scaling_settings` computes
  the effective AI0 source as `D1056` (mode 1), `D1070` (mode 0 with `D1071=1`)
  or `D8030` (mode 0). This models an optional parallel bench input; it does not
  make hardware ADC registers writable.

Rebuild the development binding on Windows after a Rust change:

```powershell
python tools/build_runtime.py
```

For a normal package build, install `vendor/gxwlib` with its original maturin
build configuration. It requires Python 3.13+ and Rust 1.93+.

## V004（2026-11-08，suite STD-004）：并联数字量端子进入命令状态判定

- 程序新增并联端子 D1072（启动，OR D191）/D1073（停止，OR D192），首扫描置 0，行为见 R01/R02 修订。
- `validation.py` 的 REL-09 command_state_oracle 实现由 D191/D192 单源改为包含 D1072/D1073 的
  双源口径：启动=D191==1 或 D1072==1，停止=D192==1 或 D1073==1，抑制释放要求有效模式下
  D191=0 且 D1072=0；INPUTS 补 D1072/D1073。不放松任何预期（停止优先与恢复规则保持）。
- 套件身份字预期 3→4（全局不变量、STD-001 步骤、REL-07 文本），新增 STD-056/057/058。
