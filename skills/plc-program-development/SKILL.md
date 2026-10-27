---
name: plc-program-development
description: 用PLCWeave进行需求驱动的PLC设计、独立测试、双版本指令表交付及人工下载后的HIL闭环。当前执行子集面向FX3U/HBDTECH L01S，客户项目独立存放，节点由4名独立Agent复核。
---

# PLC 开发与交付

## 两阶段入口（2026-10-26）

- 客户定制按[两阶段工作流](references/two-phase-workflow.md)执行。用户只提供或修改requirements.md；AI维护资源分配、design.md、独立test_cases.md、共用source.fxil及后续全部成果。
- 第一阶段使用 `workflow init/freeze/build/deliver --stage 1`：完成设计、用例、编程、两版检查与规定复核后，交付需求、设计、测试、程序四类成果；程序必须有HIL测试版与去除测试接口的正式版，二者由同一控制核心生成。
- 第二阶段由用户在厂家软件编译下载HIL版并明确确认RUN后，AI `workflow confirm-download/test`，保存PLC实际返回数据并与冻结预期比较。程序缺陷须同步更新两版，用新build经用户重新编译下载再测；单一最终版本的全部规定用例通过、清理确认和独立复核后，`workflow deliver --stage 2`。
- 新CLI仅覆盖受支持FX子集与L01S稳态采样，跨品牌和其他验证范围见上述参考；不凭两版仿真或测试版HIL升级正式版硬件结论。需求变化用 `workflow revise`保留旧MD快照及证据，AI实际修订后再走冻结与交付。

## 项目存放

- 工具仓库仅维护技能、工具链、工具测试、依赖及其说明；客户需求、程序、资料、运行证据和交付文件全部放在客户项目目录。
- 用户未指定目录时，创建 `<工具仓库>/project/<项目名称>/`；每个项目独立建目录，重名时停止并选择新名称，不能合并或覆盖既有项目。
- 用户指定项目目录时遵从该位置；若位于本工具仓库内，仍必须在 `project/` 下。不得把客户文件放进 `src/`、`tests/`、`docs/`、技能目录或历史 `private/`。
- `project/` 中的客户内容默认被公共Git忽略；可按项目另行建立私有版本库。公共仓库不分发客户程序、厂商资料或凭据。

## 演示入口（克隆后首次）

- 用户粘贴根目录 `PROMPT.md` 或 `demo/PROMPT.md` 时，先读 `demo/START-HERE.md`，按其中模式A/B执行。模式A无硬件全自动，使用可用新名称，不询问项目名或连接状态；用户明确接硬件时模式B才收集缺失的连接信息。演示是固定场景（启停+3秒延时），不冒充双程序客户定制；真实项目另建目录走两阶段入口。
- 串口参数要同时写入程序（L01S 的 `D8120/D8121`）和 `bench_config.json`，不能让程序与台架各一套。`MAIN.csv`/`COMMENT.csv` 按 GX Works2 列表导出方言（引号制表符、CRLF）生成，但厂商导入/编译仍由现场确认，工具不提供验证过的下载器。
- 客户明确确认“已烧录并 RUN”，且记录操作者、GX Works2 版本、编译结果和 RUN 状态之前，不运行 `hil`、不写设备、不生成 `manual_download.json`。
- S6 前还要确认 **PLC 已 RUN、USB-RS485 已接、现场为隔离空机**，用 `demo confirm-bench` 记录；演示项目缺少 `bench_ready.json` 时 `hil` 拒绝执行。未接 PLC/485 时保持 UNVERIFIED。
- 交付用 `plcweave demo deliver`：ZIP 至少含需求、用例、`MAIN.csv`、`COMMENT.csv`、HIL 报告、总结报告，另附 MANIFEST 和源文件；完成度与验收结论由工具按证据生成，不手工拔高。正式验收只依据导入的 S6 报告字段，不独立证明电气/带载。

## Markdown 优先

