"""Create S4 artifacts only after the independently checked S3 gate is green."""
import csv
import hashlib
import html
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from plcweave.fx import parse_fxil
from plcweave.testing import digest, frozen_suite

CASE = Path(__file__).resolve().parent
WORKSPACE = CASE.parents[1]
DOC = CASE / 'Doc'
OUT = CASE / 'candidate/V002'
SIM = CASE / 'evidence/simulation/latest'
SKILL = Path(os.environ['USERPROFILE'])/'.agents/skills/plc-program-development'
CSS = '''@page{size:A4;margin:16mm 15mm 17mm}body{font-family:Arial,"Microsoft YaHei",sans-serif;font-size:9pt;line-height:1.4;color:#162c43;margin:0}h1{font-size:22pt;color:#123f68}h2{font-size:14pt;break-after:avoid;margin-top:22px}h3{font-size:11pt;break-after:avoid;margin-top:18px}table{width:100%;border-collapse:collapse;font-size:7.7pt;margin:8px 0}thead{display:table-header-group}tr{break-inside:avoid}th,td{border:1px solid #cbd6df;padding:4px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#eef3f7}code{font-family:Consolas,monospace;font-size:8pt}.banner{border:2px solid #b77818;padding:10px;background:#fff7e8}.hash{font-family:Consolas,monospace;overflow-wrap:anywhere;font-size:7pt}header{border-bottom:2px solid #123f68;padding-bottom:8px}.page{break-before:page}footer{font-size:8pt;color:#536578}p{margin:7px 0}'''
CSS+='''table{table-layout:fixed}th{overflow-wrap:normal;word-break:normal}.duration{white-space:pre-line;overflow-wrap:normal;word-break:normal}.case,.regchunk{break-inside:avoid}.casehead{break-inside:avoid;break-after:avoid}.casehead+table{break-before:avoid}'''


def esc(value):
    return html.escape(str(value))


