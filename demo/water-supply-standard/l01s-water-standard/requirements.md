# L01S water demonstration — S0 specification V005 / suite STD-005

Task: PW-20261108-V005-BATCH-IO. Owner: user requirements 2026-11-08 (7 items),
transcribed by AI. Date: 2026-11-08.
V004 artifacts remain historical; their results do not count for V005.
V005 redesigns the external register interface for batch Modbus access
(one FC03 status block read + one FC16 command block write per refresh) and
reworks sleep/wake behavior with settable parameters.

## Authorization and gates

Bench-only isolated PLC, no pump/VFD/load. User compiles/downloads through the
programming port; identity words verified before any test write. Sleep/wake and
no-flow timers are parameter-driven; HIL writes parameters explicitly.

## Functional requirements (all MUST unless excluded)

R01. First scan application stopped, no automatic restart. D320=1 requests start;
D321=1 requests stop. Level requests, stop wins simultaneous commands. Start
latches run until stop. Other values are not asserted. From scan stop is applied,
M0=M11=0, accumulator D120=0, frequency D154=0, Y0=0, AO0=AO1=0.
V004 parallel bench terminals D334=1 (start) and D335=1 (stop) OR into the same
commands with identical level semantics.

R02. Raw input signed16 clamped[0,4000], then D100=floor((raw+12)/25),0.1bar.
Range0..4000 means0..16.0bar. D322=1 selects test D330; D322=0 selects AI0 D8030.
With D322=0 and D332=1, the parallel bench input D331 replaces AI0 for bench
tests; D330 remains ignored in mode 0. D332=0 keeps the real AI0 path unchanged.
AI1..3 unused, cannot affect control. Invalid D322 outside{0,1} stops application
and zeros outputs and sets restart inhibit. To release inhibit the PLC must
observe D320=0 and D334=0 in a valid mode; a subsequent start from either source
can then begin. A start held at1 on either source across invalid-to-valid mode
recovery cannot restart. Inputs/request words are external writes, not
continually overwritten by program.

R03. Saved SV D325 accepted[10,160] inclusive on first scan; otherwise replace60.
Initialize active SV D102 from D325. Subsequently clamp D102[10,160] every scan.
Online D324 changes never save to D325. Online SV is D324; working SV register
D102 mirrors clamp(D324). STOP/RUN initialization in scope; real power-loss
retention out of scope.

R04 (V005 sleep delay). Normal running (not sleeping) with PV >= SV continuously
D327 ticks (100ms base) enters sleep M11=1, frequency0, integral0, outputs0.
Threshold inclusive at equality. Every qualifying scan increments the sleep
counter D314 (ticks, saturating display); first non-qualifying scan resets it.
Default and first-scan value D327=100 (10.0s); online values clamp[10,600]
(1..60s); transition at clamp(D327,10,600)*100ms with tolerance+/-100ms, never
accumulating across separate high intervals. One-scan cancellations reset.

R05 (V005 wake). Sleeping with PV < wake pressure W continuously D328 ticks
(100ms base) wakes to normal running M11=0, integral0, frequency from the next
PI tick (2000 floor). Equality at W does NOT qualify (wake requires strictly
below). Default and first-scan value D328=30 (3.0s); online values clamp[5,300]
(0.5..30s); transition at clamp(D328,5,300)*100ms with tolerance+/-100ms.
Leaving the below-W region resets the wake counter D315 (ticks). Sleep persists
in the dead band PV>=W. While sleeping, PI holds f=0 and outputs0 until wake.

R06 (V005 wake pressure). Wake pressure W is the independent settable register
D326 (0.1bar). First scan initializes D326=clamp(floor(D325*85/100),0,160)
(default saved SV60 -> 51); afterwards D326 is external-writes-only, never
overwritten by the program. Online comparison uses clamp(D326,0,160). The
computed SV*0.85 automatic threshold is abolished (old D260/D262 removed).

R07. Integer PI once per rising M8012 edge (100ms clock): e=SV-PV;
A=clamp(A+e,0,30000);P=10*e;increment=clamp(P+floor(A/10),0,3000);
D154=2000+increment. D120 is A. Before first edge after start output2000.
No PI outside normal running; sleep forces f=0 and holds until wake; waking
starts at2000 until next tick. SV60/PV0 reaches5000 in39.8..40.2sec. SV60/PV50
first update A10/output2101, then A20/output2102. Tests use tick phase/count or
justified intervals; no assumed host phase. Negative errors cannot wrap unsigned.

R08. ONLY D323==1 enables physical output. With enabled,M0=1,D154>0,Y0=1,
AO0 D8050=floor(D154*4/5),range0..4000. Otherwise Y0=0,AO0=0. AO1 D8051 always0.
Disable does not stop PI simulation. D323 defaults0; stop/sleep override enable
same scan. This is register routing, not verified analog voltage/current.

