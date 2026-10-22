"""Independent, streaming S3 oracles for the frozen water-control contract.

No PLC source is interpreted here. Applied external images are kept separate
from observed program results. Sampled backends must state their capabilities;
polling cannot certify a full scan trace.
"""
import hashlib
from pathlib import Path

SCHEMA = "plcweave-case-v1-with-independent-oracles"
INPUTS = ("D102", "D190", "D191", "D192", "D193", "D194", "D261", "D1056",
          "D8030", "D8031", "D8032", "D8033")
KINDS = {
    "state_output_consistency", "physical_routing", "scaling_settings",
    "independent_pi_recurrence", "continuous_timers", "first_crossing_and_monotonicity",
    "diagnostics", "independent_fingerprint", "command_state_oracle", "serial_and_engine_gate",
}
PARAMS = {
    "independent_pi_recurrence": {"clock": "M8012", "integral_min": 0, "integral_max": 30000,
        "proportional_factor": 10, "integral_divisor": 10, "increment_min": 0,
        "increment_max": 3000, "frequency_base": 2000, "skip_transition_scan": True},
    "continuous_timers": {"sleep_delay_ms": {"min": 4900, "max": 5100},
        "wake_delay_ms": {"min": 2900, "max": 3100}, "timestamp_uncertainty_ms": 10},
    "first_crossing_and_monotonicity": {"first_full_frequency_ms": {"min": 39800, "max": 40200},
        "integral_saturated_by_ms": 50200},
    "diagnostics": {"heartbeat_interval_ms": 100, "timestamp_uncertainty_ms": 10,
        "counter_width_bits": 16, "counter_delta_per_scan": 1},
    "independent_fingerprint": {"fingerprint_words": ["D200", "D201"], "hash": "sha256",
        "bytes": 4, "byteorder": "little", "signed_word_width": 16,
        "excluded_block": ["BEGIN_IDENTITY", "END_IDENTITY"]},
}
REQUIRED = {
    "state_output_consistency": "M0 M10 M11 D120 D154 Y0 D8050 D8051",
    "physical_routing": "M0 D154 Y0 D8050 D8051",
    "scaling_settings": "D100 D102 D260 D261 D262 " + " ".join(INPUTS[1:]),
    "independent_pi_recurrence": "M0 M10 M11 M8012 D100 D102 D120 D154",
    "continuous_timers": "M0 M10 M11 D100 D260 D262",
    "first_crossing_and_monotonicity": "M0 M10 M11 D100 D120 D154",
    "diagnostics": "D195 D196 D197 D198 D199 D200 D201 D202",
    "independent_fingerprint": "D200 D201",
    "command_state_oracle": "M0",
    "serial_and_engine_gate": "M8196 M8125 D8120 D8121",
}

def signed16(value):
    return (int(value) + 32768) % 65536 - 32768

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def _keys(value, allowed, label):
    unknown = set(value) - set(allowed.split())
    if unknown:
        raise ValueError(f"Unsupported {label} fields: {sorted(unknown)}")

