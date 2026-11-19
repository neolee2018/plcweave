"""Independent capture-policy fixtures for S6; never connect to hardware.

The existing 50200 ms tolerance is fixed. A missing pair is UNVERIFIED,
including a legal early non-cap observation. These fixtures exercise the
private orchestration seam with a deterministic fake clock and read transport.
"""
import importlib.util
from pathlib import Path

import pytest


RUNNER = Path(__file__).resolve().parents[1] / "private/l01s-water-standard/run_hil02.py"


@pytest.fixture
def runner():
    if not RUNNER.exists():
        pytest.skip("Private S6 orchestration is not distributed with portable installs")
    spec = importlib.util.spec_from_file_location("s6_deadline_fixture_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(runner, *, cap_at_ms, read_ms=30, effective_delay_ms=0):
    class FakeExecutor(runner.Executor):
        def __init__(self):
            self.clock_ms = 0
            self.sequence = 0
            self.reads = {}
            self.cap_reads = []
            self.trigger_start_ms = None

        def now(self):
            return self.clock_ms

        def wait_ms(self, duration):
            self.clock_ms += max(0, duration)

        def apply(self, writes):
            start = self.now()
            self.clock_ms += 10
            if writes == {"D191": 1}:
                self.trigger_start_ms = start
            return [{"sequence": 0, "request_ms": start, "ack_ms": self.now()}]

        def read(self, watch, **kwargs):
            start = self.now()
            self.clock_ms += read_ms
            values = {}
            if set(watch) == {"M0", "M10", "M11"}:
                self.clock_ms += effective_delay_ms
                values = {"M0": 1, "M10": 0, "M11": 0}
            elif watch == ["D154"]:
                elapsed = 0 if self.trigger_start_ms is None else self.now()-self.trigger_start_ms
                values = {"D154": 5000 if elapsed >= 40000 else 2000}
            elif watch == ["D120"]:
                elapsed = self.now()-self.trigger_start_ms
                values = {"D120": 30000 if elapsed >= cap_at_ms else 29940}
            else:
                raise AssertionError(f"Unexpected fake read: {watch}")
            self.sequence += 1
            row = {"sequence": self.sequence, "start_ms": start,
                   "end_ms": self.now(), "values": values}
            self.reads[self.sequence] = row
            if watch == ["D120"]:
                self.cap_reads.append(row)
                assert len(self.cap_reads) < 100, "Deadline capture must remain bounded"
            return row

        def observe(self, expectation, hold_ms, stable_devices, **kwargs):
            return {"status": "PASS", "fixture_only": "post-deadline plateau mocked"}

    procedure = {
        "params": {
            "setup_words": {"D102": 60, "D1056": 0, "D193": 1, "D191": 0, "D192": 0},
            "trigger_write": {"D191": 1},
            "trigger_state": {"M0": 1, "M10": 0, "M11": 0},
            "poll_device": "D154", "becomes": 5000,
            "event_expected_ms": {"min": 39800, "max": 40200},
            "first_event_deadline_ms": 42000,
            "final_expected_by_ms": 50200,
            "final_observation_hold_ms": 1500,
            "minimum_stable_samples": 2,
        },
        "expect": {"M0": 1, "M10": 0, "M11": 0, "D120": 30000,
                   "D154": 5000, "Y0": 1, "D8050": 4000, "D8051": 0},
    }
    executor = FakeExecutor()
    result = executor.saturation(procedure)
    return result, executor


def assert_qualified_pair(result, executor):
    evidence = result["integral_by_deadline"]
    assert evidence["status"] == "PASS"
    pair = [executor.reads[n] for n in evidence["observation_sequences"]]
    assert len(pair) == 2
    assert all(row["values"]["D120"] == 30000 for row in pair)
    assert pair[0]["end_ms"] <= pair[1]["start_ms"]
    assert all(row["end_ms"]-executor.trigger_start_ms <= 50200 for row in pair)
    assert [row["sequence"] for row in pair] == [row["sequence"] for row in executor.cap_reads[-2:]]


def test_third_complete_read_before_deadline_can_supply_the_missing_second_cap(runner):
    # Reproduces run01's early 29940 followed by one 30000; a third read fits.
    result, executor = exercise(runner, cap_at_ms=50100)
    assert len(executor.cap_reads) >= 3
    assert_qualified_pair(result, executor)


def test_already_stable_cap_still_requires_two_complete_qualified_reads(runner):
    result, executor = exercise(runner, cap_at_ms=0)
    assert_qualified_pair(result, executor)


def test_one_cap_observation_before_deadline_does_not_qualify(runner):
    result, executor = exercise(runner, cap_at_ms=50180)
    assert result["integral_by_deadline"]["status"] == "UNVERIFIED"
    assert result["status"] != "PROGRAM_FAIL"
    qualified = [r for r in executor.cap_reads if r["end_ms"]-executor.trigger_start_ms <= 50200
                 and r["values"]["D120"] == 30000]
    assert len(qualified) <= 1


def test_cap_only_after_deadline_cannot_borrow_effective_trigger_latency(runner):
    result, executor = exercise(runner, cap_at_ms=50300, effective_delay_ms=300)
    assert result["integral_by_deadline"]["status"] == "UNVERIFIED"
    assert result["status"] != "PROGRAM_FAIL"


def test_no_cap_is_unverified_and_capture_is_bounded(runner):
    result, executor = exercise(runner, cap_at_ms=60000)
    assert result["integral_by_deadline"]["status"] == "UNVERIFIED"
    assert result["status"] != "PROGRAM_FAIL"
    assert max(row["end_ms"] for row in executor.cap_reads)-executor.trigger_start_ms <= 50200+30
