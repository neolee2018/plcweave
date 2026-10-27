"""Install the repository workflow as a priority revision of the legacy skill."""
import argparse
import shutil
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',required=True,type=Path)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    target=args.target.resolve()
    entry=target/'SKILL.md'
    original=entry.read_text(encoding='utf-8')
    backup=repo/'local/skill-backup/20261022'
    paths=['SKILL.md','resources/sop/PLC-TDD-V2.0-工作流.md',
           'resources/sop/L01S-开发标准流程.md','resources/templates/tdd/test-case-format.md']
    for name in paths:
        src=target/name;dest=backup/name
        if src.exists() and not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    source=repo/'skills/plc-program-development'
    body=(source/'SKILL.md').read_text(encoding='utf-8').split('---',2)[2].lstrip()
    ref=target/'resources/sop/PLC-MD-First-Workflow.md'
    ref.write_text(body,encoding='utf-8')
    docs=target/'resources/sop/references';docs.mkdir(exist_ok=True)
    for name in ('markdown-cases.md','s6-hil-v2.md','two-phase-workflow.md'):
        shutil.copy2(source/'references'/name,docs/name)
    marker='<!-- PLCWEAVE-MD-FIRST -->'
    note='''<!-- PLCWEAVE-MD-FIRST -->
## 2026-10-26 用户修订：当前工作流入口

**优先遵循 [MD优先工作流](resources/sop/PLC-MD-First-Workflow.md)及[两阶段入口](resources/sop/references/two-phase-workflow.md)**：用户只改需求，AI维护设计、独立用例及共用控制核心；第一阶段交付HIL/正式版两份指令表，第二阶段用户厂家编译下载后受控测试并迭代。复核节点使用4个独立上下文Agent（主Agent不计入）；每客户独立目录，默认project/下；最终在项目内建立delivery版本文件夹并ZIP打包。台达适配未实现，不把本地或测试版结果升级成正式硬件验收。

后文及旧SOP中的test_cases.json/YAML、project.yaml、旧目录约定仅保留为历史兼容，不再要求新项目生成这些并行作者文件。必要运行报告/轨迹仍可用机器格式。历史冻结文件不改写。正式交付CSV/PDF仍按适用要求生成。

<!-- /PLCWEAVE-MD-FIRST -->

'''
    if marker in original:
        start=original.index(marker);end=original.index('<!-- /PLCWEAVE-MD-FIRST -->',start)+len('<!-- /PLCWEAVE-MD-FIRST -->')
        original=original[:start]+original[end:].lstrip('\n')
    heading=original.index('\n# ')
    insert=original.index('\n',heading+1)+1
    entry.write_text(original[:insert]+'\n'+note+original[insert:].lstrip('\n'),encoding='utf-8')
    for name in paths[1:]:
        path=target/name
        if not path.exists():continue
        text=path.read_text(encoding='utf-8')
        link='PLC-MD-First-Workflow.md' if '/sop/' in name else '../../sop/PLC-MD-First-Workflow.md'
        banner=f'> 2026-10-22用户修订优先：新项目初版需求/测试只MD，4个独立Agent复核，客户目录project/或用户指定位置，最终交付目录+ZIP。当前规范见[MD优先工作流]({link})。本文JSON/YAML格式仅作历史兼容。\n\n'
        if not text.startswith('> 2026-10-22用户修订优先：'):path.write_text(banner+text,encoding='utf-8')
    print('Installed MD-first workflow; original skill preserved in local/skill-backup/20261022')


if __name__=='__main__':main()
