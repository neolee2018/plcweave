"""Build a scoped bench demonstration packet; preserve the historical candidate."""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from plcweave.testing import digest, frozen_suite

CASE=Path(__file__).resolve().parent
EVIDENCE=CASE/'evidence/hil02'
RUN='run02'
DOC=CASE/'Doc/bench-V002'
OUT=CASE/'delivery-docs/V002-bench-demo'
PACKET=CASE/'delivery/V002-bench-demo'
esc=lambda value:html.escape(str(value))


def fmt(value):
    if isinstance(value,dict):
        return ', '.join(f'{k}={fmt(v)}' for k,v in value.items()) or '-'
    if isinstance(value,list):return '['+', '.join(map(str,value))+']'
    return str(value)


def table(headings,rows,widths=None):
    columns='<colgroup>'+''.join(f'<col style="width:{w}%">' for w in widths)+'</colgroup>' if widths else ''
    return '<table>'+columns+'<thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headings)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def timing_rows(report):
    rows=[]
    for p in report['supplemental_procedures']:
        for event in ([p['timing']] if 'timing' in p else p.get('events',[])):
            interval=event.get('elapsed_ms')
            elapsed='['+', '.join(f'{x:.3f}' for x in interval)+']' if interval else 'Unobserved'
            rows.append([p['id']+' / '+event.get('id','first-full-frequency'),elapsed,fmt(event.get('expected_ms')),event['status']])
    return rows


def appendix(plan,report):
    actual={p['id']:p for p in report['supplemental_procedures']}
    counts=Counter(p['status'] for p in actual.values())
    content='<div class="page"><h2>6. V002 isolated-bench results - 22 October 2026</h2>'
    content+='<p>Manual download was confirmed by the user. PlatformIO executed the explicitly selected bench target; no automatic compiler/downloader is represented. This run used COM5 native CPU control and COM7 Modbus station 1 at 9600/8/N/1. No sensors, loads or actuators were connected.</p>'
    content+='<p><b>'+esc(fmt(dict(counts)))+'</b> across '+str(report['actual_executed_count'])+' separately frozen supplemental procedures. The original 55 scan-based cases remain hardware UNVERIFIED; none is upgraded by this table. Original local simulation: 55/55 cases and 10 relationship types passed across 92,996 scans.</p>'
    content+='<p>Every scalar decision requires two complete equal observations after settling and within its supplemental window. Exact phase-sensitive PI endpoints and full-scan invariants remain UNVERIFIED. Event timing includes request/response uncertainty; the complete elapsed interval must fit unchanged tolerances. Overlap is UNVERIFIED. The jitter waveform is UNVERIFIED even when recovery passes.</p>'
    content+=table(['Procedure','Source cases','Result'],[[p['id'],', '.join(p['source_case_ids']),p['status']] for p in actual.values()],[43,37,20])
    content+='<h3>Conservative event intervals (milliseconds)</h3>'+table(['Event','Elapsed interval','Acceptance interval','Result'],timing_rows(report),[40,23,22,15])
    content+='<p>Cleanup: '+esc(report['cleanup'])+'. Both serial connections were closed and the task lock removed. AO figures below are register observations; no terminal voltage/current measurement was performed.</p>'
    content+='<p class="hash">Source: '+report['source_sha256']+'<br>Tests: '+report['test_sha256']+'<br>Independent S6 plan: '+report['plan_sha256']+'<br>Raw trace: '+digest(EVIDENCE/RUN/'trace.jsonl')+'</p>'
    content+='<h3>Evidence and rerun contract</h3><p>The accompanying review packet contains S6-qualification-plan.json, its freeze, the raw trace, report and independent review. JSON key order is the required write order. Use a fresh evidence output directory for each rerun. Restart the real CPU with D261 seeded before STOP/RUN for every procedure except the preserved saturation plateau. Never write ADC, AO or unlisted scratch registers.</p></div>'
    content+='<div class="page"><h2>7. Frozen supplemental replay procedures</h2><p>These procedures were independently designed and frozen before the adapter implementation or any batch stimulus. They add steady and event observations; they do not amend original S1 checkpoints. Unless specified below, stop/disable output, establish zero state, set D190=1,D1056=0,D261=60, apply initial words, STOP/RUN, restore original CPU flags, and verify version/heartbeat. After each write, confirm the accepted value by readback. D102 is immediately clamped to 10..160. Steady observations settle for 200ms and require two complete samples within the stated hold window. Listed stable expectations are independently classified in the frozen plan.</p>'
    for p in plan['supplemental_procedures']:
        content+='<h3>'+esc(p['id'])+'</h3><p>Source cases: '+esc(', '.join(p['source_case_ids']))+'. '+esc(p['scope'])+'</p><p>Initial words: '+esc(fmt(p.get('initial_words',{})))+'</p>'
        if p.get('params'):
            content+=table(['Parameter','Frozen value'],[[k,fmt(v)] for k,v in p['params'].items()],[31,69])
        if p.get('steps'):
            content+=table(['Step','Apply in listed order','Hold ms','Stable expected values'],[[i+1,fmt(s['write']),s['hold_ms'],fmt(s['expect'])] for i,s in enumerate(p['steps'])],[6,25,10,59])
        if p.get('events'):
            content+=table(['Event / apply','Effective predicate','Transition / interval ms','Post-event expected'],[[e['id']+' / '+fmt(e['write']),fmt(e['effective_trigger']),f"{e['device']} {e['from']} to {e['to']}; "+fmt(e['expected_ms']),fmt(e.get('post_event_expect',{}))] for e in p['events']],[26,20,28,26])
        if p.get('expect'):content+='<p>Final stable expected: '+esc(fmt(p['expect']))+'</p>'
        content+='<p>Independent retest: __________ Operator/date: __________________ Evidence: __________________</p>'
    content+='</div>'
    return content


