"""Shared assertions for simulated and sampled hardware observations."""
import csv
import hashlib
import json
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def compare(observation, expectations):
    failures = []
    for device, expected in expectations.items():
        if isinstance(expected, dict) and (not expected or set(expected)-{"min", "max"}):
            raise ValueError(f"Unsupported scalar assertion for {device}: {expected}")
        if device not in observation or observation[device] is None:
            failures.append({"device":device,"kind":"UNVERIFIED","expected":expected,"actual":None})
            continue
        actual = observation[device]
        ok = (expected.get("min", actual) <= actual <= expected.get("max", actual)) if isinstance(expected,dict) else actual == expected
        if not ok:
            failures.append({"device":device,"kind":"PROGRAM_FAIL","expected":expected,"actual":actual})
    return failures

def suite_path(directory):
    directory=Path(directory)
    md=directory/'test_cases.md';legacy=directory/'test_cases.json'
    if md.exists() and legacy.exists():raise ValueError('Ambiguous test sources: keep one authoritative suite')
    return md if md.exists() else legacy

def frozen_suite(directory):
    directory=Path(directory)
    source=suite_path(directory)
    if source.suffix=='.md':
        from .markdown_suite import read_freeze,parse_markdown
        freeze=read_freeze(directory)
    else:
        freeze=json.loads((directory/"s1-freeze.json").read_text(encoding="utf-8"))
    for file,expected in freeze.items():
        if digest(directory/file)!=expected:
            raise ValueError(f"Frozen S1 input changed: {file}")
    suite=parse_markdown(source) if source.suffix=='.md' else json.loads(source.read_text(encoding='utf-8'))
    from .validation import validate_suite
    validate_suite(suite)
    if suite.get("requirements_sha256") and digest(directory/"requirements.md")!=suite["requirements_sha256"]:
        raise ValueError("Suite does not bind current frozen requirements")
    return suite

def engine_gate(output):
    """Execute deliberate unsupported fixtures; no unknown form may be a NOP."""
    import gxwlib
    from .fx import write_program
    fixtures=("BOGUS M0", "PID D0 D1 D2 D3", "MOV K1 D8512", "LD M99999")
    results=[]
    path=Path(output)/"S3-unsupported-fixture.csv"
    try:
        for text in fixtures:
            rows=[{"mnemonic":"LD","operands":["M8000"]}]
            parts=text.split()
            rows.extend([{"mnemonic":parts[0],"operands":parts[1:]},{"mnemonic":"END","operands":[]}])
            write_program(path,rows,quoted=True)
            try:
                compiled=gxwlib.compile_program(gxwlib.load_csv(path,device_profile="fx"),profile="fx3u")
                gxwlib.Simulator(compiled,scan_period_ns=10_000_000).run(1,watch=["M0"])
            except gxwlib.GxwError as exc:
                results.append({"fixture":text,"status":"BLOCKED","error":str(exc),"code":getattr(exc,"code",None)})
            else:
                results.append({"fixture":text,"status":"TEST_INFRA_ERROR","error":"Unsupported fixture executed without rejection"})
    finally:
        path.unlink(missing_ok=True)
    return {"status":"PASS" if all(r["status"]=="BLOCKED" for r in results) else "TEST_INFRA_ERROR","fixtures":results}

