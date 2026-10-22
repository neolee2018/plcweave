"""Conservative S6 evidence grading, separate from full-scan certification.

The frozen expectations are passed unchanged to the shared scalar comparator.
Host polling qualifies only explicitly stable quantities within declared windows.
"""
import math
from .testing import compare


def _interval(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must contain two bounds")
    if any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in value) or value[0] > value[1]:
        raise ValueError(f"Invalid {name}")
    return value


def evaluate_checkpoint(expectation, observations, *, quality, stable_devices=(), phase_sensitive_devices=()):
    """Grade the latest two complete stable polls, never an older matching pair."""
    results = []
    for device, expected in expectation.items():
        result = {"device": device, "expected": expected, "status": "UNVERIFIED", "reason": "Insufficient qualified evidence"}
        if quality.get("transport_ok") is False or quality.get("identity_ok") is False:
            result.update(status="TEST_INFRA_ERROR", reason="Transport or build identity failed")
        elif not all(quality.get(k) is True for k in ("transport_ok", "identity_ok", "applied_inputs_verified")):
            result["reason"] = "Input, identity or transport chain is not proven"
        elif device in {"D198", "D199"} or device in phase_sensitive_devices:
            result["reason"] = "Clock phase or scan count cannot be certified by polling"
        elif device not in stable_devices:
            result["reason"] = "No independent stable-state eligibility for this quantity"
        elif len(observations) < 2:
            result["reason"] = "Two complete stable observations required"
        else:
            window = quality.get("checkpoint_window_ms")
            settle = quality.get("settled_after_ms")
            pair = observations[-2:]
            valid = window is not None and settle is not None
            if valid:
                _interval(window, "checkpoint window")
                valid = all(device in row.get("values", {}) and
                            isinstance(row.get("start_ms"), (int, float)) and
                            isinstance(row.get("end_ms"), (int, float)) and
                            window[0] <= row["start_ms"] <= row["end_ms"] <= window[1] and
                            row["start_ms"] >= settle for row in pair)
                valid = valid and pair[0]["end_ms"] <= pair[1]["start_ms"]
            if not valid:
                result["reason"] = "Missing quantity or observation span outside settled checkpoint window"
            elif pair[0]["values"][device] != pair[1]["values"][device]:
                result["reason"] = "Latest two observations are not stable"
            else:
                actual = pair[-1]["values"][device]
                result.update(actual=actual, observation_spans_ms=[[row["start_ms"], row["end_ms"]] for row in pair])
                failures = compare({device: actual}, {device: expected})
                result.update(status=failures[0]["kind"] if failures else "PASS",
                              reason="Stable scalar compared within its qualified observation window")
        results.append(result)
    return results


def evaluate_timing_interval(*, trigger_ms, transition_ms, expected_ms):
    """Subtract conservative time intervals; uncertainty is not extra tolerance."""
    if transition_ms is None or trigger_ms is None:
        return {"status": "UNVERIFIED", "reason": "Transition or effective trigger was not observed", "elapsed_ms": None, "expected_ms": expected_ms}
    trigger = _interval(trigger_ms, "trigger")
    transition = _interval(transition_ms, "transition")
    limits = _interval([expected_ms["min"], expected_ms["max"]], "expected interval")
    elapsed = [transition[0]-trigger[1], transition[1]-trigger[0]]
    status = ("PASS" if limits[0] <= elapsed[0] and elapsed[1] <= limits[1] else
              "PROGRAM_FAIL" if elapsed[1] < limits[0] or elapsed[0] > limits[1] else "UNVERIFIED")
    return {"status": status, "elapsed_ms": elapsed, "expected_ms": dict(expected_ms),
            "trigger_ms": list(trigger), "transition_ms": list(transition),
            "reason": "Entire measurement interval inside tolerance" if status == "PASS" else
                      "Measurement interval disjoint from tolerance" if status == "PROGRAM_FAIL" else
                      "Measurement uncertainty overlaps tolerance boundary"}
