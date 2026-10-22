import pytest
from plcweave.hil import Bench

class Reply:
    def __init__(self, values): self.registers=values
    def isError(self): return False

class WrongPLC:
    def __init__(self): self.writes=[]
    def connect(self): return True
    def read_holding_registers(self,*args,**kwargs): return Reply([0,0])
    def write_register(self,*args,**kwargs): self.writes.append(args)
    def close(self): pass

def test_wrong_plc_identity_never_enables_writes():
    client=WrongPLC()
    bench=Bench(client=client)
    with pytest.raises(ValueError,match="identity"): bench.verify()
    with pytest.raises(ValueError): bench.write("D1056",1400)
    assert client.writes==[]

def test_even_verified_bench_cannot_write_arbitrary_devices():
    bench=Bench(client=WrongPLC())
    bench.verified=True
    for device in ["D0","D8050","D8120","Y0"]:
        with pytest.raises(ValueError): bench.write(device,1)

def test_batched_reads_keep_watched_values_and_reduce_round_trips():
    class Client:
        def __init__(self): self.calls=[]
        def read_holding_registers(self,first,count,device_id):
            self.calls.append((first,count))
            return Reply(list(range(first,first+count)))
        def read_coils(self,first,count,device_id):
            self.calls.append((first,count))
            result=Reply([])
            result.bits=[(first+i)%2==0 for i in range(count)]
            return result
    client=Client();bench=Bench(client=client)
    watch=['D100','D102','D150','D154','D196','D197','D8050','M0','M10','Y0']
    result=bench.sample(watch)
    assert set(result)==set(watch)
    assert result['D102']==102 and result['D8050']==8050
    assert result['M0']==1 and result['M10']==1 and result['Y0']==1
    assert len(client.calls)<=6
