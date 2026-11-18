"""Merge S6 v3 run reports into evidence/s6-v3/SUMMARY.md + summary.json."""
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent / 'evidence/s6-v3'
ORDER = {'PASS': 0, 'UNVERIFIED': 1, 'PROGRAM_FAIL': 2}


def load(run):
    path = BASE / run / 'report.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def case_status(case):
    steps = case['steps']
    asserted = [s for s in steps if s['compared'] or s['skipped']]
    skipped = sum(len(s['skipped']) for s in steps)
    ambiguous = sum(len(s.get('ambiguous', [])) for s in steps)
    if any(s['status'] == 'PROGRAM_FAIL' for s in steps):
        return 'PROGRAM_FAIL', skipped, ambiguous
    if asserted and all(s['status'] == 'PASS' for s in asserted) and skipped == 0 and ambiguous == 0:
        return 'PASS', skipped, ambiguous
    return 'UNVERIFIED', skipped, ambiguous


def main(runs):
    rows, writes, cleanup = {}, 0, {}
    for run in runs:
        report = load(run)
        if report is None:
            print('skip missing', run)
            continue
        writes += report.get('writes', 0)
        cleanup[run] = report.get('cleanup_state')
        for case in report['cases']:
            status, skipped, ambiguous = case_status(case)
            rows[case['id']] = {'run': run, 'id': case['id'], 'title': case.get('title', ''),
                                'status': status,
                                'compared': sum(len(s['compared']) for s in case['steps']),
                                'skipped': skipped, 'ambiguous': ambiguous}
    rows = list(rows.values())
    rows.sort(key=lambda r: (ORDER[r['status']], r['id']))
    counts = {k: sum(1 for r in rows if r['status'] == k) for k in ORDER}
    (BASE / 'summary.json').write_text(json.dumps({'cases': rows, 'counts': counts, 'writes': writes},
                                                  indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# S6 软元件注入批次结果（V002 实机）', '',
             '方法：写程序预留的注入寄存器（D190/D1056/D191/D192/D193/D102/D261/D194）→ 读输出软元件 → 与冻结 test_cases.json 逐项比对。',
             '',
             f'**{len(rows)} 项用例：PASS {counts["PASS"]}、UNVERIFIED {counts["UNVERIFIED"]}、PROGRAM_FAIL {counts["PROGRAM_FAIL"]}**；累计写入 {writes} 次。',
             '',
             '判定口径：',
             '- PASS = 全部断言被实机比对且相符，无跳过、无边界歧义。',
             '- UNVERIFIED = 已比对项相符，但存在主机轮询无法证明的瞬时值或定时器边沿歧义。',
             '- PROGRAM_FAIL = 稳定量（D100/D102/D260/D262/D190–D197/D202/D8120/D8121/M0 等）与冻结预期不符。',
             '',
             '| 用例 | 标题 | 判定 | 已比对 | 跳过 | 边界歧义 |', '|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f'| {r["id"]} | {r["title"][:36]} | {r["status"]} | {r["compared"]} | {r["skipped"]} | {r["ambiguous"]} |')
    lines += ['', '## 运行目录', '']
    for run in runs:
        if run in cleanup:
            lines.append(f'- {run}')
    lines += ['', '## 说明', '',
              '- run-v3-init：STD-001–010，真实 COM5 STOP/RUN 让 D261 首次扫描生效。',
              '- run-v3-init2：STD-001 复跑（快照补齐 D200–D202/M8196/M8125/D8120–D8121）。',
              '- run-v3-long / long2：长时序用例；long2 对定时器边沿歧义改判 UNVERIFIED。',
              '- run-v3-wrap：STD-049/055 计数器回绕，340 s 等待期间每 10 s 抽样检查不变量。',
              '- STD-017/018 未执行：实测写 D8030 会在 50 ms 内被 ADC 刷新覆盖（见 adc-probe 记录），需要 V003 程序钩子或真实模拟量源。']
    (BASE / 'SUMMARY.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(counts, ensure_ascii=False), 'cases', len(rows))


if __name__ == '__main__':
    main(sys.argv[1:] or ['run-v3-b', 'run-v3-c', 'run-v3-e', 'run-v3-init2', 'run-v3-init',
                          'run-v3-long', 'run-v3-long2', 'run-v3-wrap'])
