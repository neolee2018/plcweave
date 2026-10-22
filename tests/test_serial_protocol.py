import pytest
from plcweave.fx_serial import decode_read,read_frame

def test_actual_com5_capture_and_reject_corruption():
    assert read_frame(0x1000,2)==bytes.fromhex("0230313030303032033536")
    assert decode_read(bytes.fromhex("0230303030034333"),2)==b"\0\0"
    with pytest.raises(ValueError):
        decode_read(bytes.fromhex("0230303030034334"),2)
    with pytest.raises(ValueError):
        decode_read(bytes.fromhex("ffff0606"),2)