def find_edge():
    for base in (os.environ.get('PROGRAMFILES(X86)'),os.environ.get('PROGRAMFILES'),os.environ.get('LOCALAPPDATA')):
        if base and (Path(base)/'Microsoft/Edge/Application/msedge.exe').exists():return Path(base)/'Microsoft/Edge/Application/msedge.exe'
    found=shutil.which('msedge')
    if found:return Path(found)
    raise FileNotFoundError('msedge.exe not found in standard locations')

def render(name,source,title):
    import pymupdf
    htmlpath=DOC/(name+'.html');target=OUT/(name+'.pdf')
    htmlpath.write_text(source,encoding='utf-8')
    edge=find_edge()
    with tempfile.TemporaryDirectory(prefix='bench-pdf-profile-',dir=EVIDENCE) as profile:
        r=subprocess.run([str(edge),'--headless=new','--disable-gpu','--disable-extensions','--no-pdf-header-footer',f'--user-data-dir={profile}',f'--print-to-pdf={target.resolve()}',htmlpath.resolve().as_uri()],capture_output=True,timeout=45)
        if r.returncode or not target.exists():raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-700:])
    temp=target.with_suffix('.metadata.pdf')
    with pymupdf.open(target) as pdf:
        pdf.set_metadata(dict(title=title,author='HBDTECH',subject='V002 scoped isolated-bench demonstration; full hardware acceptance unverified',creator='PLCWeave'))
        for i,page in enumerate(pdf):page.insert_text((page.rect.width-70,page.rect.height-22),f'{i+1} / {len(pdf)}',fontsize=8,color=(.35,.4,.45))
        pdf.save(temp)
    temp.replace(target)
    qa=EVIDENCE/'pdfqa'/name;qa.mkdir(parents=True,exist_ok=True)
    with pymupdf.open(target) as pdf:
        text=''.join(p.get_text() for p in pdf)
        assert 'UNVERIFIED' in text and 'HBDTECH' in text
        assert 'V002 hardware tests have not run' not in text
        for i,p in enumerate(pdf):p.get_pixmap(dpi=100).save(qa/f'page-{i+1:03d}.png')
        return dict(name=target.name,pages=len(pdf),sha256=digest(target))


