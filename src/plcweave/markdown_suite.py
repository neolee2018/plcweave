"""Read executable Markdown tables without generating a second test source."""
import json
import re
from pathlib import Path


def _number(text):
    if not re.fullmatch(r'-?\d+',text):raise ValueError(f'Expected integer: {text}')
    return int(text)


def _expected(text):
    if '..' in text:
        ends=text.split('..')
        if len(ends)!=2:raise ValueError('Invalid expectation range')
        low,high=map(_number,ends)
        if low>high:raise ValueError('Reversed expectation range')
        return {'min':low,'max':high}
    return _number(text)


def _device(text):
    if not re.fullmatch(r'[DMSXYTC]\d+',text):raise ValueError(f'Invalid device: {text}')
    return text


def _assignments(text, *, ranges=False):
    if text in {'','-'}:return {}
    values={}
    for item in text.split(';'):
        pair=item.strip().split('=')
        if len(pair)!=2:raise ValueError(f'Invalid assignment: {item}')
        name,value=map(str.strip,pair);_device(name)
        if name in values:raise ValueError(f'Duplicate device: {name}')
        values[name]=_expected(value) if ranges else _number(value)
    return values


def _validate_model(suite):
    """Every MD representation must satisfy the same executable contract."""
    from .validation import validate_suite
    allowed={'schema_version','suite_version','requirements','requirements_sha256','scan_ms','watch','global_invariants','relationship_invariants','oracle_contract','cases'}
    if not isinstance(suite,dict) or set(suite)-allowed:raise ValueError('Unsupported Markdown suite fields')
    from .validation import SCHEMA
    schema=suite.get('schema_version',1)
    if not (type(schema) is int and schema==1 or type(schema) is str and schema==SCHEMA):raise ValueError('Unsupported Markdown schema')
    if type(suite.get('scan_ms')) is not int or suite['scan_ms']<=0:raise ValueError('Invalid scan period')
    if not isinstance(suite.get('suite_version'),str) or not suite['suite_version'].strip():raise ValueError('Suite version required')
    watch=suite.get('watch')
    if not isinstance(watch,list) or not watch or any(not isinstance(x,str) for x in watch) or len(set(watch))!=len(watch):raise ValueError('Invalid watch list')
    for name in watch:_device(name)
    def values(data,ranges=False):
        if not isinstance(data,dict):raise ValueError('Device values must be a mapping')
        for name,value in data.items():
            _device(name)
            if type(value) is int:
                if not ranges and not name.startswith('D') and value not in {0,1}:raise ValueError('Bit input must be 0 or 1')
                continue
            if not ranges or not isinstance(value,dict) or not value or set(value)-{'min','max'} or any(type(v) is not int for v in value.values()):raise ValueError('Unsupported scalar expectation')
            if value.get('min',float('-inf'))>value.get('max',float('inf')):raise ValueError('Reversed expectation range')
        if ranges and not set(data)<=set(watch):raise ValueError('Assertion device is not watched')
    values(suite.get('global_invariants'),True)
    cases=suite.get('cases')
    if not isinstance(cases,list) or not cases:raise ValueError('No executable cases')
    ids=set()
    for case in cases:
        allowed_case={'id','title','priority','requirements','injection_mode','hardware_scope','initial_words','steps','expected_behavior_note'}
        if not isinstance(case,dict) or set(case)-allowed_case:raise ValueError('Unsupported case fields')
        identifier=case.get('id')
        if not isinstance(identifier,str) or not identifier or identifier in ids:raise ValueError('Invalid/duplicate case ID')
        ids.add(identifier)
        if case.get('priority','MUST') not in {'MUST','SHOULD'}:raise ValueError('Unsupported priority')
        values(case.get('initial_words'))
        steps=case.get('steps')
        if not isinstance(steps,list) or not steps:raise ValueError('Case has no steps')
        assertions=bool(suite['global_invariants'])
        for step in steps:
            if not isinstance(step,dict) or set(step)-{'duration_ms','write','invariant','expect','note'}:raise ValueError('Unsupported step fields')
            duration=step.get('duration_ms')
            if type(duration) is not int or duration<=0 or duration%suite['scan_ms']:raise ValueError('Invalid step duration')
            values(step.get('write'));values(step.get('invariant'),True);values(step.get('expect'),True)
            assertions=assertions or bool(step['invariant']) or bool(step['expect'])
        if not assertions and not suite.get('relationship_invariants'):raise ValueError('Case has no executable assertions')
    validate_suite(suite)
    return suite


