"""A short executable Python test for the bench window's script integration."""
import time
import argparse

from plcweave.bench.contract import DEFAULT_DEMO_PROFILE as profile, group_checksum
from plcweave.bench.rtu import LoopbackTransport, RtuClient
from plcweave.bench.virtual import VirtualPLC

parser = argparse.ArgumentParser()
parser.add_argument("--step-delay", type=float, default=0.25)
args = parser.parse_args()
if not 0 <= args.step_delay <= 10:
    parser.error("--step-delay must be between 0 and 10 seconds")


client = RtuClient(LoopbackTransport(VirtualPLC(profile)), 1)
try:
    assert client.read_words(196, 1) == [101]
    client.write_word(profile.session_request, 1)
    assert client.read_words(profile.session_confirm, 1) == [1]
    for sequence, raw in enumerate((1000, 2000, 3000), 1):
        x = [sequence % 2, 0, 0, 0, 0, 0, 0, 0]
        ad = [raw, raw // 2, 0, 0]
        client.write_words(profile.x_command[0], x)
        client.write_words(profile.ad_command[0], ad)
        client.write_word(profile.content_checksum, group_checksum([*x, *ad]))
        client.write_word(profile.request_seq, sequence)
        assert client.read_words(profile.ack_seq, 1) == [sequence]
        client.read_words(profile.x_effective[0], 8)
        client.read_words(profile.ad_effective[0], 4)
        print(f"步骤 {sequence}：AD0={raw}，观察 PLC 输出", flush=True)
        assert client.read_words(8050, 2) == [raw, raw // 2]
        client.read_bits(1, 0x3300, 8)
        time.sleep(args.step_delay)
    client.write_word(260, 88)
    assert client.read_words(260, 1) == [88]
    print("脚本断言全部通过", flush=True)
finally:
    client.write_word(profile.end_request, 1)
    client.read_words(8050, 2)
    client.read_bits(1, 0x3300, 8)
    client.close()
