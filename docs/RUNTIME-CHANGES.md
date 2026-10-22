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

Rebuild the development binding on Windows after a Rust change:

```powershell
python tools/build_runtime.py
```

For a normal package build, install `vendor/gxwlib` with its original maturin
build configuration. It requires Python 3.13+ and Rust 1.93+.
