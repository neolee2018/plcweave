# PLCWeave Agent 指引

用途：测试驱动的PLC开发与验证工具链。技术栈：Python + Rust + Markdown + pytest（运行证据按需JSON/CSV）。

## 第一条规则：先加载技能（Codex / Claude Code / 其他Agent通用）

- 只要任务涉及编写、修改、调试、仿真、测试或交付PLC程序，**动手前必须完整阅读 `.agents/skills/plc-program-development/SKILL.md` 及其 `references/`**，并按其中S0–S7执行。不得跳过S0需求、S1冻结直接写 `source.fxil`。
- Codex会自动发现 `.agents/skills/`（也可在对话中输入 `$plc-program-development` 显式调用）；其他Agent没有自动发现时，按本条手动读取。
- 回复用户的第一步应说明当前所处阶段（S0–S7）和下一步需要的输入。

## 客户项目与技能（2026-10-22用户修订，优先于旧格式说明）

- 工作流技能入口：.agents/skills/plc-program-development/SKILL.md。
- 本仓除project/外只维护技能、工具链、工具测试、依赖和说明；客户程序、资料、需求、测试、证据和交付全部存入客户项目目录。
- 未指定目录时每项目新建project/<项目名>/；指定外部目录则遵从。仓库内的客户目录只能在project/下，不使用private/、src/或docs/存客户案例。客户内容默认不进入公共Git。
- 第一版requirements.md和test_cases.md为唯一作者源，不生成同义JSON/YAML/CSV/PDF；S1用s1-freeze.md冻结，执行内存解析MD。必要执行报告/轨迹格式不受此作者源限制。历史冻结JSON证据仅兼容读取，不为迁移改写。
- 需要复核的节点必须由4个不同的独立上下文Agent进行，主Agent不计入；传最少原始材料与验收条件，不传完整主会话或预设结论。额度不足分批运行，失败或缺席不得写成PASS；记录输入版本、实际检查、问题与结论。细则见技能。
- 最终交付必须在客户项目内建立delivery/<版本>/并打成ZIP，核验清单和压缩包，不只给散落文件，不覆盖已有版本。

## 项目状态与权威入口

- 2026-10-22 已整合首个FX执行子集、冻结用例比较、PlatformIO任务编排及受控HIL入口；不把其余蓝图计划写成已实现功能。
- 工作流与模块边界：docs/BLUEPRINT.md；阶段计划：docs/ROADMAP.md。
- 程序设计、测试设计、测试执行分别留证；S2不得自行更改冻结预期。
- 验证等级分别记录；未知/未实现指令必须明确阻断，不能NOP化。
- 不凭AI阅读源码声称仿真或硬件验证通过。

## 复用与授权

- 扫描执行核来自 vendor/gxwlib（上游 monozukuri-ai/gxwlib，MIT），厂家通路参考 Arienax/gxworks-agent（Apache-2.0）；来源与修改范围见 THIRD_PARTY_NOTICES.md 和 docs/RUNTIME-CHANGES.md。
- 合并任何代码、数据前先记录来源、commit、许可、哈希与修改范围，保留全部适用版权和第三方声明。
- 不将厂商软件、手册或客户资料随项目公开；不将内部凭据/公司记忆服务变成必需依赖。

## 开发和验证

- 当前CLI支持init/freeze/package/simulate/preflight/hil，具体可复现命令与验证记录见README；没有运行服务、没有已验证的自动下载器。
- 仿真与硬件后端共用用例模型和比较器，保留时间精度/采样质量差异。
- 未知映射不连接/写设备；程序下载、RUN/STOP和设备动作遵循现场授权及安全确认。
- 首版无监听端口；新增服务需先说明端口与用途。
- CLAUDE.md只是本文件指针；不要维护两套互相冲突的Agent规则。

## 可选：所在组织的内部工作区

- 若仓库上级目录存在组织自己的AGENTS.md、登记表或端口表，按其规则执行；它们不随本仓发布，开源用户没有也不需要。
- 任何内部服务、记忆库或凭据都不能成为本仓安装、测试或使用的必需依赖。

## 任务日志与资源释放

每次登记task_id、owner、时限与资源归属；记录开始、实际进展、结束/失败及cleanup结果。
用try/finally与超时路径回收本任务创建的进程、GUI临时工程、连接、串口、锁和临时文件。
保存成果后核验无残留；不按进程名全局清理，不关闭用户已有应用和共享权威服务。
logs/默认保留30天并忽略Git；业务成果与验证证据另行归档。
