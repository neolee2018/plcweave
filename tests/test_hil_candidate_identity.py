"""A stale program or suite must never unlock a new candidate's writes."""
import json
import pytest
from plcweave.hil import Bench, candidate_bench


class Reply:
    def __init__(self,values): self.registers=values
    def isError(self): return False


class Client:
    def __init__(self,version=2,fingerprint=(12,-34),suite=2):
        self.version=version;self.fingerprint=fingerprint;self.suite=suite
        self.writes=[];self.heartbeat=0
    def connect(self): return True
    def read_holding_registers(self,first,count,device_id):
        if first==196: return Reply([self.version,31])
        if first==200: return Reply([v&65535 for v in (*self.fingerprint,self.suite)])
        self.heartbeat+=1
        return Reply([self.heartbeat])
    def write_register(self,*args,**kwargs): self.writes.append(args);return Reply([])
    def close(self): pass


@pytest.mark.parametrize('kwargs',[{'version':1},{'fingerprint':(99,-34)},{'suite':1}])
def test_wrong_candidate_cannot_unlock_writes(kwargs):
    client=Client(**kwargs)
    bench=Bench(client=client,expected_identity=(2,31),expected_fingerprint=(12,-34),expected_suite=2)
    bench.verified=True  # A previous verification must not survive a failed recheck.
    with pytest.raises(ValueError,match='identity'): bench.verify()
    with pytest.raises(ValueError): bench.write('D191',1)
    assert not bench.verified and not client.writes


def test_expected_candidate_can_unlock_only_allowlisted_writes(monkeypatch):
    monkeypatch.setattr('plcweave.hil.time.sleep',lambda _:None)
    client=Client()
    bench=Bench(client=client,expected_identity=(2,31),expected_fingerprint=(12,-34),expected_suite=2)
    assert bench.verify()['suite']==2
    bench.write('D1056',1400)
    with pytest.raises(ValueError): bench.write('D8050',4000)
    assert client.writes==[(1056,1400)]


def test_stale_source_manifest_fails_before_serial_open(tmp_path,monkeypatch):
    (tmp_path/'source.fxil').write_text('changed',encoding='utf-8')
    (tmp_path/'build_identity.json').write_text(json.dumps({'source_sha256':'stale'}),encoding='utf-8')
    monkeypatch.setattr('plcweave.hil.Bench',lambda *a,**kw:pytest.fail('Serial client was constructed'))
    with pytest.raises(ValueError,match='stale'): candidate_bench(tmp_path)


def test_full_trace_suite_cannot_silently_use_legacy_hardware_runner(tmp_path,monkeypatch):
    from plcweave.hil import run
    monkeypatch.setattr('plcweave.hil.frozen_suite',lambda _: {'relationship_invariants':[{'kind':'physical_routing'}]})
    monkeypatch.setattr('plcweave.hil.Bench',lambda *a,**kw:pytest.fail('Serial client was constructed'))
    with pytest.raises(ValueError,match='qualified sampled replay'): run(tmp_path,True)
