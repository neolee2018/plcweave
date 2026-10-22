"""Independent reviewer probes; authored under logs, no customer input changed."""
import json
from pathlib import Path
import pytest
from plcweave.markdown_suite import freeze_markdown, parse_markdown
from plcweave.testing import simulate

BASE = '''# Cases
## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0 |
## TC1: case
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 10 | - | - | M0=1 | check |
'''

def project(path, text):
    (path/'requirements.md').write_text('# Requirement\nM0 must be 1.',encoding='utf8')
    (path/'test_cases.md').write_text(text,encoding='utf8')
    return path

def test_empty_assertions_cannot_report_pass(tmp_path):
    path=project(tmp_path,BASE.replace('M0=1','-'))
    try:
        freeze_markdown(path)
    except ValueError:
        return
    (path/'source.fxil').write_text('#instructions\nLD M8000\nOUT M0\nEND\n',encoding='utf8')
    result=simulate(path)
    assert result['status'] != 'SIM_PASS', 'zero assertions produced SIM_PASS'

def test_imported_suite_unknown_step_assertion_rejected(tmp_path):
    legacy={'schema_version':1,'suite_version':'V001','scan_ms':10,'watch':['M0'],'global_invariants':{},'cases':[{'id':'TC1','initial_words':{},'steps':[{'duration_ms':10,'write':{},'invariant':{},'expect':{'M0':1},'must_not_happen':{'M0':1}}]}]}
    path=project(tmp_path,'# Cases\n```plcweave-suite\n'+json.dumps(legacy)+'\n```\n')
    try:
        freeze_markdown(path)
    except ValueError:
        return
    (path/'source.fxil').write_text('#instructions\nLD M8000\nOUT M0\nEND\n',encoding='utf8')
    result=simulate(path)
    assert result['status'] != 'SIM_PASS', 'unknown assertion ignored and SIM_PASS returned'

def test_duplicate_case_metadata_rejected(tmp_path):
    path=project(tmp_path,BASE.replace('### Steps','### Metadata\n| key | value |\n| --- | --- |\n| priority | MUST |\n| priority | SHOULD |\n### Steps'))
    with pytest.raises(ValueError):freeze_markdown(path)

def test_import_block_cannot_override_native_executable_tables(tmp_path):
    legacy={'schema_version':1,'suite_version':'V001','scan_ms':10,'watch':['M0'],'global_invariants':{},'cases':[{'id':'TC1','initial_words':{},'steps':[{'duration_ms':10,'write':{},'invariant':{},'expect':{'M0':1}}]}]}
    native=BASE.replace('M0=1','M0=0')
    path=project(tmp_path,native+'\n```plcweave-suite\n'+json.dumps(legacy)+'\n```\n')
    try:
        freeze_markdown(path)
    except ValueError:
        return
    (path/'source.fxil').write_text('#instructions\nLD M8000\nOUT M0\nEND\n',encoding='utf8')
    result=simulate(path)
    assert result['status'] != 'SIM_PASS', 'native M0=0 ignored because imported block overrides tables'

@pytest.mark.parametrize('version',[True,1.0])
def test_import_schema_type_is_explicit(tmp_path,version):
    legacy={'schema_version':version,'suite_version':'V001','scan_ms':10,'watch':['M0'],'global_invariants':{},'cases':[{'id':'TC1','initial_words':{},'steps':[{'duration_ms':10,'write':{},'invariant':{},'expect':{'M0':1}}]}]}
    path=project(tmp_path,'# Cases\n```plcweave-suite\n'+json.dumps(legacy)+'\n```\n')
    with pytest.raises(ValueError):freeze_markdown(path)

def test_import_duplicate_json_assertions_rejected(tmp_path):
    data='{"schema_version":1,"suite_version":"V001","scan_ms":10,"watch":["M0"],"global_invariants":{},"cases":[{"id":"TC1","initial_words":{},"steps":[{"duration_ms":10,"write":{},"invariant":{},"expect":{"M0":0},"expect":{"M0":1}}]}]}'
    path=project(tmp_path,'# Cases\n```plcweave-suite\n'+data+'\n```\n')
    with pytest.raises(ValueError):freeze_markdown(path)

def test_bit_input_does_not_silently_coerce_nonbinary_value(tmp_path):
    path=project(tmp_path,BASE.replace('M0','X0').replace('| 10 | - |','| 10 | X0=2 |'))
    with pytest.raises(ValueError):freeze_markdown(path)