def table(headers, rows):
    widths=([7,27,10,56] if headers==['Step','Apply','Duration','Expected'] else [7,14,22,57] if headers==['Step','Instruction','Operands','Comment'] else [18,12,23,16,31] if len(headers)==5 else [32,68])
    cols='<colgroup>'+''.join(f'<col style="width:{w}%">' for w in widths)+'</colgroup>'
    return '<table>'+cols+'<thead><tr>' + ''.join('<th>'+esc(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td'+(' class="duration"' if headers==['Step','Apply','Duration','Expected'] and i==2 else '')+'>'+esc(x)+'</td>' for i,x in enumerate(row))+'</tr>' for row in rows) + '</tbody></table>'


def fmt(value):
    if isinstance(value,dict):
        if set(value) and set(value)<={'min','max'}:return '['+str(value.get('min','-inf'))+'..'+str(value.get('max','+inf'))+']'
        return ', '.join(f'{key}={fmt(item) if isinstance(item,dict) else item}' for key,item in value.items()) or '-'
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')) if value else '-'


def step_rows(steps):
    """Losslessly condense repeated two-step stimulus/check patterns for print."""
    def key(step): return {k:v for k,v in step.items() if k!='note'}
    rows=[];i=0
    while i<len(steps):
        repeats=1
        if i+3<len(steps):
            while i+2*repeats+1<len(steps) and all(key(steps[i+j])==key(steps[i+2*repeats+j]) for j in (0,1)):
                repeats+=1
        if repeats>=3:
            a,b=steps[i:i+2]
            rows.append([f'{i+1}..{i+2*repeats}',f"Repeat A then B, {repeats} times. A: {fmt(a['write'])}; B: {fmt(b['write'])}",f"A {a['duration_ms']}ms; B {b['duration_ms']}ms",f"A each-scan {fmt(a['invariant'])}, end {fmt(a['expect'])}; B each-scan {fmt(b['invariant'])}, end {fmt(b['expect'])}"])
            i+=2*repeats
        else:
            s=steps[i]
            rows.append([i+1,fmt(s['write']),str(s['duration_ms'])+'ms',f"Each-scan {fmt(s['invariant'])}; end {fmt(s['expect'])}. "+s.get('note','')])
            i+=1
    return rows


def find_edge():
    for base in (os.environ.get('PROGRAMFILES(X86)'),os.environ.get('PROGRAMFILES'),os.environ.get('LOCALAPPDATA')):
        if base and (Path(base)/'Microsoft/Edge/Application/msedge.exe').exists():return Path(base)/'Microsoft/Edge/Application/msedge.exe'
    found=shutil.which('msedge')
    if found:return Path(found)
    raise FileNotFoundError('msedge.exe not found in standard locations')

def print_pdf(name, title, body):
    import pymupdf
    source=DOC/(name+'.html');target=OUT/(name+'.pdf')
    source.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>'+esc(title)+'</title><style>'+CSS+'</style><body><header>HBDTECH | PLCWeave | L01S-16M-4AD2DA | Candidate V002</header><h1>'+esc(title)+'</h1>'+body+'<footer>V002 candidate - local logic verification only; new manual download required.</footer></body></html>',encoding='utf-8')
    edge=find_edge()
    with tempfile.TemporaryDirectory(prefix='pdf-profile-',dir=CASE/'evidence') as profile:
        result=subprocess.run([str(edge),'--headless=new','--disable-gpu','--disable-extensions','--no-pdf-header-footer',f'--user-data-dir={profile}',f'--print-to-pdf={target.resolve()}',source.resolve().as_uri()],capture_output=True,timeout=45)
        if result.returncode or not target.exists(): raise RuntimeError('PDF print failed: '+result.stderr.decode('utf-8',errors='replace')[-600:])
    metadata=target.with_suffix('.metadata.pdf')
    with pymupdf.open(target) as pdf:
        pdf.set_metadata({'title':title,'author':'HBDTECH','subject':'V002 independent S1/S2/S3 candidate; vendor and hardware gates not executed','creator':'PLCWeave'})
        for index,page in enumerate(pdf):
            page.insert_text((page.rect.width-70,page.rect.height-22),f'{index+1} / {len(pdf)}',fontsize=8,color=(0.35,0.4,0.45))
        pdf.save(metadata)
    metadata.replace(target)
    render=CASE/'evidence/pdfqa'/name;render.mkdir(parents=True,exist_ok=True)
    for old in render.glob('page-*.png'):old.unlink()
    with pymupdf.open(target) as pdf:
        text=''.join(page.get_text() for page in pdf)
        assert 'V002' in text and 'HBDTECH' in text and len(text)>400
        assert not any(term in text.casefold() for term in ('coolmay','gx_check_pass: true','hardware_pass: true'))
        for index,page in enumerate(pdf): page.get_pixmap(dpi=100).save(render/f'page-{index+1:03d}.png')
        return {'file':target.name,'pages':len(pdf),'sha256':digest(target)}


def main():
    suite=frozen_suite(CASE)
    report=json.loads((SIM/'simulation_report.json').read_text(encoding='utf-8'))
    review=json.loads((CASE/'evidence/S3-final-review.json').read_text(encoding='utf-8'))
    assert report['status']=='SIM_PASS' and all(c['status']=='PASS' for c in report['cases'])
    assert len(report['cases'])==len(suite['cases'])==55
    assert report['source_sha256']==digest(CASE/'source.fxil') and report['test_sha256']==digest(CASE/'test_cases.json')
    assert report['comparator_sha256']==digest(WORKSPACE/'src/plcweave/validation.py')
    coverage=report['relationship_coverage']
    assert len(coverage)==10 and all(r['evaluated_scans']>0 and r['violation_count']==0 and r['statuses']==['PASS'] for r in coverage.values())
    assert review['status']=='PASS' and review['source_sha256']==report['source_sha256'] and review['test_sha256']==report['test_sha256']
    OUT.mkdir(parents=True,exist_ok=True);DOC.mkdir(exist_ok=True)
    for name in ('MAIN.csv','COMMENT.csv','simulation_report.json','simulation_trace.csv'):
        shutil.copy2(SIM/name,OUT/name)
    for name in ('source.fxil','requirements.md','test_cases.json','s0-freeze.json','s1-freeze.json','s1-attestation.json','S1-design-review.md','build_identity.json','register_map.csv','io_map.csv','machine-profile.md','workflow.md','platformio.ini'):
        shutil.copy2(CASE/name,OUT/name)
    shutil.copy2(CASE/'S1-Test-Cases_EN.md',DOC/'S1-Test-Cases_EN.md')
    with (CASE/'register_map.csv').open(encoding='utf-8-sig',newline='') as f: registers=list(csv.DictReader(f))
    register_rows=[[r['device']+' / '+r['modbus_space']+' '+(r['offset_decimal'] or 'unverified'),r['permission']+' / '+r['data_type'],r['unit']+' / '+r['first_scan_default'],r['range_or_encoding'],r['description']] for r in registers]
    mapping_notes=sorted({r['mapping_status'] for r in registers})
    banner='<div class="banner"><b>CANDIDATE V002 - INDEPENDENT LOCAL LOGIC CHECKS PASSED.</b><br>55 MUST cases,10 relationship oracles. New manual compile/download required. GX: NOT_EXECUTED by user instruction. V002 hardware and physical I/O: UNVERIFIED. Fixed-point PI, derivative zero.</div>'
    hashes='<p class="hash">Source SHA256: '+report['source_sha256']+'<br>Tests SHA256: '+report['test_sha256']+'</p>'
    identity=json.loads((CASE/'build_identity.json').read_text(encoding='utf-8'))
    setup='''<h2>1. Bench setup and download gate</h2><p>Keep the empty PLC isolated; no sensors, actuators or loads are attached. COM5 is the application programming port. COM7 is Modbus RTU station1,9600/8/N/1. Default D190=1 selects simulated pressure D1056, raw0..4000=0..16.0bar; D193=0 blocks AO0 and Y0. AO1 always zero. No servo is used; servo parameters are not applicable.</p><ol><li>Use a known compatible L01S application compiler/downloader, preserving the original runtime firmware. This task has no validated automatic uploader. User instructed not to use GX Works2; no manufacturer compilation result is claimed.</li><li>Download this exact V002 MAIN.csv/COMMENT.csv or supported instruction-list representation through COM5. Record software/version,operator,time and source/test hashes. Old V001 confirmation does not apply.</li><li>RUN on the isolated bench; read D196=2,D197=31,D202=2 and the build words below. Check changing D198/D199, D190=1,D193=0 and stopped zero outputs.</li><li>After download confirmation, read-only identity/preflight precedes controlled input writes. Do not write scratch, ADC or AO words. Hardware polling cannot establish one-scan invariants; only suitable cases are replayed.</li><li>Finish with D191=0,D192=1,D193=0 and read back M0=D154=D8050=D8051=Y0=0. CPU STOP disables COM7 on the prior sample; use documented COM5 recovery for authorized STOP/RUN tests.</li></ol>'''
    setup+=table(['Identity','Expected'],[['Program/edition/suite','2 /31 /2'],['D200/D201',fmt(identity['fingerprint_words'])],['Fingerprint limitation','Build correlation, not binary readback attestation']])
    register_html=''.join('<div class="regchunk">'+table(['Device / Modbus offset','Access / type','Unit / first-scan default','Range / encoding','Meaning'],register_rows[i:i+14])+'</div>' for i in range(0,len(register_rows),14))
    cases=setup+'<h2>2. Complete register map</h2><p>RW/RO are application contracts,not device security. D holding-register offset=n; M0 coil0; Y0 coil0x3300. Confirm this version read-only before writes. Signed16 values; two-word arithmetic storage low word first. Modes:1 test,0 AI0; other modes stop and inhibit restart until valid mode/start0 then new start1. State M0 run,M10 pre-sleep,M11 sleep; M10/M11 mutually exclusive. No alarm-code word or native PID parameter block is exposed.</p>'+register_html+'<p>Mapping notes: '+esc('; '.join(mapping_notes))+'. See register_map.csv for both decimal and hex offsets.</p>'
    cases+='<h2>3. Frozen replay cases</h2><p>Each case is isolated. Seed initial words before an actual first scan for initialization cases. The first10ms boot step is a local simulation operation,not a hardware RESET command. Other bench cases require a verified stopped/reset state. Each-scan checks require full local traces; host polling evidence is separately qualified. Every case includes a blank independent retest result field.</p>'
    for case in suite['cases']:
        cases+='<div class="case"><div class="casehead"><h3>'+esc(case['id']+' - '+case['title'])+'</h3><p>'+esc('MUST | '+','.join(case['requirements'])+' | '+case['injection_mode']+' | '+case['hardware_scope'])+'</p><p>Initial words: '+esc(fmt(case['initial_words']))+'</p></div>'+table(['Step','Apply','Duration','Expected'],step_rows(case['steps']))+'<p>Retest result: __________ Operator/date: __________________ Evidence: __________________</p></div>'
    cases+='<h2>4. Full-trace acceptance oracles</h2>'+''.join('<h3>'+esc(rel['id']+' - '+rel['kind'])+'</h3><p>'+esc(rel['definition'])+'</p>' for rel in suite['relationship_invariants'])
    cases+='<h2>5. Validation scope</h2><p>Local static and full-scan checks passed; independent mutation checks are recorded in S3 review. Full upstream tool tests still contain5 legacy expectation mismatches documented separately. ADC/DAC and UART are external images in local simulation. Electrical types,voltage/current,real plant performance,power-loss retention and full manufacturer compilation remain unverified. V002 hardware tests have not run. This candidate is not a final production release.</p>'
    # Use the skill's same-source annotated parser, independently cross-check sequence.
    path=SKILL/'resources/tools/gen_il_md.py'
    spec=importlib.util.spec_from_file_location('skill_gen_il_md',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    meta,sections=module.parse_fxil_annotated((CASE/'source.fxil').read_text(encoding='utf-8'))
    rows=[(m,ops,cmt) for section in sections for m,ops,cmt in section['rows']]
    _,parsed,_=parse_fxil(CASE/'source.fxil')
    assert [(m,ops) for m,ops,_ in rows]==[(x['mnemonic'],x['operands']) for x in parsed]
    assert rows[-1][0]=='END'
    annotated='<h2>1. Implementation and interpretation</h2><p>The tables below are generated from the same source.fxil as MAIN.csv. Step means instruction ordinal,not manufacturer memory-word address. Every instruction and final END are included. Edit source then regenerate; never edit generated tables.</p>'
    md=['# L01S Water PI - Annotated Instruction List','',f'Version V002; instruction count {len(rows)}; source SHA256 {report["source_sha256"]}.','']
    ordinal=0
    for index,section in enumerate(sections,2):
        annotated+='<h2>'+esc(str(index)+'. '+section['title'])+'</h2><p>'+esc(' '.join(section['notes']))+'</p>'
        data=[];md+=['## '+section['title'],'',' | Step | Instruction | Operands | Comment |',' | --- | --- | --- | --- |']
        for mnemonic,operands,comment in section['rows']:
            ordinal+=1;data.append([ordinal,mnemonic,' '.join(operands),comment]);md.append(f' | {ordinal} | {mnemonic} | {" ".join(operands)} | {comment} |')
        annotated+=table(['Step','Instruction','Operands','Comment'],data);md.append('')
    (DOC/'L01S-Water-PI-il-annotated_EN.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    pdfs=[print_pdf('Blackbox-Test-Cases_EN','Independent tests, setup and register map',banner+hashes+cases),print_pdf('L01S-Water-PI-il-annotated_EN','Annotated instruction list',banner+hashes+annotated)]
    lab=CASE/'lab-tests';lab.mkdir(exist_ok=True)
    for name in ('MAIN.csv','COMMENT.csv'):shutil.copy2(OUT/name,lab/name)
    archive=CASE/'versions/V002';archive.mkdir(parents=True,exist_ok=True)
    for name in ('source.fxil','MAIN.csv','COMMENT.csv','build_identity.json'):shutil.copy2(OUT/name,archive/name)
    shutil.copy2(DOC/'L01S-Water-PI-il-annotated_EN.md',archive/'L01S-Water-PI-il-annotated_EN.md')
    (CASE/'evidence/pdf-build.json').write_text(json.dumps({'pdfs':pdfs,'instruction_count':ordinal,'generator_sha256':digest(path),'profiles_cleanup':'TemporaryDirectory context completed'},indent=2),encoding='utf-8')
    print(json.dumps({'pdfs':pdfs,'candidate':str(OUT),'status':'pending independent PDF visual review'},indent=2))


if __name__=='__main__': main()
