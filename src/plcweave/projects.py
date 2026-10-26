"""Keep customer files in independent projects; package explicit deliverables."""
import hashlib
import re
import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path


def _name(value):
    if not value or value!=value.strip() or value in {'.','..'} or re.search(r'[\x00-\x1f<>:"/\\|?*]',value) or value.endswith('.'):
        raise ValueError('Use a single valid project/version name')
    if value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        raise ValueError('Reserved Windows filename')
    return value


def _location(path, workspace):
    path=Path(path).resolve();workspace=Path(workspace).resolve()
    if path==workspace or (path.is_relative_to(workspace) and not path.is_relative_to(workspace/'project')):
        raise ValueError('Customer folders inside the toolchain must be under project/')
    if path==workspace/'project':raise ValueError('Each customer needs an independent subfolder')
    return path


def create_project(name, *, workspace=None, directory=None):
    workspace=Path(workspace or Path.cwd()).resolve();_name(name)
    default=workspace/'project'
    if directory is None and (default.resolve()!=default or (default/name).resolve()!=default/name):raise ValueError('Default project/ must not redirect outside the workspace')
    path=_location(directory if directory is not None else default/name,workspace)
    path.mkdir(parents=True,exist_ok=False)
    try:
        return _write_draft(path,name)
    except BaseException:
        # This invocation owns this newly created directory, never an existing one.
        if path.resolve()!=path or not path.is_relative_to(path.parent):raise ValueError('Invalid cleanup target')
        shutil.rmtree(path)
        raise


def _write_draft(path,name):
    (path/'requirements.md').write_text('# 用户需求\n\n## 目标与验收\n\n请填写需求、机型、I/O、启停、故障、时序和现场授权。\n',encoding='utf-8')
    (path/'test_cases.md').write_text('''# 测试用例草稿

先独立写清初态、输入、预期、时序、清理与验证层级，再冻结和编程。

## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0 |

## Invariants
| device | expected |
| --- | --- |

## TC-001: 请填写场景
### Initial
| device | value |
| --- | --- |

### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |

''',encoding='utf-8')
    (path/'README.md').write_text(f'# {name}\n\n需求：requirements.md；用例：test_cases.md。\nS1冻结前不创建PLC程序。正式交付存入delivery/<版本>/并打包ZIP。\n复核节点由4个独立上下文Agent复核，报告保存在项目内。\n',encoding='utf-8')
    return path


def package_delivery(directory, version, files, *, workspace=None):
    workspace=Path(workspace or Path.cwd()).resolve();_name(version)
    case=_location(directory,workspace)
    if not case.is_dir():raise ValueError('Project does not exist')
    inputs=[];names=set()
    entries=files.items() if isinstance(files,Mapping) else ((None,source) for source in files)
    for selected_name,source in entries:
        source=Path(source)
        if not source.is_absolute():source=case/source
        source=source.resolve()
        if not source.is_relative_to(case) or not source.is_file():raise ValueError('Deliverable must be a file inside this project')
        filename=source.name
        if selected_name is not None:
            relative=Path(selected_name)
            if relative.is_absolute() or relative.drive or '\\' in selected_name or relative.as_posix()!=selected_name:
                raise ValueError('Delivery member must be a canonical relative path')
            for part in relative.parts:_name(part)
            if not relative.parts:raise ValueError('Empty delivery member')
            filename=relative.as_posix()
        if filename.casefold() in names or filename.casefold()=='manifest.md':raise ValueError('Duplicate/reserved delivery filename')
        names.add(filename.casefold());inputs.append((source,filename))
    if not inputs:raise ValueError('Select actual deliverables before packaging')
    delivery=case/'delivery'
    if delivery.resolve()!=delivery:raise ValueError('Delivery destination must not redirect outside project')
    delivery.mkdir(exist_ok=True)
    target=delivery/version;archive=delivery/f'{case.name}-{version}.zip'
    if target.exists() or archive.exists():raise FileExistsError('Delivery version already exists')
    with tempfile.TemporaryDirectory(prefix='.package-',dir=delivery) as temporary:
        temporary=Path(temporary);folder=temporary/version;folder.mkdir()
        manifest=['# Delivery manifest','','| File | SHA256 |','| --- | --- |']
        for source,filename in inputs:
            dest=folder/filename;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            manifest.append(f'| {filename} | {hashlib.sha256(dest.read_bytes()).hexdigest()} |')
        (folder/'MANIFEST.md').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
        staged=temporary/'delivery.zip'
        with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob('*')):
                if p.is_file():z.write(p,Path(f'{case.name}-{version}')/p.relative_to(folder))
        with zipfile.ZipFile(staged) as z:
            if z.testzip():raise ValueError('Delivery archive integrity failed')
            for p in folder.rglob('*'):
                if p.is_file() and z.read((Path(f'{case.name}-{version}')/p.relative_to(folder)).as_posix())!=p.read_bytes():
                    raise ValueError('Delivery archive content differs from folder')
        folder.rename(target)
        try:staged.rename(archive)
        except BaseException:
            # Remove only the folder this invocation just published.
            if target.resolve()!=target or not target.is_relative_to(case):raise ValueError('Invalid cleanup target')
            shutil.rmtree(target)
            raise
    return {'folder':target,'archive':archive}