def parse_markdown(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    # Lossless import of older rich suites stays in one MD source. New drafts
    # and ordinary cases use the readable tables below, not this import form.
    if '```plcweave-suite' in text:
        pattern=r'^```plcweave-suite[ \t]*\r?\n(.*?)^```[ \t]*$'
        blocks=re.findall(pattern,text,re.M|re.S)
        if len(blocks)!=1:raise ValueError('Exactly one imported suite block is required')
        outside=re.sub(pattern,'',text,flags=re.M|re.S)
        if any(line.lstrip().startswith('|') for line in outside.splitlines()):raise ValueError('Ambiguous imported block and Markdown tables')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate imported JSON key')
                result[key]=value
            return result
        result=json.loads(blocks[0],object_pairs_hook=unique)
        if not isinstance(result,dict):raise ValueError('Imported suite must be a mapping')
        return _validate_model(result)
    suite={'schema_version':1,'global_invariants':{},'cases':[]}
    section=None;case=None;header=None;meta={};seen=set()
    headings={'Suite':['key','value'],'Invariants':['device','expected'],
              'Initial':['device','value'],'Steps':['duration_ms','write','invariant','expect','note'],
              'Metadata':['key','value']}
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('## '):
            title=line[3:].strip();header=None
            match=re.fullmatch(r'([A-Za-z0-9_-]+):\s*(.+)',title)
            if match:
                identifier,title=match.groups()
                if identifier in seen:raise ValueError('Duplicate case ID')
                seen.add(identifier)
                case={'id':identifier,'title':title,'priority':'MUST','initial_words':{},'steps':[]}
                case_meta=set()
                suite['cases'].append(case);section=None
            elif title in {'Suite','Invariants'}:
                section=title;case=None
            else:raise ValueError(f'Unsupported Markdown section: {title}')
        elif line.startswith('### '):
            section=line[4:].strip();header=None
            if case is None or section not in {'Initial','Steps','Metadata'}:
                raise ValueError(f'Unsupported case section: {section}')
        elif line.startswith('|'):
            cells=[s.strip().strip('`') for s in line.strip('|').split('|')]
            if section not in headings:raise ValueError('Table outside executable section')
            if all(re.fullmatch(r':?-{3,}:?',s) for s in cells):continue
            if header is None:
                if cells!=headings[section]:raise ValueError(f'Unsupported {section} table columns')
                header=cells;continue
            if len(cells)!=len(header):raise ValueError('Markdown table column count differs')
            if section=='Suite':
                key,value=cells
                if key not in {'suite_version','scan_ms','watch'} or key in meta:raise ValueError(f'Unsupported/duplicate suite key: {key}')
                meta[key]=value
            elif section=='Invariants':
                name,value=cells;_device(name)
                if name in suite['global_invariants']:raise ValueError('Duplicate invariant')
                suite['global_invariants'][name]=_expected(value)
            elif section=='Initial':
                name,value=cells;_device(name)
                if name in case['initial_words']:raise ValueError('Duplicate initial device')
                case['initial_words'][name]=_number(value)
            elif section=='Metadata':
                key,value=cells
                if key not in {'priority','hardware_scope','injection_mode','requirements','expected_behavior_note'}:raise ValueError(f'Unsupported case key: {key}')
                if key in case_meta:raise ValueError('Duplicate case metadata')
                case_meta.add(key)
                case[key]=[v.strip() for v in value.split(',')] if key=='requirements' else value
            else:
                duration,write,invariant,expect,note=cells
                case['steps'].append({'duration_ms':_number(duration),'write':_assignments(write),
                                      'invariant':_assignments(invariant,ranges=True),
                                      'expect':_assignments(expect,ranges=True),'note':note})
    if set(meta)!={'suite_version','scan_ms','watch'}:raise ValueError('Draft suite metadata is incomplete')
    suite.update(suite_version=meta['suite_version'],scan_ms=_number(meta['scan_ms']),
                 watch=[_device(s.strip()) for s in meta['watch'].split(',')])
    if suite['scan_ms']<=0 or len(set(suite['watch']))!=len(suite['watch']):raise ValueError('Invalid scan period/watch list')
    if not suite['cases']:raise ValueError('Draft has no executable cases')
    for case in suite['cases']:
        if case['priority'] not in {'MUST','SHOULD'} or not case['steps']:raise ValueError('Case is incomplete')
        for step in case['steps']:
            if step['duration_ms']<=0 or step['duration_ms']%suite['scan_ms']:raise ValueError('Duration must be a positive scan multiple')
            if not set(step['expect'])|set(step['invariant']) <= set(suite['watch']):raise ValueError('Assertion device is not watched')
    if not set(suite['global_invariants'])<=set(suite['watch']):raise ValueError('Invariant device is not watched')
    return _validate_model(suite)


def freeze_markdown(directory):
    from .testing import digest
    from .validation import validate_suite
    directory=Path(directory);target=directory/'s1-freeze.md'
    if target.exists():raise FileExistsError('S1 freeze already exists; create a reviewed revision')
    if (directory/'source.fxil').exists():raise ValueError('Initial S1 freeze must precede PLC source')
    if (directory/'test_cases.json').exists():raise ValueError('Ambiguous test sources')
    suite=parse_markdown(directory/'test_cases.md');validate_suite(suite)
    rows=[(name,digest(directory/name)) for name in ['requirements.md','test_cases.md']]
    text='# S1 freeze\n\n| File | SHA256 |\n| --- | --- |\n'+''.join(f'| {name} | {sha} |\n' for name,sha in rows)
    created=False
    try:
        with target.open('x',encoding='utf-8') as stream:
            created=True
            stream.write(text)
    except BaseException:
        if created:target.unlink(missing_ok=True)
        raise
    return target


def read_freeze(directory):
    text=(Path(directory)/'s1-freeze.md').read_text(encoding='utf-8-sig')
    result={}
    for line in text.splitlines():
        if not line.startswith('|'):continue
        cells=[x.strip() for x in line.strip('|').split('|')]
        if cells==['File','SHA256'] or all(re.fullmatch(r':?-{3,}:?',s) for s in cells):continue
        if len(cells)!=2 or cells[0] not in {'requirements.md','test_cases.md'} or not re.fullmatch('[0-9a-f]{64}',cells[1]) or cells[0] in result:
            raise ValueError('Invalid Markdown freeze')
        result[cells[0]]=cells[1]
    if set(result)!={'requirements.md','test_cases.md'}:raise ValueError('Incomplete Markdown freeze')
    return result