def write_chinese_report(report,review):
    counts=Counter(p['status'] for p in report['supplemental_procedures'])
    rows='\n'.join('| '+p['id']+' | '+p['status']+' |' for p in report['supplemental_procedures'])
    timing='\n'.join('| '+' | '.join(map(str,row))+' |' for row in timing_rows(report))
    text=f'''# L01S 供水 PI V002 台架演示与验证报告

生成：{datetime.now(timezone.utc).isoformat()}。机型：HBDTECH L01S-16M-4AD2DA（4AI/2AO）。

## 本次结论

已使用用户烧录的 V002，在空机隔离台架上由 PlatformIO 执行完整28项冻结补充程序：{dict(counts)}。
PLC程序没有改版；没有已证明的程序失败。采样结果与原始事务经独立复算，{review['decision']}。
这是可复演的寄存器台架案例；原55项完整扫描用例的硬件结论仍为 UNVERIFIED，电气、带载水压闭环、掉电保持及单扫描瞬态也未验收。没有发布为 V1 或宣称完整 HARDWARE_PASS。

## 测试先于程序的证据

- S0先冻结需求；独立S1冻结55项MUST和10类关系断言。
- 私有Git快照 fa673fe / S1-STD-002-FROZEN 时间2026-10-22 13:51:28 +08，当时快照不含PLC源。
- 新PLC源首次创建2026-10-22 13:53:39 +08；独立S2依据冻结需求和用例编程。
- 独立S3完整解释执行176条指令、92,996个扫描，55/55用例、10类关系通过；7类语义故障变体被捕获。CLI及PlatformIO仿真入口通过。
- 本轮S6采样规则和无硬件测试也先冻结、先记录失败，再实现采样器。第一次实机run01为24PASS/4UNVERIFIED；独立复核发现积分截止采样只读两次，第二次已经30000但缺一次稳定确认。追加独立采集策略和失败测试后，改为截止时间内连续读取，仍严格要求最后两次完整到顶确认都不跨截止线。run02第一次到顶响应约50196.377ms，第二次50226.220ms跨过50200ms，因此截止断言仍UNVERIFIED，没有追逐PASS或扩大容差。run01原始报告、执行器和轨迹完整保留，最终run02重新执行全部28项。
- PLC源、原测试、预期值和所有时序容差始终未改。普通串口轮询不替代原每扫描关系验证。

## 实机范围与结果

COM5用于已授权真实STOP/RUN及身份核验；COM7为Modbus RTU，站号1，9600/8/N/1。每次写指定输入后回读确认；禁止写ADC、AO及未知映射。
已核对D196=2、D197=31、D200=28642、D201=27104、D202=2及变化心跳。该指纹用于版本关联，不能替代二进制回读。
范围覆盖初始化、保存设定值校验、压力标定、启停优先级、非法模式重启抑制、满频/积分限幅、输出使能路由、休眠/唤醒及抖动后的恢复。

| 补充程序 | 判定 |
| --- | --- |
{rows}

计时使用保守区间，整个区间落入原容差才通过；与边界重叠保留UNVERIFIED，不扩大容差，也不据此指认程序早动作。

| 事件 | 实测区间ms | 容差ms | 判定 |
| --- | --- | --- | --- |
{timing}

AO0的4000及AO1的0是寄存器回读，没有测量端子电压或电流。PLC没有连接传感器或执行设备，未验证真实水压。

## 复演方法

当前硬件已烧录V002，运行本仓现有工具环境，不需要再次下载或打开GX Works2。此任务未发现经过验证的L01S自动应用下载器，PlatformIO负责仿真和测试编排；upload仍明确阻断。

在案例目录的platformio.ini中，将custom_hil_output设为未存在的新编号（如run03），然后执行PlatformIO的bench目标。证据目录不可覆盖；默认目标仍是simulate。只允许在本次已确认无传感器/执行器的测试台复演。PlatformIO显示SUCCESS表示任务完成，完整硬件结论仍以报告中的UNVERIFIED和逐项状态为准。

手动寄存器演示可按顺序操作：

1. D192=1、D191=0、D193=0，确认停止和输出0。
2. D190=1、D102=60、D1056=1250（5.0bar），再D192=0、D191=1；观察M0=1。
3. D1056=1450（5.8bar）持续保持，观察M10预休眠、随后M11休眠。
4. D1056=1275（5.1bar）持续保持，观察重新唤醒。人工观察不用于精确时序验收。
5. 若演示满频，将D1056=0保持约51秒；观察D154=5000（50Hz）、D120=30000。仅在空机测试台将D193=1时，Y0=1且D8050=4000；D193改0则路由关闭。
6. 结束写D192=1、D191=0、D193=0，回读M0/M10/M11/D120/D154/Y0/D8050/D8051全部0。

four-piece-set文件夹含MAIN.csv、COMMENT.csv和两份英文PDF；测试PDF包含完整寄存器表、原55用例和28项补充程序操作表。Doc保留可编辑HTML/Markdown，evidence保留两轮原始记录、独立复核、失败测试及冻结哈希。
压缩包是案例与证据包；自动复演依赖本仓已安装的PLCWeave环境，并非独立Windows安装器。

## 清理、限制与版本绑定

最终状态：{report['cleanup']}。CPU RUN，M8035/M8036/M8037恢复原值；应用停止，D193=0，输出寄存器与Y0为0。串口关闭：{report['serial_closed']}；任务锁移除：{report['serial_lock_removed']}。
S5按用户不使用GX Works2的要求未执行。未声称厂家编译或导入实测通过；CSV格式检查通过和用户手工烧录是独立事实。历史上游扩大测试仍有5项旧预期差异，原记录保留，不称上游全绿。

源SHA256：`{report['source_sha256']}`

原测试SHA256：`{report['test_sha256']}`

S6冻结计划SHA256：`{report['plan_sha256']}`

原始run02报告SHA256：`{digest(EVIDENCE/RUN/'report.json')}`

原始run02轨迹SHA256：`{digest(EVIDENCE/RUN/'trace.jsonl')}`
'''
    (DOC/'Validation-Report_CN.md').write_text(text,encoding='utf-8')