R09. First scan D322=1,D320=0,D321=0,D323=0,D333=0,D334=0,D335=0,D327=100,
D328=30,D329=2000. Next executed scan echo D333 to D317. D305 heartbeat changes
each100ms, D306 increments each scan with signed word wrap (diagnostics, not
precision clocks). Version D300=5, edition D301=31, suite D304=5. D302/D303
fingerprint words per algorithm below. Initialize identity first scan; verify
identity before any hardware writes.

R10. First scan serial M8196=1,M8125=1,D8120=HE081,D8121=1. External peripheral
images locally, real protocol checked separately. Unknown instructions/addresses
block execution, never silent NOP.

R11 (V005 no-flow speed). Normal running (not sleeping) with D154 <= no-flow
speed D329 counts on the SAME sleep delay timer as R04 (either qualifying
condition keeps the timer running; both non-qualifying reset). Sustained for the
sleep delay -> sleep. Default and first-scan D329=2000 (20.00Hz); online values
clamp[2000,3000]. With the default this overlaps the PI floor; raising D329
(e.g.2200) makes a barely-turning pump sleep despite PV slightly below SV.

R12 (V005 batch interface). All external interface registers live in two
contiguous blocks so one FC03 read and one FC16 write cover every host need.
Status block D300..D319 (PLC writes each executed scan, values settle before
the next scan):
  D300 version; D301 edition; D302/D303 fingerprint; D304 suite;
  D305 heartbeat; D306 scan counter;
  D307 status bitmap: bit0=run M0, bit1=sleep M11, bit2=sleep-delay timing,
        bit3=wake-delay timing, bit4=test mode, bit5=output enable;
  D308 PV; D309 SV; D310 wake pressure in effect; D311 frequency;
  D312 AO0 raw; D313 AO1 raw; D314 sleep counter ticks; D315 wake counter ticks;
  D316 physical DI image X0..X7 bitmap; D317 echo response; D318 selected raw;
  D319 PI integral A.
Command block D320..D335 (host writes; PLC consumes every scan):
  D320 start; D321 stop; D322 mode; D323 output enable; D324 online SV;
  D325 saved SV; D326 wake pressure; D327 sleep delay ticks; D328 wake delay
  ticks; D329 no-flow speed; D330 AI injection; D331 parallel AI; D332 parallel
  AI enable; D333 echo request; D334 parallel start terminal; D335 parallel stop
  terminal.
Status mirrors are written by the program every scan (batch refresh), never
stale beyond one scan. Both blocks lie in the user area; FC03 D300 count20 and
FC16 D320 count16 are the sanctioned host transactions; per-word access remains
legal but hosts SHOULD batch.

R13 (V005 DI image). D316 bit i mirrors physical input X_i (octal index) as of
the executed scan. Hosts read DI through this word; FC02 remains legal for
legacy tools. bits8..15 are zero.

R14 (V005 sleep/wake timing units). D327/D328 are counts of 100ms ticks
(signed16, clamped online per R04/R05); D314/D315 expose the live tick counters
(saturate at 32767). Timer equality at the parameter value transitions in the
same scan the equality is observed.

## Frozen interface

Bench writable block: D320..D335 (see R12); identity words D300..D304 read-only.
D330/D331/D332 follow R02 injection rules. D8030..D8033 remain local-only seeds;
HIL cannot pretend hardware ADC channels are writable simulated inputs.
Read-only observations: D300..D319 plus Y0 (coil 0x3300). M0/M11 are mirrored in
D307 bits; hosts SHOULD use D307. Other internals allocated/documented by S2,
S1 cannot depend on them. Words signed16; pressure0.1bar, frequency0.01Hz,
delays in 100ms ticks, AI/AO raw counts. Diagnostic wrap cannot corrupt
frequency/AO. Modbus Dn=holding offset n (zero based), M0..7679 coil offset n,
Y0=coil0x3300 per previous sample/manual; reverify read-only first.

Build fingerprint: canonical instruction text excluding dedicated
BEGIN_IDENTITY/END_IDENTITY block; SHA256 first4 bytes as two little-endian
uint16 words, stored signed in D302/D303. Avoid self-reference. S2 supplies
exact canonical algorithm/checker, S3 independently verifies. Record full
source/test hashes externally. Fingerprint/version/user download/behavior
correlate build; none proves binary readback identity.

## Validation contract

S1 covers all requirements, four analog injection modes, equalities/adjacent
values, canceled/repeated timers (including parameter-driven sleep/wake delays),
no-flow sleep, command conflicts, invalid settings/modes/enables, batch mirror
consistency, initialization and two complete sleep/wake cycles. Per-scan
invariants separate from endpoints. Scan 10ms or faster, full local traces.
Independent S3 evaluates all MUST cases and shows representative deliberately
faulty programs rejected. Hardware polling cannot prove one-scan behavior.
Missing oracle/observation is UNVERIFIED; transport/address/version failure
TEST_INFRA_ERROR; actual mismatch PROGRAM_FAIL. Only PROGRAM_FAIL drives code
changes. Three non-improving rounds, same regression twice, or UNSUPPORTED
produces diagnostic pause. No S4 candidate until static validation and all
local MUST PASS.