- 需求与测试唯一可编辑作者源分别为 `requirements.md` 和 `test_cases.md`；新两阶段工程另有AI维护的 `design.md`。用户只改需求，AI独立更新设计和测试，不要求用户同步编辑多份文件。均用Markdown，不建立同义作者副本。
- 不提前生成需求/测试的JSON、YAML、CSV、HTML或PDF副本，不维护两套正确答案。
- 可执行用例使用MD内的表格；执行时直接解析到内存模型，不生成 `test_cases.json`。格式见 [Markdown用例规范](references/markdown-cases.md)。复杂关系可放在同一MD的结构块中，仍只有这份MD权威源。
- S1完成后以 `s1-freeze.md` 记录两份MD的SHA256。初次冻结必须先于新PLC源；S2不得更改冻结预期。规格确需改变时，独立记录修订原因、影响和新版本，不覆盖旧冻结。
- 历史JSON案例与历史证据仅作兼容读取和归档；不得为了这次目录整理改写历史冻结文件或伪造新的验证结果。

## S0–S7

1. **S0**：在项目中写MD需求，确认机型、映射、功能、现场授权和验收范围。先确认本地/串口/电气测量的能力边界。
2. **S1**：独立设计MD用例，覆盖正常、边界、故障、恢复及有关不变量，再冻结。
3. **S2**：依据冻结需求/测试编写 `source.fxil`，生成所需CSV并运行真实指令解释器。未知指令或地址明确阻断，不能NOP化。
4. **S3**：实际执行并比较轨迹；复核按下节的4 Agent执行。数据不全不判PASS；主Agent不能凭读源码代替独立复核。
5. **S4**：完成第一阶段独立复核与交付，包含需求、设计、用例、两版指令表/说明及本地验证证据；草稿保持MD，额外排版按用户需要生成。
6. **S5/S6**：按用户选定的厂家通路/人工烧录/PlatformIO编排执行。没有经过验证的下载器就明确保留人工下载，不改写原厂固件。写入、RUN/STOP和设备动作须有现场授权与已知映射。S6 硬件在环方法见 [S6-HIL-V2](references/s6-hil-v2.md)：默认 L01S 档案，先绑定镜像身份再写入，只写程序只读的注入寄存器，轮询只证明稳态标量。
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
- 双程序工程按上述两阶段交付规范：需求、设计、测试用例，以及HIL/正式版各自的指令表、注释与程序说明，附同版证据。PDF按用户明确格式额外生成，不再把旧“单程序+双PDF四件套”当作默认交付。
- 交付附文件哈希清单（工具生成的MANIFEST.md可随包，属于清单而非编辑源），核验ZIP可读且内容一致；不覆盖既有版本。客户另有明确格式时优先遵从。
- 演示交付可用 `plcweave demo deliver`：至少含 `requirements.md`、`test_cases.md`、`MAIN.csv`、`COMMENT.csv`、`HIL-REPORT.md`、`SUMMARY.md`，另附 `MANIFEST.md`。总结报告必须写清完成度、演示验收/正式验收的区别及未测试项。
- 交付只收纳本项目明确选定的成果，禁止自动打包整个工具仓库、环境、凭据或其他客户目录。

## 当前CLI

在工具仓库根使用自动配置本仓环境的PowerShell入口（或使用已安装的 `plcweave` 命令；源码直接用python时先设置PYTHONPATH=src）：

```powershell
./tools/plcweave.ps1 init 客户项目名
./tools/plcweave.ps1 init 客户项目名 --directory F:/客户指定路径/项目
./tools/plcweave.ps1 freeze project/客户项目名
./tools/plcweave.ps1 simulate project/客户项目名
./tools/plcweave.ps1 package project/客户项目名 --version V001 --file 实验室测试/MAIN.csv --file 实验室测试/COMMENT.csv --file Doc/Blackbox-Test-Cases_EN.pdf --file Doc/项目-il-annotated_EN.pdf
./tools/plcweave.ps1 demo start 演示项目 --port COM7 --baud 9600 --parity N --station 1
./tools/plcweave.ps1 demo status project/演示项目
./tools/plcweave.ps1 demo confirm-flash project/演示项目 --operator 姓名 --software "GX Works2 1.77F" --compile-status "客户报告零错误" --run-state RUN
./tools/plcweave.ps1 demo confirm-bench project/演示项目 --operator 姓名 --isolated-bench --rs485-connected --plc-running
./tools/plcweave.ps1 demo deliver project/演示项目 --version V001
```

新建目录只有MD草稿，没有PLC程序或测试JSON。用例尚未完整、尚未冻结时执行应阻断。运行报告/轨迹可以使用JSON/CSV等机器格式；“初版只存MD”约束作者源，不禁止必要的真实执行证据。