def simulate(directory, output=None):
    import gxwlib
    from .fx import export
    directory=Path(directory)
    suite=frozen_suite(directory)
    from .validation import SCHEMA
    independent=suite.get("schema_version")==SCHEMA
    output=Path(output or directory/("evidence/simulation/latest" if independent else "candidate/V001"))
    instructions=export(directory/"source.fxil",output)
    (output/"simulation_trace.csv").unlink(missing_ok=True)
    from gxwlib import _core
    report={"environment":"local_instruction_simulator","engine_binary_sha256":digest(_core.__file__),"source_sha256":digest(directory/"source.fxil"),
            "test_sha256":digest(suite_path(directory)),"suite_version":suite["suite_version"],
            "scan_ms":suite["scan_ms"],"instruction_count":len(instructions),"cases":[],
            "limits":["No vendor or hardware equivalence claimed", "ADC/DAC and UART are external register images", "No power-cycle retention model"]}
    from .validation import InputImage, INPUTS, TraceOracle, independent_fingerprint
    report["comparator_sha256"]=digest(Path(__file__).with_name("validation.py"))
    context={}
    if independent:
        report["engine_gate"]=engine_gate(output)
        context["engine_gate_pass"]=report["engine_gate"]["status"]=="PASS"
        try:
            report["independent_fingerprint"]=independent_fingerprint(directory/"source.fxil")
            context.update(report["independent_fingerprint"])
        except ValueError as exc:
            report["independent_fingerprint"]={"status":"UNVERIFIED","error":str(exc)}
    try:
        compiled=gxwlib.compile_program(gxwlib.load_csv(output/"runtime.csv",device_profile="fx"),profile="fx3u")
    except gxwlib.GxwError as exc:
        report.update(status="BLOCKED",error=str(exc),error_code=getattr(exc,"code",None),diagnostic_pause=True)
        (output/"simulation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        return report
    columns=["case_id","step","time_ms"]+suite["watch"]+(["applied_"+name for name in INPUTS] if independent else [])
    with (output/"simulation_trace.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        for case in suite["cases"]:
            sim=gxwlib.Simulator(compiled,scan_period_ns=suite["scan_ms"]*1_000_000)
            sim.set_word_devices(case["initial_words"])
            inputs=InputImage(case["initial_words"])
            oracle=TraceOracle(suite,case,capabilities={"full_scan_trace":True,"verified_applied_inputs":True},context=context)
            failures=[]
            failure_count=0
            failure_kinds=set()
            scans=0
            for index,step in enumerate(case["steps"]):
                words={key:value for key,value in step["write"].items() if key.startswith("D")}
                bits={key:bool(value) for key,value in step["write"].items() if not key.startswith("D")}
                if words: sim.set_word_devices(words)
                if bits: sim.set_inputs(bits)
                inputs.apply(step["write"])
                count=step["duration_ms"]//suite["scan_ms"]
                if count<1 or count*suite["scan_ms"]!=step["duration_ms"]:
                    raise ValueError("Duration must be a positive multiple of scan_ms")
                last={}
                # Bound runtime trace allocations without dropping a scan.
                for offset in range(0,count,256):
                    trace=sim.run(min(256,count-offset),watch=suite["watch"])
                    if len(trace.samples)!=min(256,count-offset):
                        raise ValueError("TEST_INFRA_ERROR: runtime returned an incomplete scan trace")
                    bit_names=[name for name in trace.watch if not name.startswith("D")]
                    for sample in trace.samples:
                        observation=dict(zip(bit_names,[int(v) for v in sample.values]))
                        observation.update(sample.words)
                        before_scan=inputs.values.copy()
                        applied=inputs.next_scan()
                        row={"case_id":case["id"],"step":index,"time_ms":sample.time_ns//1_000_000,**observation}
                        if independent:
                            row.update({"applied_"+key:value for key,value in before_scan.items()})
                            oracle.consume(observation,applied,row["time_ms"])
                        writer.writerow(row)
                        errors=compare(observation,suite["global_invariants"])+compare(observation,step["invariant"])
                        if errors:
                            failure_count+=len(errors)
                            failure_kinds.update(error["kind"] for error in errors)
                            if len(failures)<12:
                                failures.append({"step":index,"time_ms":row["time_ms"],"checks":errors})
                        last=observation
                errors=compare(last,step["expect"])
                if errors:
                    failure_count+=len(errors)
                    failure_kinds.update(error["kind"] for error in errors)
                    failures.append({"step":index,"checkpoint":True,"checks":errors})
                scans+=count
            relationships=oracle.finish() if independent else []
            failure_kinds.update(r["status"] for r in relationships if r["status"]!="PASS")
            status="PROGRAM_FAIL" if "PROGRAM_FAIL" in failure_kinds else "UNVERIFIED" if failure_kinds else "PASS"
            result={"id":case["id"],"status":status,"scans":scans,"failures":failures[:12],"scalar_violation_count":failure_count}
            if independent:
                result.update(relationships=relationships,metrics=oracle.metrics(),priority=case["priority"])
            report["cases"].append(result)
            print(case["id"],result["status"],flush=True)
    statuses={case["status"] for case in report["cases"]}
    report["status"]="PROGRAM_FAIL" if "PROGRAM_FAIL" in statuses else "UNVERIFIED" if "UNVERIFIED" in statuses else "SIM_PASS"
    if independent and report["engine_gate"]["status"]!="PASS":
        report["status"]="TEST_INFRA_ERROR"
    if independent:
        from .validation import KINDS
        coverage={kind:{"case_count":0,"evaluated_scans":0,"violation_count":0,"statuses":set()} for kind in KINDS}
        for result in report["cases"]:
            for check in result["relationships"]:
                entry=coverage[check["kind"]]
                entry["case_count"]+=1
                entry["evaluated_scans"]+=check["evaluated_scans"]
                entry["violation_count"]+=check["violation_count"]
                entry["statuses"].add(check["status"])
        for entry in coverage.values():
            entry["statuses"]=sorted(entry["statuses"])
            if not entry["evaluated_scans"] and report["status"]=="SIM_PASS":
                report["status"]="UNVERIFIED"
        report["relationship_coverage"]=coverage
    # Detect changes to frozen input files made during execution as well.
    frozen_suite(directory)
    (output/"simulation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report
