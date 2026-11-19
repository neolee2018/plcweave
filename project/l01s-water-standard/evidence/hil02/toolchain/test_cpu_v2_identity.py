"""CPU control binds all V002 build identity words over programming port.

STOP disables Modbus. These fixtures prohibit reliance on that transport and
record whether a CPU control frame was sent before identity verification.
"""
from types import SimpleNamespace

import pytest

from plcweave.cpu_control import CPUControl


def install_fx(monkeypatch, *, identity=(2, 31), fingerprint=(28642, 27104), suite=2):
    import plcweave.cpu_control as module

    frames, reads = [], []

    class Serial:
        def reset_input_buffer(self):
            pass

        def write(self, frame):
            frames.append(frame)

        def read(self, count):
            return b"\x06"

    class FX:
        def __enter__(self):
            self.serial = Serial()
            return self

        def __exit__(self, *args):
            pass

        def read_words(self, start, count):
            reads.append((start, count))
            words = {196: identity[0], 197: identity[1], 200: fingerprint[0],
                     201: fingerprint[1], 202: suite}
            return [words[n] for n in range(start, start+count)]

    class NoModbus:
        def __getattr__(self, name):
            raise AssertionError("CPU control during STOP must not access Modbus")

    monkeypatch.setattr(module, "FXReadOnly", FX)
    bench = SimpleNamespace(verified=True, client=NoModbus(), expected_identity=(2, 31),
                            expected_fingerprint=(28642, 27104), expected_suite=2)
    return CPUControl(bench, isolated_bench=True), frames, reads


def test_cpu_control_accepts_verified_v002_on_programming_port(monkeypatch):
    control, frames, reads = install_fx(monkeypatch)
    control.write(8037, True)
    assert len(frames) == 1
    assert (196, 2) in reads
    assert any(start <= 200 and start+count >= 203 for start, count in reads)


@pytest.mark.parametrize("kwargs", [
    {"identity": (1, 31)},
    {"identity": (2, 30)},
    {"fingerprint": (28643, 27104)},
    {"fingerprint": (28642, 27105)},
    {"suite": 1},
])
def test_any_identity_word_mismatch_blocks_cpu_frame(monkeypatch, kwargs):
    control, frames, _ = install_fx(monkeypatch, **kwargs)
    with pytest.raises(ValueError, match="(?i)(identity|fingerprint|suite)"):
        control.write(8037, True)
    assert frames == []