def validate_suite(suite):
    """Reject unevaluated contract extensions instead of silently ignoring them."""
    if suite.get("schema_version") in (None, 1):
        if suite.get("relationship_invariants") or suite.get("oracle_contract"):
            raise ValueError("Relationship contracts require an explicit supported schema")
        return
    if suite["schema_version"] != SCHEMA:
        raise ValueError(f"Unsupported suite schema: {suite['schema_version']}")
    _keys(suite, "suite_version schema_version requirements_sha256 scan_ms watch global_invariants relationship_invariants oracle_contract cases", "suite")
    _keys(suite["oracle_contract"], "all_relationship_invariants trace hardware scope timing_phase", "oracle contract")
    if not suite["cases"] or not suite["relationship_invariants"]:
        raise ValueError("An independent suite requires cases and relationship invariants")
    ids = [case["id"] for case in suite["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ID")
    seen = set()
    for rule in suite["relationship_invariants"]:
        _keys(rule, "id requirements scope case_ids kind definition params", "relationship")
        kind = rule["kind"]
        if kind not in KINDS:
            raise ValueError(f"Unsupported relationship kind: {kind}")
        if kind in seen:
            raise ValueError(f"Duplicate relationship kind: {kind}")
        seen.add(kind)
        if rule.get("params", {}) != PARAMS.get(kind, {}):
            raise ValueError(f"Unsupported parameters for {kind}: {rule.get('params')}")
        if rule.get("scope") not in {None, "every_scan", "every_scan_and_transition", "build_and_initialization", "first_scan_and_static_validation"}:
            raise ValueError(f"Unsupported relationship scope: {rule.get('scope')}")
        if "case_ids" in rule and not rule["case_ids"]:
            raise ValueError("Relationship case selector cannot be empty")
        if not set(rule.get("case_ids", [])) <= set(ids):
            raise ValueError("Relationship references absent case")
    if seen != KINDS:
        raise ValueError(f"Missing mandatory relationship kinds: {sorted(KINDS-seen)}")
    for case in suite["cases"]:
        _keys(case, "id title priority requirements injection_mode hardware_scope initial_words steps expected_behavior_note", "case")
        if case["priority"] not in {"MUST", "SHOULD"}:
            raise ValueError("Unsupported case priority")
        if not case["steps"]:
            raise ValueError("A case must execute at least one step")
        for step in case["steps"]:
            _keys(step, "write duration_ms invariant expect note", "step")
            if not isinstance(step["duration_ms"], int) or step["duration_ms"] <= 0 or step["duration_ms"] % suite["scan_ms"]:
                raise ValueError("Duration must be a positive multiple of scan_ms")

def independent_fingerprint(path):
    """Canonicalize instructions independently of the S2 build/checker code."""
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if lines.count("#instructions") != 1 or lines.count("#comments") != 1 or lines.index("#comments") < lines.index("#instructions"):
        raise ValueError("Canonical source requires one ordered instructions/comments region")
    section, excluded = None, False
    begins = ends = 0
    canonical = []
    for raw in lines:
        stripped = raw.strip()
        if stripped in ("#meta", "#instructions", "#comments"):
            section = stripped
            continue
        if section != "#instructions":
            continue
        if stripped == "// BEGIN_IDENTITY":
            begins += 1
            if excluded or ends:
                raise ValueError("Invalid identity marker order")
            excluded = True
            continue
        if stripped == "// END_IDENTITY":
            ends += 1
            if not excluded:
                raise ValueError("Invalid identity marker order")
            excluded = False
            continue
        if excluded:
            code = raw.split("//", 1)[0].strip().upper().split()
            if code and not (code == ["LD", "M8002"] or
                    len(code) == 3 and code[0] == "MOV" and code[1].startswith(("K", "H")) and
                    code[2] in {"D196", "D197", "D200", "D201", "D202"}):
                raise ValueError("Identity block contains nonidentity instructions")
            continue
        code = raw.split("//", 1)[0].strip()
        if code:
            canonical.append(" ".join(code.upper().split()))
    if (begins, ends, excluded) != (1, 1, False):
        raise ValueError("Exactly one ordered identity block is required")
    payload = ("\n".join(canonical) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return {"canonical_sha256": digest.hex(), "canonical_instruction_count": len(canonical),
            "fingerprint_words": [signed16(int.from_bytes(digest[i:i+2], "little")) for i in (0, 2)]}

class InputImage:
    """Expected external memory image, never populated from program results."""
    def __init__(self, initial=None):
        self.values = dict.fromkeys(INPUTS, 0)
        self.values.update({key: signed16(value) for key, value in (initial or {}).items() if key in INPUTS})
        self.first = True

    def apply(self, writes):
        self.values.update({key: signed16(value) for key, value in writes.items() if key in INPUTS})

    def next_scan(self):
        if self.first:
            self.values.update(D190=1, D191=0, D192=0, D193=0, D194=0)
            saved = self.values["D261"]
            self.values["D261"] = saved if 10 <= saved <= 160 else 60
            self.values["D102"] = self.values["D261"]
            self.first = False
        self.values["D102"] = clamp(self.values["D102"], 10, 160)
        return self.values.copy()

class TraceOracle:
    """Feed complete postscan observations, then finish to obtain all verdicts.

    A hardware poller can use this exact interface; without proven full trace
    and applied inputs, mandatory relations remain UNVERIFIED.
    """
    def __init__(self, suite, case, *, capabilities=None, context=None):
        self.scan_ms = suite["scan_ms"]
        self.case = case
        self.context = context or {}
        self.capabilities = capabilities or {}
        self.rules = [rule for rule in suite.get("relationship_invariants", [])
                      if "case_ids" not in rule or case["id"] in rule["case_ids"]]
        self.results = {rule["kind"]: {"id": rule["id"], "kind": rule["kind"], "status": "PASS", "evaluated_scans": 0,
                       "violation_count": 0, "failures": []} for rule in self.rules}
        self.previous = None
        self.previous_time = None
        self.run = False
        self.inhibit = False
        self.a = self.frequency = 0
        self.normal = False
        self.clock = False
        self.high_start = self.low_start = None
        self.sleep = False
        self.start_normal = self.first_full = None
        self.heartbeat_changed = None
        self.heartbeat_intervals = 0
        self.sleep_events = self.wake_events = self.pi_ticks = self.counter_wraps = 0
        self.consumed_scans = 0

    def _fail(self, kind, time_ms, expected, actual, status="PROGRAM_FAIL"):
        result = self.results[kind]
        result["violation_count"] += 1
        if result["status"] != "PROGRAM_FAIL":
            result["status"] = status
        if len(result["failures"]) < 6:
            result["failures"].append({"time_ms": time_ms, "expected": expected, "actual": actual, "kind": status})

    def _expect(self, kind, t, observed, expected):
        wrong = {key: {"expected": value, "actual": observed.get(key)} for key, value in expected.items() if observed.get(key) != value}
        if wrong:
            self._fail(kind, t, expected, wrong)

    def consume(self, observation, applied_input, time_ms):
        self.consumed_scans += 1
        if self.previous_time is None and time_ms != self.scan_ms:
            self.capabilities = {**self.capabilities, "full_scan_trace": False}
        if self.previous_time is not None and time_ms - self.previous_time != self.scan_ms:
            self.capabilities = {**self.capabilities, "full_scan_trace": False}
        ready = set()
        for rule in self.rules:
            kind = rule["kind"]
            if not self.capabilities.get("full_scan_trace") or not self.capabilities.get("verified_applied_inputs"):
                self._fail(kind, time_ms, "full scan trace and verified applied inputs", self.capabilities, "UNVERIFIED")
                continue
            missing = [name for name in REQUIRED[kind].split() if observation.get(name) is None]
            if missing or any(applied_input.get(name) is None for name in INPUTS):
                self._fail(kind, time_ms, "all required observations and applied inputs", missing, "UNVERIFIED")
                continue
            ready.add(kind)
            self.results[kind]["evaluated_scans"] += 1
        o, i, t = observation, applied_input, time_ms
        if any(i.get(name) is None for name in INPUTS):
            self.previous, self.previous_time = dict(o), t
            return
        first = self.previous is None
        # Independent command state depends only on separately recorded inputs.
        if first:
            self.run = False
        elif i["D190"] not in (0, 1):
            self.run, self.inhibit = False, True
        else:
            if self.inhibit and i["D191"] == 0:
                self.inhibit = False
            if i["D192"] == 1:
                self.run = False
            elif i["D191"] == 1 and not self.inhibit:
                self.run = True
        valid = i["D190"] in (0, 1)
        pv = (clamp(signed16(i["D1056"] if i["D190"] == 1 else i["D8030"]), 0, 4000) + 12) // 25
        sv = i["D102"]
        if "command_state_oracle" in ready:
            self._expect("command_state_oracle", t, o, {"M0": int(self.run)})
        if "scaling_settings" in ready:
            expected = {**i, "D260": sv-2, "D262": sv*85//100}
            if valid:
                expected["D100"] = pv
            self._expect("scaling_settings", t, o, expected)
        if "state_output_consistency" in ready:
            k = "state_output_consistency"
            if not o["M0"] or not valid:
                self._expect(k, t, o, dict.fromkeys("M0 M10 M11 D120 D154 Y0 D8050 D8051".split(), 0))
            elif o["M11"]:
                self._expect(k, t, o, {"M0": 1, "M10": 0, "D120": 0, "D154": 0, "Y0": 0, "D8050": 0})
            elif o["M10"]:
                self._expect(k, t, o, {"M0": 1, "M11": 0, "D120": 0, "D154": 2000})
            elif not 2000 <= o["D154"] <= 5000:
                self._fail(k, t, "normal frequency 2000..5000", o["D154"])
        if "physical_routing" in ready:
            enabled = i["D193"] == 1 and o["M0"] == 1 and o["D154"] > 0
            self._expect("physical_routing", t, o, {"Y0": int(enabled), "D8050": o["D154"]*4//5 if enabled else 0, "D8051": 0})
        # Timer state is adopted only at a legal observed transition. Every
        # transition and every missed upper deadline is checked independently.
        if "continuous_timers" in ready:
            k = "continuous_timers"
            current_sleep = bool(o["M11"])
            if not self.run or not valid:
                self.high_start = self.low_start = None
                self._expect(k, t, o, {"M10": 0, "M11": 0})
            elif not self.sleep:
                self.low_start = None
                if pv >= sv-2:
                    if self.high_start is None:
                        self.high_start = t
                    elapsed = t-self.high_start
                    if current_sleep:
                        if not 4900 <= elapsed <= 5100 or not self.previous or not self.previous.get("M10"):
                            self._fail(k, t, "sleep after continuous 4900..5100ms and prior pre-sleep", elapsed)
                        self.sleep_events += 1
                        self.high_start = None
                    else:
                        self._expect(k, t, o, {"M10": 1})
                        if elapsed > 5100:
                            self._fail(k, t, "sleep by 5100ms", elapsed)
                else:
                    self.high_start = None
                    self._expect(k, t, o, {"M10": 0, "M11": 0})
            else:
                self.high_start = None
                if pv <= sv*85//100:
                    if self.low_start is None:
                        self.low_start = t
                    elapsed = t-self.low_start
                    if not current_sleep:
                        if not 2900 <= elapsed <= 3100:
                            self._fail(k, t, "wake after continuous 2900..3100ms", elapsed)
                        self.wake_events += 1
                        self.low_start = None
                        if pv >= sv-2:
                            self.high_start = t  # SV10 overlap permits immediate pre-sleep.
                        else:
                            self._expect(k, t, o, {"M10": 0})
                    elif elapsed > 3100:
                        self._fail(k, t, "wake by 3100ms", elapsed)
                else:
                    self.low_start = None
                    self._expect(k, t, o, {"M11": 1, "M10": 0})
            self.sleep = current_sleep if self.run and valid else False
        if "independent_pi_recurrence" in ready:
            k = "independent_pi_recurrence"
            normal = bool(o["M0"] and not o["M10"] and not o["M11"])
            rising = bool(o["M8012"] and not self.clock)
            if not normal:
                self.a = 0
                self.frequency = 2000 if o["M10"] else 0
            elif not self.normal:
                self.a, self.frequency = 0, 2000
            elif rising:
                error = sv-pv
                self.a = clamp(self.a+error, 0, 30000)
                self.frequency = 2000+clamp(10*error+self.a//10, 0, 3000)
                self.pi_ticks += 1
            self._expect(k, t, o, {"D120": self.a, "D154": self.frequency})
            self.normal, self.clock = normal, bool(o["M8012"])
        if "first_crossing_and_monotonicity" in ready:
            k = "first_crossing_and_monotonicity"
            if self.run and valid and pv == 0:
                self._expect(k, t, o, {"M10": 0, "M11": 0})
                if self.start_normal is None:
                    self.start_normal = t
                elapsed = t-self.start_normal
                if self.previous and self.previous.get("M0") and (o["D120"] < self.previous["D120"] or o["D154"] < self.previous["D154"]):
                    self._fail(k, t, "monotonic integral and frequency", {"A": o["D120"], "f": o["D154"]})
                if self.first_full is None and o["D154"] == 5000:
                    self.first_full = elapsed
                    if not 39800 <= elapsed <= 40200:
                        self._fail(k, t, "first 5000 in 39800..40200ms", elapsed)
                if elapsed > 40200 and self.first_full is None:
                    self._fail(k, t, "5000 by 40200ms", elapsed)
                if elapsed >= 50200:
                    self._expect(k, t, o, {"D120": 30000, "D154": 5000})
        if "diagnostics" in ready:
            k = "diagnostics"
            self._expect(k, t, o, {"D195": i["D194"], "D196": 2, "D197": 31, "D202": 2})
            if self.previous and all(self.previous.get(d) is not None for d in ("D199", "D198", "D200", "D201")):
                self._expect(k, t, o, {"D199": signed16(self.previous["D199"]+1), "D200": self.previous["D200"], "D201": self.previous["D201"]})
                if self.previous["D199"] == 32767 and o["D199"] == -32768:
                    self.counter_wraps += 1
                if o["D198"] != self.previous["D198"]:
                    if self.heartbeat_changed is not None:
                        interval = t-self.heartbeat_changed
                        if not 90 <= interval <= 110:
                            self._fail(k, t, "heartbeat interval 90..110ms", interval)
                        self.heartbeat_intervals += 1
                    self.heartbeat_changed = t
                elif t-(self.heartbeat_changed or self.scan_ms) > 110:
                    self._fail(k, t, "heartbeat change within 110ms", t-(self.heartbeat_changed or self.scan_ms))
        if "independent_fingerprint" in ready:
            words = self.context.get("fingerprint_words")
            if words is None:
                self._fail("independent_fingerprint", t, "independently calculated build fingerprint", None, "UNVERIFIED")
            else:
                self._expect("independent_fingerprint", t, o, dict(zip(("D200", "D201"), words)))
        if "serial_and_engine_gate" in ready:
            if first:
                self._expect("serial_and_engine_gate", t, o, {"M8196": 1, "M8125": 1, "D8120": -8063, "D8121": 1})
            if not self.context.get("engine_gate_pass"):
                self._fail("serial_and_engine_gate", t, "unsupported opcode/address execution gate proved", None, "UNVERIFIED")
        self.previous, self.previous_time = dict(o), t

    def finish(self):
        expected_scans = sum(step["duration_ms"]//self.scan_ms for step in self.case.get("steps", []))
        if "steps" in self.case and self.consumed_scans != expected_scans:
            for kind in self.results:
                self._fail(kind, self.previous_time, f"exactly {expected_scans} scans", self.consumed_scans, "UNVERIFIED")
        for result in self.results.values():
            if not result["evaluated_scans"] and result["status"] == "PASS":
                self._fail(result["kind"], None, "at least one observed scan", None, "UNVERIFIED")
        if "first_crossing_and_monotonicity" in self.results and self.first_full is None:
            self._fail("first_crossing_and_monotonicity", self.previous_time, "observed first full frequency crossing", None, "UNVERIFIED")
        return list(self.results.values())

    def metrics(self):
        return {"pi_updates": self.pi_ticks, "sleep_events": self.sleep_events, "wake_events": self.wake_events,
                "heartbeat_intervals": self.heartbeat_intervals, "counter_wraps": self.counter_wraps,
                "first_full_frequency_elapsed_ms": self.first_full}
