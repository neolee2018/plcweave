import pytest
from plcweave.cpu_control import CPUControl

class Bench:
    verified=False
    client=None

def test_restart_cannot_run_without_both_guards():
    bench=Bench()
    with pytest.raises(ValueError): CPUControl(bench,isolated_bench=True)
    bench.verified=True
    with pytest.raises(ValueError): CPUControl(bench)

def test_restart_cannot_write_other_special_relays():
    bench=Bench();bench.verified=True
    control=CPUControl(bench,isolated_bench=True)
    with pytest.raises(ValueError): control.write(8034,True)

def test_restart_recovers_without_the_modbus_transport(monkeypatch):
    # Actual bug seam: the PLC disables Modbus while STOPped. Recovery must
    # remain possible over the independently available programming port.
    import plcweave.cpu_control as module
    class Unavailable:
        def __getattr__(self,name): raise AssertionError('Modbus unavailable during STOP')
    state={8000:True,8035:False,8036:False,8037:False}
    class Serial:
        def reset_input_buffer(self): pass
        def write(self,frame):
            body=frame[1:-3]
            if body[:1] in (b'7',b'8'):
                address=int(body[3:5]+body[1:3],16)
                relay=address-0x0F00+8000
                state[relay]=body[:1]==b'7'
                if relay==8037 and state[relay]: state[8000]=False
                if relay==8036 and state[relay] and state[8035]: state[8000]=True;state[8037]=False
                self.reply=b'\x06'
            else:
                image=bytearray(8)
                for relay,on in state.items():
                    if on: image[(relay-8000)//8]|=1<<((relay-8000)%8)
                payload=image.hex().upper().encode()+b'\x03'
                self.reply=b'\x02'+payload+f'{sum(payload)&255:02X}'.encode()
        def read(self,count): return self.reply
    serial=Serial()
    class FX:
        def __enter__(self): self.serial=serial;return self
        def __exit__(self,*args): pass
        def read_words(self,start,count): return [1,31] if start==196 else [99]
    monkeypatch.setattr(module,'FXReadOnly',FX)
    bench=Bench();bench.verified=True;bench.client=Unavailable()
    control=CPUControl(bench,isolated_bench=True)
    assert control.stop()['M8000']==0
    assert control.start()['M8000']==1