def build():
    frozen_suite(CASE)
    report=json.loads((EVIDENCE/RUN/'report.json').read_text(encoding='utf-8'))
    review=json.loads((EVIDENCE/'S6-independent-hardware-review.json').read_text(encoding='utf-8'))
    assert report['actual_executed_count']==28 and report['serial_closed'] and report['serial_lock_removed']
    assert report['status']=='UNVERIFIED' and all(p['status'] not in {'PROGRAM_FAIL','TEST_INFRA_ERROR'} for p in report['supplemental_procedures'])
    assert review['decision']=='ACCEPT_SCOPED_BENCH_EVIDENCE'
    assert review['run']==RUN and review['sha256']['report']==digest(EVIDENCE/RUN/'report.json')
    assert review['sha256']['trace']==digest(EVIDENCE/RUN/'trace.jsonl')
    assert report['source_sha256']==digest(CASE/'source.fxil') and report['test_sha256']==digest(CASE/'test_cases.json')
    plan=json.loads((EVIDENCE/'S6-qualification-plan.json').read_text(encoding='utf-8'))
    DOC.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    for name in ['HMI-register-map.md','L01S-Water-PI-il-annotated_EN.md','S1-Test-Cases_EN.md']:
        shutil.copy2(CASE/'Doc'/name,DOC/name)
    write_chinese_report(report,review)
    for name in ['MAIN.csv','COMMENT.csv']:
        assert digest(CASE/'lab-tests'/name)==digest(CASE/'versions/V002'/name)
        shutil.copy2(CASE/'lab-tests'/name,OUT/name)
    counts=Counter(p['status'] for p in report['supplemental_procedures'])
    banner='<div class="banner"><b>V002 - ISOLATED BENCH DEMONSTRATION.</b><br>Local: 55/55 MUST cases passed. Bench supplements: '+esc(fmt(dict(counts)))+'. Original full-scan hardware suite and physical I/O: UNVERIFIED. Fixed-point PI; derivative zero.</div>'
    pdfs=[]
    for name in ['Blackbox-Test-Cases_EN','L01S-Water-PI-il-annotated_EN']:
        source=(CASE/'Doc'/(name+'.html')).read_text(encoding='utf-8')
        source=re.sub(r'<div class="banner">.*?</div>',lambda _:banner,source,count=1,flags=re.S)
        source=source.replace('Candidate V002</header>','V002 bench demo</header>')
        source=source.replace('V002 hardware tests have not run. This candidate is not a final production release.','Separately frozen V002 bench supplements have now been executed. See section 6 for qualified results; original scan-based assertions remain hardware UNVERIFIED. This demonstration is not a production release.')
        source=source.replace('V002 candidate - local logic verification only; new manual download required.','V002 bench demonstration - see scoped results; full hardware/electrical acceptance UNVERIFIED.')
        if name.startswith('Blackbox'):
            source=source.replace('<footer>',appendix(plan,report)+'<footer>')
        pdfs.append(render(name,source,name+' - V002 bench demonstration'))
    (EVIDENCE/'pdf-build.json').write_text(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),pdfs=pdfs),indent=2),encoding='utf-8')
    print(json.dumps(pdfs,indent=2))


