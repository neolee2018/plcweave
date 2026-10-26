"""Opt-in isolated-bench Modbus runner; never downloads or changes RUN/STOP."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from .testing import compare, digest, frozen_suite, suite_path

ALLOWED_WRITES={102,190,191,192,193,194,261,1056}
DEFAULT_BENCH={"port":"COM7","baud":9600,"parity":"N","bytesize":8,"stopbits":1,"station":1}
BAUD_RATES={600,1200,2400,4800,9600,19200,38400,57600,115200}
PARITIES={"N","E","O"}

def validate_bench_settings(values):
    """Validate reviewer-supplied serial settings before any port is opened."""
    data={**DEFAULT_BENCH,**dict(values)}
    unknown=set(data)-set(DEFAULT_BENCH)
    if unknown:raise ValueError(f"Unsupported bench settings: {sorted(unknown)}")
    port=data["port"]
    if not isinstance(port,str) or not re.fullmatch(r"(?i:COM(?:[1-9]|[1-9]\d|1\d\d|2[0-4]\d|25[0-6]))|/dev/tty[A-Za-z0-9._-]+",port):
        raise ValueError("Bench port must be COM1..COM256 or /dev/tty*")
    baud=data["baud"];parity=data["parity"]
    if type(baud) is not int or baud not in BAUD_RATES:raise ValueError(f"Unsupported baud rate: {baud}")
    if not isinstance(parity,str) or parity.upper() not in PARITIES:raise ValueError("Parity must be N, E or O")
    if type(data["bytesize"]) is not int or data["bytesize"] not in {7,8}:raise ValueError("Data bits must be 7 or 8")
    if type(data["stopbits"]) is not int or data["stopbits"] not in {1,2}:raise ValueError("Stop bits must be 1 or 2")
    if type(data["station"]) is not int or not 1<=data["station"]<=247:raise ValueError("Station must be 1..247")
    return {"port":port,"baud":baud,"parity":parity.upper(),"bytesize":data["bytesize"],
            "stopbits":data["stopbits"],"station":data["station"]}

def load_bench_settings(directory):
    path=Path(directory)/"bench_config.json"
    if not path.exists():return dict(DEFAULT_BENCH)
    try:data=json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:raise ValueError(f"Invalid bench_config.json: {exc}") from exc
    if not isinstance(data,dict):raise ValueError("bench_config.json must be an object")
    missing=set(DEFAULT_BENCH)-set(data)
    if missing:raise ValueError(f"bench_config.json is missing: {sorted(missing)}")
    return validate_bench_settings(data)

class Bench:
    def __init__(self,port=None,client=None,*,settings=None,expected_identity=(1,31),expected_fingerprint=None,expected_suite=None,allowed_writes=None):
        if settings is None:
            settings={**DEFAULT_BENCH,**({"port":port} if port else {})}
        self.settings=validate_bench_settings(settings)
        self.station=self.settings["station"]
        if client is None:
            try:
                from pymodbus.client import ModbusSerialClient
            except ModuleNotFoundError as exc:
                raise RuntimeError("HIL dependencies are missing; install with: pip install -e \".[hil]\"") from exc
            client=ModbusSerialClient(port=self.settings["port"],baudrate=self.settings["baud"],
                bytesize=self.settings["bytesize"],parity=self.settings["parity"],
                stopbits=self.settings["stopbits"],timeout=0.5,retries=0)
        self.client=client
        self.verified=False
        self.expected_identity=tuple(expected_identity)
        self.expected_fingerprint=None if expected_fingerprint is None else tuple(expected_fingerprint)
        self.expected_suite=expected_suite
        self.allowed_writes=set(ALLOWED_WRITES if allowed_writes is None else allowed_writes)

    def read_words(self,first,count):
        response=self.client.read_holding_registers(first,count=count,device_id=self.station)
        if response.isError() or len(getattr(response,"registers",[]))!=count:
            raise ConnectionError(f"FC03 D{first} count={count} station={self.station}: {response}")
        return [v-65536 if v>=32768 else v for v in response.registers]

    def verify(self):
        self.verified=False
        if not self.client.connect():
            raise ConnectionError(f"Cannot open {self.settings['port']}")
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
        if not device.startswith("D") or address not in self.allowed_writes or not self.verified:
            raise ValueError(f"Unverified or forbidden write: {device}")
        response=self.client.write_register(address,int(value)&65535,device_id=self.station)
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
            response=self.client.read_coils(first,count=count,device_id=self.station)
            if response.isError() or len(getattr(response,"bits",[]))<count:
                raise ConnectionError(f"FC01 {first} count={count}: {response}")
            values.update({name:int(response.bits[address-first]) for address,name in group})
        return values

    def close(self):
        self.client.close()

def candidate_bench(directory):
    """Bind new candidates to their source manifest before opening a serial port."""
    directory=Path(directory)
    settings=load_bench_settings(directory)
    path=directory/"build_identity.json"
    if not path.exists():
        # Backwards compatibility is limited to the explicitly numbered legacy suite.
        suite=frozen_suite(directory)
        if suite_path(directory).suffix=='.md' or suite.get("suite_version")!="V001":
            raise ValueError("New candidate requires build_identity.json; no serial access")
        return Bench(settings=settings)
    identity=json.loads(path.read_text(encoding="utf-8"))
    if identity.get("source_sha256")!=digest(directory/"source.fxil"):
        raise ValueError("Build identity is stale for current source; no serial access")
    words=identity.get("fingerprint_words")
    if not isinstance(words,list) or len(words)!=2 or any(type(w) is not int or not -32768<=w<=32767 for w in words):
        raise ValueError("Invalid candidate fingerprint words; no serial access")
    return Bench(settings=settings,expected_identity=(identity["program_version"],identity["edition"]),
                 expected_fingerprint=words,expected_suite=identity["suite_version_word"])

def preflight(directory):
    path=Path(directory)/"evidence/modbus-preflight.json"
    bench=None
    settings=load_bench_settings(directory)
    report={"environment":"hardware_protocol_preflight","port":settings["port"],"bench":settings,"writes":0}
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
    manual_path=directory/"manual_download.json"
    if not manual_path.is_file():
        raise ValueError("Missing manual_download.json; run `demo confirm-flash` or record the download first")
    demo_build=False
    identity_path=directory/"build_identity.json"
    if identity_path.is_file():
        try:demo_build=bool(json.loads(identity_path.read_text(encoding="utf-8")).get("demo"))
        except json.JSONDecodeError:demo_build=False
    record=json.loads(manual_path.read_text(encoding="utf-8"))
    binds=(record.get("source_sha256")==digest(directory/"source.fxil")
           and record.get("test_sha256")==digest(suite_path(directory))
           and bool(record.get("confirmed_by")) and bool(record.get("downloaded_at")))
    if demo_build:
        binds=binds and bool(record.get("compile_status")) and bool(record.get("run_state"))
    if not binds:
        raise ValueError("Manual download record must bind current source/test hashes, operator, time"
                         + (" and compile/RUN status" if demo_build else ""))
    if not isolated_bench:
        raise ValueError("Controlled writes require explicit isolated-bench authorization")
    if demo_build:
        ready_path=directory/"bench_ready.json"
        if not ready_path.is_file():
            raise ValueError("Demo S6 requires bench_ready.json; run `demo confirm-bench` after wiring")
        ready=json.loads(ready_path.read_text(encoding="utf-8"))
        if ready.get("source_sha256")!=record["source_sha256"] or ready.get("test_sha256")!=record["test_sha256"] or not ready.get("isolated_bench") or not ready.get("rs485_connected") or not ready.get("plc_running"):
            raise ValueError("Bench readiness is stale or incomplete; confirm isolated bench, RS485 and RUN again")
    bench=candidate_bench(directory)
    (directory/"evidence").mkdir(parents=True,exist_ok=True)
    report={"environment":"hardware_sampled","timestamp":datetime.now(timezone.utc).isoformat(),
            "bench":load_bench_settings(directory),"source_sha256":record["source_sha256"],
            "test_sha256":record["test_sha256"],"cases":[],"status":"UNVERIFIED"}
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
