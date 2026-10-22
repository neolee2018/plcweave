"""User-facing Markdown authoring, project isolation and delivery regressions."""
import hashlib
import zipfile
from pathlib import Path

import pytest

from plcweave.projects import create_project, package_delivery
from plcweave.markdown_suite import freeze_markdown
from plcweave.testing import frozen_suite, simulate


SUITE = '''# 测试用例

## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0 |

## Invariants
| device | expected |
| --- | --- |
| M0 | 0..1 |

## TC-001: RUN输出
### Initial
| device | value |
| --- | --- |
| D0 | 0 |

### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | M0=0..1 | M0=1 | 两个扫描 |
'''


def ready_case(tmp_path):
    path = create_project('客户甲', workspace=tmp_path)
    (path/'requirements.md').write_text('# 需求\nRUN时M0=1。\n', encoding='utf-8')
    (path/'test_cases.md').write_text(SUITE, encoding='utf-8')
    freeze_markdown(path)
    return path


def test_default_project_starts_with_markdown_only_and_refuses_reuse(tmp_path):
    path=create_project('客户甲', workspace=tmp_path)
    assert path==tmp_path/'project/客户甲'
    assert {p.suffix for p in path.iterdir() if p.is_file()}=={'.md'}
    assert not (path/'source.fxil').exists()
    with pytest.raises(FileExistsError):create_project('客户甲',workspace=tmp_path)


def test_customer_can_choose_external_folder_but_not_toolchain_folder(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    external=tmp_path/'客户指定'
    assert create_project('客户甲',workspace=repo,directory=external)==external
    with pytest.raises(ValueError):create_project('bad',workspace=repo,directory=repo/'src/customer')
    with pytest.raises(ValueError):create_project('../escape',workspace=repo)


def test_markdown_freeze_drives_actual_simulation_without_json_authoring(tmp_path):
    path=ready_case(tmp_path)
    suite=frozen_suite(path)
    assert suite['cases'][0]['steps'][0]['expect']=={'M0':1}
    assert suite['global_invariants']=={'M0':{'min':0,'max':1}}
    assert not list(path.glob('*.json'))
    (path/'source.fxil').write_text('#instructions\nLD M8000\nOUT M0\nEND\n',encoding='utf-8')
    report=simulate(path)
    assert report['status']=='SIM_PASS'
    assert report['test_sha256']==hashlib.sha256((path/'test_cases.md').read_bytes()).hexdigest()
    assert not (path/'test_cases.json').exists()


@pytest.mark.parametrize('name',['requirements.md','test_cases.md'])
def test_frozen_markdown_tamper_is_rejected(tmp_path,name):
    path=ready_case(tmp_path)
    with (path/name).open('a',encoding='utf-8') as f:f.write('\n改变后的内容\n')
    with pytest.raises(ValueError,match='Frozen'):frozen_suite(path)


def test_incomplete_markdown_and_unknown_columns_fail_closed(tmp_path):
    path=create_project('draft',workspace=tmp_path)
    with pytest.raises(ValueError):freeze_markdown(path)
    (path/'test_cases.md').write_text(SUITE.replace('duration_ms |','unexpected |'),encoding='utf-8')
    with pytest.raises(ValueError):freeze_markdown(path)
    assert not (path/'s1-freeze.md').exists()


def test_markdown_never_silently_falls_back_to_json(tmp_path):
    path=ready_case(tmp_path)
    (path/'test_cases.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='[Aa]mbiguous'):frozen_suite(path)


def test_freeze_does_not_overwrite_or_allow_program_before_initial_freeze(tmp_path):
    path=ready_case(tmp_path)
    with pytest.raises(FileExistsError):freeze_markdown(path)
    draft=create_project('late-tests',workspace=tmp_path)
    (draft/'test_cases.md').write_text(SUITE,encoding='utf-8')
    (draft/'source.fxil').write_text('END',encoding='utf-8')
    with pytest.raises(ValueError):freeze_markdown(draft)


def test_delivery_folder_zip_and_hashes_preserve_originals(tmp_path):
    case=ready_case(tmp_path)
    source=case/'MAIN.csv';source.write_bytes(b'PLC fixture')
    result=package_delivery(case,'V001',[source],workspace=tmp_path)
    assert result['folder']==case/'delivery/V001'
    assert result['archive'].is_file()
    assert (result['folder']/'MAIN.csv').read_bytes()==source.read_bytes()
    with zipfile.ZipFile(result['archive']) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert any(n.endswith('/MAIN.csv') for n in names)
        assert any(n.endswith('/MANIFEST.md') for n in names)
    with pytest.raises(FileExistsError):package_delivery(case,'V001',[source],workspace=tmp_path)


def test_delivery_cannot_include_external_files_or_escape_destination(tmp_path):
    case=ready_case(tmp_path);external=tmp_path/'secret.txt';external.write_text('outside')
    with pytest.raises(ValueError):package_delivery(case,'V001',[external],workspace=tmp_path)
    with pytest.raises(ValueError):package_delivery(case,'../escape',[],workspace=tmp_path)
    assert not (case/'delivery/V001').exists()


def test_new_markdown_v001_cannot_use_legacy_hardware_identity_fallback(tmp_path,monkeypatch):
    from plcweave import hil
    case=ready_case(tmp_path)
    constructed=[]
    monkeypatch.setattr(hil,'Bench',lambda *a,**k:constructed.append(True))
    with pytest.raises(ValueError,match='identity'):hil.candidate_bench(case)
    assert constructed==[]
