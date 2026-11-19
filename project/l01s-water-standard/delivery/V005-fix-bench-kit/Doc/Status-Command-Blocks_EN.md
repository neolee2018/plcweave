# Status & Command Blocks — V005 (D300–D335)

One FC03 read of D300–D319 + one FC16 write of D320–D335 per host refresh
(two transactions). All words are signed 16-bit. Register semantics below are
copied from the program's own comment table (`Program/source.fxil`).

## Status block D300–D319 (read-only for the host)

| Register | Meaning |
|---|---|
| D300 | Program version word; 5 |
| D301 | Edition word; 31 |
| D302 | Canonical instruction fingerprint word 0 (signed little endian) |
| D303 | Canonical instruction fingerprint word 1 (signed little endian) |
| D304 | Test suite version word; 5 |
| D305 | Heartbeat edge counter; signed word wrap |
| D306 | Scan counter; signed word wrap |
| D307 | Status bitmap; bit0 run, bit1 sleep, bit2 sleep-timing, bit3 wake-timing, bit4 test, bit5 enable |
| D308 | Pressure mirror (D100), 0.1 bar |
| D309 | Active setting mirror (D102), 0.1 bar, clamp 10–160 |
| D310 | Wake pressure in effect (D160), 0.1 bar |
| D311 | Frequency mirror (D154), 0.01 Hz; 0 or 2000–5000 |
| D312 | Analog output 0 raw mirror (D8050), 0–4000 |
| D313 | Analog output 1 mirror (D8051); always zero |
| D314 | Sleep-delay tick counter (D165), qualifying 100 ms edges |
| D315 | Wake-delay tick counter (D166), qualifying 100 ms edges |
| D316 | Reserved; always zero (physical DI stays on FC02 0x3400) |
| D317 | Diagnostic echo response (copied each executed scan from D333) |
| D318 | Selected signed raw input mirror (D110), clamped 0–4000 |
| D319 | PI integral mirror (D120), 0–30000 |

## Command block D320–D335 (host writes, FC16; program never writes them)

| Register | Meaning |
|---|---|
| D320 | Start level request; only value 1 asserted |
| D321 | Stop level request; only value 1 asserted; stop wins |
| D322 | Source mode; 1 = test input D330, 0 = hardware AI0 |
| D323 | Physical route enable; only value 1 asserted; defaults zero |
| D324 | Online pressure setting, 0.1 bar; clamped 10–160 into D102; never saved |
| D325 | Saved pressure setting; validated [10,160] on first scan only, else 60 |
| D326 | Wake pressure setting, 0.1 bar; first scan floor(saved SV × 85 / 100); external writes only afterwards |
| D327 | Sleep delay, 100 ms ticks; first scan 100; online clamp 10–600 |
| D328 | Wake delay, 100 ms ticks; first scan 30; online clamp 5–300 |
| D329 | No-flow speed, 0.01 Hz; first scan 2000; online clamp 2000–5000 |
| D330 | Test PV injection (0.1 bar raw code); used when D322=1 |
| D331 | Parallel AI0 bench input; substitutes D8030 when D332=1 and D322=0 |
| D332 | Parallel AI0 enable; 0 keeps the real AI0 path unchanged |
| D333 | Diagnostic echo request; copied to D317 each executed scan |
| D334 | Parallel terminal start request (OR with D320, same level semantics) |
| D335 | Parallel terminal stop request (OR with D321, stop wins) |

Runner defaults: reset block `RESET_WORDS = [0,1,1,0,60,60,51,100,30,2000,0,0,0,0,0,0]`
(D320..D335) and neutral block with D320=D321=0.

## Behavior summary (V005)

- **Run**: start (D320=1 or D334=1) latches M0 until stop (D321=1 or D335=1);
  invalid mode (D322∉{0,1}) stops the application, zeroes outputs and sets the
  restart inhibit M12; release requires both sources 0 in a valid mode, and a
  start held across invalid→valid recovery cannot restart.
- **Sleep**: normal running with PV ≥ SV **or** frequency ≤ no-flow speed
  continuously for clamp(D327)×100 ms → M11=1, frequency 0, integral 0,
  outputs 0. Equality qualifies.
- **Wake**: sleeping with PV **strictly below** wake pressure (D326/D160)
  continuously for clamp(D328)×100 ms → M11=0. Equality does NOT qualify; the
  dead band (PV ≥ W) keeps sleep latched.
- **Y0** = M0 AND D323=1 AND D154>0 (pure scan-level deterministic output).
- **AO0 (D8050)** = frequency × 4 / 5 counts (0–10 V scaling).
