---
name: plc-program-development
description: >-
  必须使用：凡是编写、修改、调试、仿真、测试或交付PLC程序（三菱FX3U/FX系列、HBDTECH L01S、梯形图/指令表、GX Works2 CSV）的任务，开始前先加载本技能并按S0–S7执行。
  Use for ANY task that writes, modifies, debugs, simulates, tests or delivers a PLC program (Mitsubishi FX3U/FX, HBDTECH L01S, ladder or instruction list, GX Works2 CSV) with PLCWeave: Markdown requirements and test cases first, freeze before source, real simulation, independent review, project-local delivery ZIP.
---

# PLC 开发与交付

## 项目存放

- 工具仓库仅维护技能、工具链、工具测试、依赖及其说明；客户需求、程序、资料、运行证据和交付文件全部放在客户项目目录。
- 用户未指定目录时，创建 `<工具仓库>/project/<项目名称>/`；每个项目独立建目录，重名时停止并选择新名称，不能合并或覆盖既有项目。
- 用户指定项目目录时遵从该位置；若位于本工具仓库内，仍必须在 `project/` 下。不得把客户文件放进 `src/`、`tests/`、`docs/`、技能目录或历史 `private/`。
- `project/` 中的客户内容默认被公共Git忽略；可按项目另行建立私有版本库。公共仓库不分发客户程序、厂商资料或凭据。

## Markdown 优先

- 第一版只写 `requirements.md` 和 `test_cases.md`：用Markdown描述需求、初态、输入、预期、时序/容差、清理和验证层级。
- 不提前生成需求/测试的JSON、YAML、CSV、HTML或PDF副本，不维护两套正确答案。
- 可执行用例使用MD内的表格；执行时直接解析到内存模型，不生成 `test_cases.json`。格式见 [Markdown用例规范](references/markdown-cases.md)。复杂关系可放在同一MD的结构块中，仍只有这份MD权威源。
- S1完成后以 `s1-freeze.md` 记录两份MD的SHA256。初次冻结必须先于新PLC源；S2不得更改冻结预期。规格确需改变时，独立记录修订原因、影响和新版本，不覆盖旧冻结。
- 历史JSON案例与历史证据仅作兼容读取和归档；不得为了这次目录整理改写历史冻结文件或伪造新的验证结果。

## S0–S7

1. **S0**：在项目中写MD需求，确认机型、映射、功能、现场授权和验收范围。先确认本地/串口/电气测量的能力边界。
2. **S1**：独立设计MD用例，覆盖正常、边界、故障、恢复及有关不变量，再冻结。
3. **S2**：依据冻结需求/测试编写 `source.fxil`，生成所需CSV并运行真实指令解释器。未知指令或地址明确阻断，不能NOP化。
4. **S3**：实际执行并比较轨迹；复核按下节的4 Agent执行。数据不全不判PASS；主Agent不能凭读源码代替独立复核。
5. **S4**：形成可检查的候选；草稿阶段保持MD和机器执行证据，正式排版只在需要交付时生成。
6. **S5/S6**：按用户选定的厂家通路/人工烧录/PlatformIO编排执行。没有经过验证的下载器就明确保留人工下载，不改写原厂固件。写入、RUN/STOP和设备动作须有现场授权与已知映射。
7. **S7**：归因、必要回归、独立复核、最终交付与资源清理。程序、测试基础设施失败和证据不足分别处理。

## 需要复核的节点：4个独立Agent

- S1冻结、S3验证/重大修订、S6结果判定、最终交付等需要复核的节点，必须由 **4个独立上下文的Agent** 复核。主Agent只组织、汇总和修复，不计入4名复核者，不代写其结论。
- 为每名复核Agent创建全新上下文（支持时使用 `fork_turns="none"`）。只给任务、相关原始文件/冻结版本、独立验收标准和资源边界；不传主会话完整历史、预设结论或希望它通过的答案。
- 四个角色分别检查：①需求与测试覆盖/独立性；②程序、执行记录与判定；③工具、异常路径、身份门禁和资源清理；④项目隔离、文档、交付一致性与可复测性。每人独立作出结论，重叠检查关键风险。
- 并发额度不足时分批运行，仍须4名不同的独立Agent；不能用同一Agent换角色凑数。额度/工具失败记为“未完成复核”，不能写成PASS。
- 复核记录存入项目 `reviews/<节点>/`，保留reviewer、输入版本/哈希、实际检查、问题和结论（MD即可）。阻断问题修复后由相关复核Agent复查，不无故重复全部4轮。
- 未变更且版本/哈希相同的已复核材料可以引用既有结论；必须写清适用范围。新的冻结、程序或判定语义不继承不适用的旧结论。

## 测试范围与停止规则

- 本地快速回归保留。实机按变更影响选择用例和必要依赖；仅采集策略或排版变化不自动触发无关的全量PLC重跑。
- 保留PASS / PROGRAM_FAIL / TEST_INFRA_ERROR / UNVERIFIED。普通轮询不能证明每扫描轨迹、未测电气量或真实水压闭环；不通过放宽原容差追求PASS。
- 显然精度不足时记录缺口，停止无效重试。只有已证明的程序问题回S2；工具问题先修工具。

## 最终交付

- 必须先在客户项目内建立 `delivery/<版本>/`，再把该交付目录打成ZIP，放在项目的 `delivery/` 下。不能只返回分散文件或只给仓库路径。
- FX/L01S正式四件套：`MAIN.csv`、`COMMENT.csv`、测试/接线/完整寄存器表PDF、同源指令表详解PDF；适用限制和未验证项应明确。HTML/MD编辑源留在项目文档目录，不塞进四件套目录。
- 交付附文件哈希清单（工具生成的MANIFEST.md可随包，属于清单而非编辑源），核验ZIP可读且内容一致；不覆盖既有版本。客户另有明确格式时优先遵从。
- 交付只收纳本项目明确选定的成果，禁止自动打包整个工具仓库、环境、凭据或其他客户目录。

## 当前CLI

在工具仓库根使用自动配置本仓环境的PowerShell入口（或使用已安装的 `plcweave` 命令；源码直接用python时先设置PYTHONPATH=src）：

```powershell
./tools/plcweave.ps1 init 客户项目名
./tools/plcweave.ps1 init 客户项目名 --directory F:/客户指定路径/项目
./tools/plcweave.ps1 freeze project/客户项目名
./tools/plcweave.ps1 simulate project/客户项目名
./tools/plcweave.ps1 package project/客户项目名 --version V001 --file 实验室测试/MAIN.csv --file 实验室测试/COMMENT.csv --file Doc/Blackbox-Test-Cases_EN.pdf --file Doc/项目-il-annotated_EN.pdf
```

新建目录只有MD草稿，没有PLC程序或测试JSON。用例尚未完整、尚未冻结时执行应阻断。运行报告/轨迹可以使用JSON/CSV等机器格式；“初版只存MD”约束作者源，不禁止必要的真实执行证据。
