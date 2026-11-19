# L01S water demonstration — S0 specification V002 / suite STD-002

Task: PW-20261022-STANDARD-REDO. Owner: codex. Date: 2026-10-22.
Fresh process run after V001 was returned for lack of independent S1/S3.
V001 artifacts remain historical; their results do not count for V002.
Domain source: private/l01s-water/requirements.md and user request for standard rerun.
Portable PI means PID with derivative zero, not Delta private PID emulation.

## Authorization and gates

- HBDTECH L01S-16M-4AD2DA, 4 AI / 2 AO; empty isolated PLC without sensors,
  pumps, drives or other actuators (user confirmation in this chat).
- COM5 application programming; COM7 RS485 station1,9600/8/N/1.
- User prohibits GX Works2. GX_CHECK remains NOT_EXECUTED, never PASS.
- PlatformIO task orchestration required. No validated L01S uploader exists here;
  user permitted manual download. A new candidate requires new download confirmation;
  the earlier V001 confirmation cannot bind V002.
- Register simulation and CPU RUN/STOP on this isolated PLC are authorized.
- S1 fresh agent receives this specification/schema only, no old/new implementation
  or old tests. Freeze S1 before S2 starts. Independent S3 runs frozen cases/traces.
- Logic/bench acceptance only: electrical output, pressure control and power-loss
  retention remain UNVERIFIED without connected equipment.

## Functional requirements (all MUST unless excluded)

R01. First scan application stopped, no automatic restart. D191=1 requests start;
D192=1 requests stop. Both level requests, stop wins simultaneous commands. Start
latches run until stop. Other values are not asserted. From scan stop is applied,
M0=M10=M11=0, accumulator D120=0, frequency D154=0,Y0=0,AO0=AO1=0.

R02. Raw input signed16 clamped[0,4000], then D100=floor((raw+12)/25),0.1bar.
Range0..4000 means0..16.0bar. D190=1 selects test D1056; D190=0 selects AI0 D8030.
AI1..3 unused, cannot affect control. Invalid D190 outside{0,1} stops application
and zeros outputs and sets restart inhibit. To release inhibit the PLC must
observe D191=0 in a valid mode; a subsequent D191=1 can then start. A start held
at1 across invalid-to-valid mode recovery cannot restart. Inputs/request words
are external writes, not continually overwritten by program.

R03. Saved SV D261 accepted[10,160] inclusive on first scan; otherwise replace60.
Initialize active SV D102 from D261. Subsequently clamp D102[10,160] every scan.
Online D102 changes never save to D261. Recompute D260=SV-2 and
D262=floor(SV*85/100) every scan; default60,58,51 in0.1bar.
STOP/RUN initialization in scope; real power-loss retention out of scope.

R04. Running/not sleeping with PV>=D260 enters pre-sleep M10=1,frequency2000
(20.00Hz),integral0. After5sec continuous condition sleep M11=1,M10=0,frequency0.
Leaving threshold before expiry cancels delay. Timing tolerance+/-100ms, never
accumulate across separate high intervals. Sleep latched until wake or stop.

R05. Sleeping with PV<=D262 continuously3sec wakes normal running M11=0.
Leaving wake region resets timer. Equality counts for both thresholds. Timing
tolerance+/-100ms. Sleep persists in dead band; timer resets for next cycle.
At SV10 both thresholds equal8: after a wake event at PV8, immediate reentry to
pre-sleep is permitted; no minimum normal-state dwell is required at this overlap.

R06. Every scan frequency normal run2000..5000,pre-sleep2000,stop/sleep0
(0.01Hz). M0 stays1 in sleep; M10/M11 mutually exclusive. Stop/pre-sleep/sleep
clear D120. Full-scale goes through pre-sleep to sleep; zero reaches5000 without
spurious sleep. Alternating0/full-scale every100ms for>=5sec cannot deadlock,
exceed bounds or accumulate sleep time; after recovery to PV50 run>=2sec.

R07. Integer PI once per rising M8012 edge (100ms clock): e=SV-PV;
A=clamp(A+e,0,30000);P=10*e;increment=clamp(P+floor(A/10),0,3000);
D154=2000+increment. D120 is A. Before first edge after start output2000.
No PI outside normal running. Leaving pre-sleep/waking starts at2000 until next
tick. SV60/PV0 reaches5000 in39.8..40.2sec. SV60/PV50 first update A10/output2101,
then A20/output2102. Tests use tick phase/count or justified intervals; no assumed
host phase. Negative errors cannot wrap unsigned.

R08. ONLY D193==1 enables physical output. With enabled,M0=1,D154>0,Y0=1,
AO0 D8050=floor(D154*4/5),range0..4000. Otherwise Y0=0,AO0=0. AO1 D8051 always0.
Disable does not stop PI simulation. D193 defaults0; stop/sleep override enable
same scan. This is register routing, not verified analog voltage/current.

R09. First scan D190=1,D191=0,D192=0,D193=0,D194=0,D195=0. Next executed scan
echo D194 to D195. D198 heartbeat changes each100ms,D199 increments each scan
with signed word wrap (diagnostics,not precision clocks). Version D196=2,
edition D197=31,suite D202=2. D200/D201 fingerprint words per algorithm below.
Initialize identity first scan; verify identity before any hardware writes.

R10. First scan serial M8196=1,M8125=1,D8120=HE081,D8121=1. External peripheral
images locally, real protocol checked separately. Unknown instructions/addresses
block execution, never silent NOP.

## Frozen interface

Bench writable: D102,D190,D191,D192,D193,D194,D261,D1056.
Local can also seed AI0..3 D8030..D8033; HIL cannot pretend hardware ADC channels
are writable simulated inputs. Label such cases local-only.
Read-only observations: D100,D120,D154,D195..D202,D260,D262,D8050,D8051,M0,M10,M11,Y0.
Other internals allocated/documented by S2, S1 cannot depend on them.
Words signed16;pressure0.1bar,frequency0.01Hz,AI/AO raw counts. Diagnostic wrap
cannot corrupt frequency/AO. Modbus Dn=holding offset n (zero based), M0..7679
coil offset n,Y0=coil0x3300 per previous sample/manual; reverify read-only first.

Build fingerprint: canonical instruction text excluding dedicated
BEGIN_IDENTITY/END_IDENTITY block; SHA256 first4 bytes as two little-endian
uint16 words, stored signed in D200/D201. Avoid self-reference. S2 supplies exact
canonical algorithm/checker, S3 independently verifies. Record full source/test
hashes externally. Fingerprint/version/user download/behavior correlate build;
none proves binary readback identity.

## Validation contract

S1 covers all requirements,four analog injection modes,equalities/adjacent values,
canceled/repeated timers,command conflicts,invalid settings/modes/enables,
initialization and two complete sleep/wake cycles. Per-scan invariants separate
from endpoints. Scan10ms or faster,full local traces. Independent S3 evaluates
all MUST cases and shows representative deliberately faulty programs rejected.
Hardware polling cannot prove one-scan behavior. Missing oracle/observation is
UNVERIFIED;transport/address/version failure TEST_INFRA_ERROR;actual mismatch
PROGRAM_FAIL. Only PROGRAM_FAIL drives code changes. Three non-improving rounds,
same regression twice,or UNSUPPORTED produces diagnostic pause. No S4 candidate
until static validation and all local MUST PASS.
