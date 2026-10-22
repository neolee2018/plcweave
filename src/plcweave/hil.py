"""Opt-in isolated-bench Modbus runner; never downloads or changes RUN/STOP."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from .testing import compare, digest, frozen_suite, suite_path

ALLOWED_WRITES={102,190,191,192,193,194,261,1056}

class Bench:
    def __init__(self,port="COM7",client=None,*,expected_identity=(1,31),expected_fingerprint=None,expected_suite=None):
        if client is None:
            from pymodbus.client import ModbusSerialClient
            client=ModbusSerialClient(port=port,baudrate=9600,bytesize=8,parity="N",stopbits=1,timeout=0.5,retries=0)
        self.client=client
        self.verified=False
        self.expected_identity=tuple(expected_identity)
        self.expected_fingerprint=None if expected_fingerprint is None else tuple(expected_fingerprint)
        self.expected_suite=expected_suite

    def read_words(self,first,count):
        response=self.client.read_holding_registers(first,count=count,device_id=1)
        if response.isError() or len(getattr(response,"registers",[]))!=count:
            raise ConnectionError(f"FC03 D{first} count={count}: {response}")
        return [v-65536 if v>=32768 else v for v in response.registers]

    def verify(self):
        self.verified=False
        if not self.client.connect():
            raise ConnectionError("Cannot open COM7")
        version,edition=self.read_words(196,2)
        if (version,edition)!=self.expected_identity:
            raise ValueError(f"Unexpected program identity: {version}/{edition}; no write allowed")
        fingerprint=None
        suite=None
        if self.expected_fingerprint is not None or self.expected_suite is not None:
            words=self.read_words(200,3)
            fingerprint=words[:2]
            suite=words[2]
            if self.expected_fingerprint is not None and tuple(fingerprint)!=self.expected_fingerprint:
                raise ValueError("Build fingerprint identity mismatch; no write allowed")
            if self.expected_suite is not None and suite!=self.expected_suite:
                raise ValueError("Test-suite identity mismatch; no write allowed")
        first=self.read_words(198,1)[0]
        time.sleep(0.25)
        second=self.read_words(198,1)[0]
        if first==second:
            raise ValueError("PLC heartbeat did not advance; no write allowed")
        self.verified=True
        return {"version":version,"edition":edition,"fingerprint_words":fingerprint,"suite":suite,"heartbeat_before":first,"heartbeat_after":second}

    def write(self,device,value):
        address=int(device.removeprefix("D"))
        if not device.startswith("D") or address not in ALLOWED_WRITES or not self.verified:
            raise ValueError(f"Unverified or forbidden write: {device}")
        response=self.client.write_register(address,int(value)&65535,device_id=1)
        if response.isError():
            raise ConnectionError(f"FC06 {device}: {response}")

    def sample(self,watch):
        values={}
        # Merge small gaps to reduce serial round trips. Return watched values
        # only; a block remains <=125 holding registers and never spans banks.
        words=sorted(int(d[1:]) for d in watch if d.startswith("D"))
        groups=[]
        for address in words:
            if not groups or address>groups[-1][-1]+9 or address-groups[-1][0]>=125:
                groups.append([address])
            else:
                groups[-1].append(address)
        for group in groups:
            block=self.read_words(group[0],group[-1]-group[0]+1)
            values.update({f"D{address}":block[address-group[0]] for address in group})
        coils=[]
        for name in watch:
            if name.startswith("D"): continue
            if name.startswith("Y"):
                address=0x3300+int(name[1:],8)
            elif name.startswith("M"):
                index=int(name[1:])
                if 0<=index<=7679: address=index
                elif 8000<=index<=8511: address=0x1E00+index-8000
                else: raise ValueError(f"Unsupported coil: {name}")
            else: raise ValueError(f"Unsupported observation: {name}")
            coils.append((address,name))
        groups=[]
        for item in sorted(coils):
            if not groups or item[0]>groups[-1][-1][0]+16 or item[0]-groups[-1][0][0]>=2000:
                groups.append([item])
            else: groups[-1].append(item)
        for group in groups:
            first=group[0][0]
            count=group[-1][0]-first+1
            response=self.client.read_coils(first,count=count,device_id=1)
            if response.isError() or len(getattr(response,"bits",[]))<count:
                raise ConnectionError(f"FC01 {first} count={count}: {response}")
            values.update({name:int(response.bits[address-first]) for address,name in group})
        return values

    def close(self):
        self.client.close()

def candidate_bench(directory):
    """Bind new candidates to their source manifest before opening a serial port."""
    directory=Path(directory)
    path=directory/"build_identity.json"
    if not path.exists():
        # Backwards compatibility is limited to the explicitly numbered legacy suite.
        suite=frozen_suite(directory)
        if suite_path(directory).suffix=='.md' or suite.get("suite_version")!="V001":
            raise ValueError("New candidate requires build_identity.json; no serial access")
        return Bench()
    identity=json.loads(path.read_text(encoding="utf-8"))
    if identity.get("source_sha256")!=digest(directory/"source.fxil"):
        raise ValueError("Build identity is stale for current source; no serial access")
    words=identity.get("fingerprint_words")
    if not isinstance(words,list) or len(words)!=2 or any(type(w) is not int or not -32768<=w<=32767 for w in words):
        raise ValueError("Invalid candidate fingerprint words; no serial access")
    return Bench(expected_identity=(identity["program_version"],identity["edition"]),expected_fingerprint=words,expected_suite=identity["suite_version_word"])

def preflight(directory):
    path=Path(directory)/"evidence/modbus-preflight.json"
    bench=None
    report={"environment":"hardware_protocol_preflight","port":"COM7","writes":0}
    try:
        bench=candidate_bench(directory)
        report.update(bench.verify(),status="PROTOCOL_READ_PASS")
    except Exception as exc:
        report.update(status="TEST_INFRA_ERROR",error=str(exc))
    finally:
        if bench is not None: bench.close()
        report["cleanup"]="serial_closed"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def run(directory, isolated_bench=False):
    directory=Path(directory)
    suite=frozen_suite(directory)
    if suite.get("relationship_invariants"):
        raise ValueError("UNVERIFIED: this full-trace suite requires a qualified sampled replay adapter; the legacy endpoint runner cannot validate it. No serial access attempted.")
    record=json.loads((directory/"manual_download.json").read_text(encoding="utf-8"))
    if record.get("source_sha256")!=digest(directory/"source.fxil") or record.get("test_sha256")!=digest(suite_path(directory)) or not record.get("confirmed_by") or not record.get("downloaded_at"):
        raise ValueError("Manual download record must bind current source/test hashes, operator and time")
    if not isolated_bench:
        raise ValueError("Controlled writes require explicit isolated-bench authorization")
    bench=candidate_bench(directory)
    report={"environment":"hardware_sampled","timestamp":datetime.now(timezone.utc).isoformat(),"source_sha256":record["source_sha256"],"test_sha256":record["test_sha256"],"cases":[],"status":"UNVERIFIED"}
    batch_deadline=time.monotonic()+600
    try:
        report["identity"]=bench.verify()
        with (directory/"evidence/hardware_trace.jsonl").open("w",encoding="utf-8") as stream:
            for case in suite["cases"]:
                if time.monotonic()>batch_deadline:
                    raise TimeoutError("Hardware batch exceeded 600 seconds")
                if case["initial_words"]:
                    report["cases"].append({"id":case["id"],"status":"UNVERIFIED","reason":"First-scan/retention case requires an independently recorded manual STOP/RUN or power cycle"})
                    continue
                print(f"START {case['id']}",flush=True)
                # Reset and confirm between cases. Hardware is never downloaded or RUN-switched here.
                for name,value in {"D191":0,"D192":1,"D193":0,"D102":60,"D190":1,"D1056":0}.items(): bench.write(name,value)
                time.sleep(0.1)
                if compare(bench.sample(["M0","D154"]),{"M0":0,"D154":0}):
                    raise ValueError("Case reset did not reach stopped zero-output state")
                bench.write("D192",0)
                failures=[]
                for index,step in enumerate(case["steps"]):
                    for name,value in step["write"].items(): bench.write(name,value)
                    started=time.monotonic()
                    deadline=started+step["duration_ms"]/1000
                    last={}
                    while True:
                        if time.monotonic()>batch_deadline:
                            raise TimeoutError("Hardware batch exceeded 600 seconds")
                        sample_started=time.monotonic()
                        last=bench.sample(suite["watch"])
                        row={"case_id":case["id"],"step":index,"elapsed_ms":round((time.monotonic()-started)*1000),"sample_span_ms":round((time.monotonic()-sample_started)*1000),"values":last}
                        stream.write(json.dumps(row)+"\n")
                        stream.flush()
                        errors=compare(last,suite["global_invariants"])+compare(last,step["invariant"])
                        if errors: failures.append(errors)
                        if time.monotonic()>=deadline: break
                        time.sleep(min(0.05,max(0,deadline-time.monotonic())))
                    errors=compare(last,step["expect"])
                    if errors: failures.append(errors)
                report["cases"].append({"id":case["id"],"status":"PROGRAM_FAIL" if failures else "UNVERIFIED","sampled_checks":"FAIL" if failures else "PASS","failures":failures[:12],"reason":"Polling cannot certify scan-level invariants or exact timer boundaries; physical I/O unmeasured"})
                print(f"END {case['id']} sampled_checks={'FAIL' if failures else 'PASS'}",flush=True)
                (directory/"evidence/hardware_progress.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        if any(case.get("status")=="PROGRAM_FAIL" for case in report["cases"]):
            report["status"]="PROGRAM_FAIL"
    except Exception as exc:
        report.update(status="TEST_INFRA_ERROR",error=str(exc))
    finally:
        # Only this task's allowlisted commands are restored; never global cleanup.
        if bench.verified:
            try:
                for name,value in {"D191":0,"D192":1,"D193":0}.items(): bench.write(name,value)
                time.sleep(0.1)
                report["exit_state"]=bench.sample(["M0","D154","D8050","D8051"])
                if compare(report["exit_state"],{"M0":0,"D154":0,"D8050":0,"D8051":0}):
                    raise ValueError("Final stopped/output-zero state was not confirmed")
                report["cleanup"]="stopped_output_disabled_and_read_back_zero"
            except Exception as exc:
                report["cleanup"]="restore_unconfirmed"
                report["cleanup_error"]=str(exc)
        bench.close()
        report["serial_closed"]=True
        (directory/"evidence/hardware_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