def package():
    visual=json.loads((EVIDENCE/'pdf-visual-review.json').read_text(encoding='utf-8'))
    assert visual['status']=='PASS'
    for name,sha in visual['pdf_sha256'].items():assert digest(OUT/name)==sha
    PACKET.mkdir(parents=True,exist_ok=True)
    for directory in ['four-piece-set','Doc','evidence']: (PACKET/directory).mkdir(exist_ok=True)
    for p in OUT.iterdir():
        assert p.name in {'MAIN.csv','COMMENT.csv','Blackbox-Test-Cases_EN.pdf','L01S-Water-PI-il-annotated_EN.pdf'}
        shutil.copy2(p,PACKET/'four-piece-set'/p.name)
    for p in DOC.iterdir():shutil.copy2(p,PACKET/'Doc'/p.name)
    shutil.copy2(DOC/'Validation-Report_CN.md',PACKET/'README_CN.md')
    for name in ['source.fxil','requirements.md','test_cases.json','s1-freeze.json','s0-freeze.json','build_identity.json','register_map.csv','io_map.csv','manual_download.json','run_hil02.py','platformio.ini']:
        shutil.copy2(CASE/name,PACKET/name)
    for name in ['S6-qualification-plan.json','S6-qualification-plan.md','S6-qualification-freeze.json','S6-fixtures-red.json','S6-independent-implementation-review.json','S6-independent-fault-dryrun.json','S6-independent-capture-refinement-review.json','S6-independent-hardware-review.json','S6-independent-hardware-review.md','infrastructure-tests.json','toolchain-provenance.json','exit-read-only.json','exit-read-only-trace.jsonl','resource-cleanup.json','pdf-build.json','pdf-content-check.json','pdf-visual-review.json','pdf-visual-review.md']:
        shutil.copy2(EVIDENCE/name,PACKET/'evidence'/name)
    for run_name in ['run01',RUN]:
        directory=PACKET/'evidence'/run_name;directory.mkdir(exist_ok=True)
        for name in ['trace.jsonl','report.json','executor.py','S6-independent-hardware-review.json','S6-independent-hardware-review.md']:shutil.copy2(EVIDENCE/run_name/name,directory/name)
    for p in EVIDENCE.glob('S6-deadline-*'):shutil.copy2(p,PACKET/'evidence'/p.name)
    for name in ['S3-final-review.json','S3-full-trace-review.json','S3-final-cli.txt','S3-platformio-simulate.txt']:
        shutil.copy2(CASE/'evidence'/name,PACKET/'evidence'/name)
    for name in ['sampled.py','cpu_control.py','fx_serial.py']:
        shutil.copy2(CASE.parents[1]/'src/plcweave'/name,PACKET/'evidence'/name)
    shutil.copy2(CASE.parents[1]/'tools/pio-platform/builder/main.py',PACKET/'evidence/pio-main.py')
    fixtures=PACKET/'evidence/fixtures';fixtures.mkdir(exist_ok=True)
    for name in ['test_sampled_backend.py','test_cpu_v2_identity.py','test_saturation_deadline.py']:
        shutil.copy2(CASE.parents[1]/'tests'/name,fixtures/name)
    manifest=dict(version='V002-bench-demo',created_at=datetime.now(timezone.utc).isoformat(),release='SCOPED_DEMONSTRATION_ONLY',files={str(p.relative_to(PACKET)).replace('\\','/'):digest(p) for p in sorted(PACKET.rglob('*')) if p.is_file() and p.name!='manifest.json'})
    (PACKET/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=CASE/'L01S-Water-PI-V002-bench-demo.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(PACKET.rglob('*')):
            if p.is_file():z.write(p,Path('L01S-Water-PI-V002-bench-demo')/p.relative_to(PACKET))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    for path,sha in manifest['files'].items():assert digest(PACKET/path)==sha
    summary=dict(archive=str(archive),sha256=digest(archive),bytes=archive.stat().st_size,files=len(manifest['files']))
    (EVIDENCE/'delivery-manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    import sys
    package() if '--package' in sys.argv else build()
