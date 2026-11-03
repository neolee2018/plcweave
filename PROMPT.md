# 提示词合集：克隆仓库后，把构建、演示或真实编程交给任意 AI Agent

这是给**刚克隆本仓库的人**的入口。本文件有两份提示词：

- **提示词一：安装 + 演示**——一条提示词让 Agent 自动装环境、跑测试、执行固定场景演示并
  打出交付 ZIP，中途不需要你回答任何问题；
- **提示词二：真实项目编程**——按两阶段工作流开发你自己的控制程序：第一阶段交付
  需求/设计/测试/程序（HIL 测试版与正式版两份指令表），第二阶段在你编译下载并确认后完成
  在环测试与正式交付（见文末）。

两份都要求 Agent 能在本机执行终端命令和读写文件；纯网页聊天窗口（没有本机执行能力的对话）
跑不了这些流程。

**三步用法：**

1. `git clone https://github.com/neolee2018/plcweave.git && cd plcweave`
2. 复制下面【提示词】整段；
3. 粘贴给一个**能在你电脑上执行终端命令和读写文件**的 AI Agent（Codex CLI、Claude Code、
   Cursor、ZCode 等）。

纯网页聊天窗口（没有本机执行能力的对话）跑不了本流程，它最多帮你解读结果。默认是
**无硬件全自动**模式：Agent 不会打开串口，S6 硬件在环在交付报告里如实写“未执行”。
如果你接了隔离 L01S 台架，发提示词时补一句“PLC 已连接”，Agent 会切换到
[`demo/START-HERE.md`](demo/START-HERE.md) 的硬件流程：采集串口参数、等你本人用 GX Works2
烧录并明确确认后，才会做 S6。

## 提示词一：安装 + 演示（复制这一段）

> 你在用户刚克隆的 PLCWeave 仓库里工作（先 cd 到含 `pyproject.toml` 和 `vendor/gxwlib` 的
> 仓库根目录）。目标：完成环境构建，跑通固定场景演示，交付并汇报。每一步真实执行、如实记录，
> 不伪造结果。
>
> 1. **构建**：先读仓库 `README.md` 第 1 节与 `demo/START-HERE.md`，再按你的操作系统执行：
>    - 确认 CPython 3.13+、Rust 1.93+ 与本机编译器/链接器；缺失时按 README 给的官方途径安装
>      （如 `winget`、`rustup`），遵守主机权限；需要提权被拒或没有网络时不要硬来，停下并明确
>      告诉用户卡在哪一步、差什么。
>    - 在仓库根目录创建 `.venv`（已存在则复用，不覆盖无关 venv）。下文 `python` 一律指该
>      venv 的解释器：Windows 是 `./.venv/Scripts/python.exe`，POSIX 是 `.venv/bin/python`。
>    - 先 `python -m pip install ./vendor/gxwlib`（会编译 Rust，几分钟属正常），再
>      `python -m pip install -e ".[test]"`。
>    - 验证：`python -c "import gxwlib; from gxwlib import _core; print(_core.__file__)"` 与
>      `python -m plcweave --help` 都要成功。
> 2. **自检**：`python -m pytest -q tests --basetemp=local/pytest-agent`，记录实际通过/失败
>    数量。失败先按 README 第 7 节排查环境问题，不改任何测试预期；排查后仍失败就如实报告并
>    停止，不要继续演示。
> 3. **演示（无硬件）**：依次执行：
>
>    ```
>    python -m plcweave demo start demo-run --not-connected
>    python -m plcweave simulate project/demo-run
>    python -m plcweave demo status project/demo-run
>    python -m plcweave demo deliver project/demo-run --version V001
>    ```
>
>    项目名已存在就换新名字（`demo-run-2`……），不删除旧项目。这条链路只做本地仿真与打包，
>    不会打开串口；中途不要向用户提问。
> 4. **汇报（给用户看的成品）**，用中文输出：
>    - 交付 ZIP 与目录的完整路径（`project/demo-run/delivery/` 下）；
>    - 贴出 `SUMMARY.md` 的关键结论原文：完成度（预期 60%）、仿真结果（预期 8 个用例全部
>      PASS、整体 `SIM_PASS`）、S6“未执行”、演示验收结论；
>    - 用一行一个文件说明 ZIP 里各是什么（需求、用例、指令表、注释、S6 报告、总结、清单等）；
>    - 最后告诉用户：若接了隔离 L01S 台架如何继续——按 `demo/START-HERE.md` 的 D4/D5，由用户
>      本人在 GX Works2 烧录并明确确认后，Agent 补装 `pip install -e ".[hil]"` 再做 S6。
> 5. **边界**（任何情况下）：不改冻结预期（`s1-freeze.md`）；未知指令不当 NOP；不把 SIM_PASS
>    或抽样通过说成正式/电气验收；未获用户明确确认烧录与台架前，不打开串口、不写设备；某一步
>    被权限或环境挡住，就如实说明卡在哪一步，不伪造完成。
> 6. **硬件分支**：如果用户随提示词说明“PLC 已连接/要接硬件”，改按 `demo/START-HERE.md` 的
>    模式 B：先问项目名并收集 COM 口、波特率、校验位、从站地址再 `demo start`；仿真通过后提醒
>    用户烧录；用户明确确认烧录并接好 RS485、现场为隔离空机后，才执行 `demo confirm-flash`、
>    `demo confirm-bench`、`preflight`、`hil --isolated-bench`，最后重新 `demo deliver` 新版本。

## 提示词二：真实项目编程（两阶段工作流）

要开发你自己的控制程序，在【我的控制需求】处填入你的控制要求后整段复制给能在本机执行终端
命令的 AI Agent；写不清楚也没关系，Agent 会先提问澄清再动工。本提示词与
[`README.zh-CN.md`](README.zh-CN.md) 第 2 节末尾内容一致。流程与命令细节以仓库技能文件为准，
Agent 第一步就会读它们。

```text
你在 PLCWeave 仓库根目录工作（目录里有 pyproject.toml 和 vendor/gxwlib）。请按两阶段工作流
为我开发一个 PLC 控制程序：每一步真实执行、如实记录，不伪造结果；流程细节一律以仓库技能
文件为准。

【我的控制需求】（在此填写；写不清楚也没关系，你会先向我提问澄清）
机型/品牌：例如 HBDTECH L01S（FX3U 兼容）
输入/输出：例如 X0 启动按钮、X1 停止按钮、Y0 水泵、Y1 故障指示灯
控制逻辑：例如启动后水泵运行；停止或液位超限立即停机；故障报警并自锁
保护/复位/验收要求：（补充你的验收要求）

0. 准备：先读 AGENTS.md、skills/plc-program-development/SKILL.md 和
   skills/plc-program-development/references/two-phase-workflow.md。环境没装就先按 README
   第 1 节装好：创建专用 .venv；先 python -m pip install ./vendor/gxwlib，再
   python -m pip install -e ".[test]"；导入与 --help 验证通过。不要动无关环境。项目默认建在
   仓库 project/<项目名>/ 下；我指定了外部目录就遵从。
1. 第一阶段（AI 主导，我只改 requirements.md）：
   - 澄清需求后用 workflow init 建项目；项目名已存在就停下问我，不合并不覆盖；
   - 你维护 design.md、独立 test_cases.md 和共用 source.fxil，关键产出给我确认；
   - 构建前向我收集串口参数（COM 口、波特率、校验、站号），程序与台架必须同一套；
   - S1 冻结（workflow freeze）前组织 4 个不同独立上下文的 Agent 复核，主 Agent 不计入；
   - workflow build 生成同一控制核心的 HIL 测试版与正式版两份指令表；
   - 复核通过后 workflow deliver --stage 1：在项目 delivery/<版本>/ 打成 ZIP，汇报需求、
     设计、测试、程序四类成果与哈希清单。
2. 第二阶段（我烧录，你采样）：
   - 我在 GX Works2 导入 hil/MAIN.csv 与同目录 COMMENT.csv，选对 CPU，编译并下载 HIL 版；
   - 我明确确认"已编译、已下载、RUN"后，你才执行 workflow confirm-download；等我确认
     隔离空机、RS485 已接后再 workflow test 采样，与冻结预期比较；
   - 程序缺陷修共用核心并出新 build，等我重新编译下载确认后再测；不放宽预期，不把通信
     或脚本错误当程序缺陷；
   - 全部规定用例同版 PASS、四位独立复核通过后 workflow deliver --stage 2。
3. 边界（任何情况下）：不改冻结预期；未知指令不当 NOP；未经我明确确认不打开串口、不写
   设备、不切 RUN/STOP；SIM_PASS 与稳态采样不冒充正式/电气验收；被权限或环境挡住时
   如实说明卡在哪一步，不伪造完成。我改需求时走 workflow revise，旧快照与证据保留。
```

## English（提示词二）

```text
You are working at the PLCWeave repository root (the directory contains pyproject.toml and
vendor/gxwlib). Develop a PLC control program for me through the two-phase workflow: execute
every step for real, record honest results, never fabricate completion, and treat the repository
skill files as the authority for details.

[My control requirement] (fill in here; unclear requirements are fine — you ask me first)
Model/brand: e.g. HBDTECH L01S (FX3U compatible)
Inputs/outputs: e.g. X0 start button, X1 stop button, Y0 pump, Y1 fault lamp
Control logic: e.g. the pump runs after start; stops immediately on stop or high level; latched
alarm on fault
Protection / reset / acceptance: (add your acceptance requirements)

0. Preparation: read AGENTS.md, skills/plc-program-development/SKILL.md and
   skills/plc-program-development/references/two-phase-workflow.md first. If the environment is
   not installed, follow README section 1: create a dedicated .venv; install ./vendor/gxwlib
   first, then -e ".[test]"; verify the import and --help. Never touch unrelated environments.
   Create the project under project/<name>/ in the repository unless I specify an external
   directory.
1. Phase 1 (AI-led; I edit only requirements.md):
   - Clarify my requirement, then workflow init the project; on a name clash stop and ask me,
     never merge or overwrite;
   - You maintain design.md, independent test_cases.md and the shared source.fxil; show me key
     outputs for confirmation;
   - Collect serial parameters from me before building (COM port, baud, parity, station); the
     program and the bench must use the same set;
   - Arrange review by 4 distinct fresh-context agents before the S1 freeze (workflow freeze);
     the main agent does not count;
   - workflow build produces the HIL test build and the production build from one shared
     control core;
   - After review passes, workflow deliver --stage 1: build delivery/<version>/ plus a ZIP in
     the project and report requirements, design, tests, program and the hash manifest.
2. Phase 2 (I download, you sample):
   - I import hil/MAIN.csv with its COMMENT.csv into GX Works2, select the right CPU, compile
     and download the HIL build;
   - Only after I explicitly confirm "compiled, downloaded, RUN" do you run workflow
     confirm-download; after I confirm the isolated idle bench with RS485 connected, run
     workflow test and compare against frozen expectations;
   - For program defects fix the shared core into a new build and wait for my re-download and
     confirmation; never loosen expectations and never blame communication or script errors on
     the PLC program;
   - After all planned cases PASS on one final build and the four-agent review passes, run
     workflow deliver --stage 2.
3. Boundaries (always): never edit frozen expectations; never treat unknown instructions as
   NOPs; never open a serial port, write a device or switch RUN/STOP without my explicit
   confirmation; never present SIM_PASS or steady-state sampling as formal/electrical
   acceptance; when blocked, say exactly which step is blocked instead of faking completion.
   When I change requirements use workflow revise and keep old snapshots and evidence.
```

## English

> Work inside the user's freshly cloned PLCWeave repository (first `cd` to the repository root that
> contains `pyproject.toml` and `vendor/gxwlib`). Goal: build the environment, run the fixed demo
> end to end, deliver, and report. Execute every step for real and record honest results; never
> fabricate completion.
>
> 1. **Build**: read `README.md` section 1 and `demo/START-HERE.md`, then for your OS: verify
>    CPython 3.13+, Rust 1.93+ and a native compiler/linker; install missing prerequisites via the
>    official routes given in the README, respecting host permissions — if elevation is refused or
>    there is no network, stop and say exactly what is missing. Create `.venv` at the repository
>    root (reuse an existing one; never overwrite an unrelated venv). `python` below means that
>    venv's interpreter (`./.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on POSIX).
>    Install `python -m pip install ./vendor/gxwlib` first (it compiles Rust; a few minutes is
>    normal), then `python -m pip install -e ".[test]"`. Verify with
>    `python -c "import gxwlib; from gxwlib import _core; print(_core.__file__)"` and
>    `python -m plcweave --help`.
> 2. **Self-check**: run `python -m pytest -q tests --basetemp=local/pytest-agent` and record the
>    real passed/failed counts. On failure, troubleshoot the environment per README section 7 —
>    never change test expectations. If it still fails, report honestly and stop.
> 3. **Demo (no hardware)**: run, without asking the user anything:
>
>    ```
>    python -m plcweave demo start demo-run --not-connected
>    python -m plcweave simulate project/demo-run
>    python -m plcweave demo status project/demo-run
>    python -m plcweave demo deliver project/demo-run --version V001
>    ```
>
>    If the project name exists, pick a new one (`demo-run-2`, ...); never delete old projects.
>    This chain only simulates and packages locally; it never opens a serial port.
> 4. **Report (the deliverable the user sees)**: give the full delivery ZIP/folder paths under
>    `project/demo-run/delivery/`; quote the `SUMMARY.md` verdicts (expected: completion 60%,
>    8/8 cases PASS and overall `SIM_PASS`, S6 "not executed"); explain each ZIP file in one line;
>    and explain how to continue with an isolated L01S bench (`demo/START-HERE.md` D4/D5: the user
>    downloads with GX Works2 and explicitly confirms; the agent then installs `.[hil]` and runs S6).
> 5. **Boundaries**: never edit frozen expectations (`s1-freeze.md`); never treat unknown
>    instructions as NOPs; never present SIM_PASS or sampled checks as formal/electrical
>    acceptance; never open a serial port or write to a device before the user explicitly confirms
>    the download and bench readiness; when blocked, say which step is blocked instead of faking it.
> 6. **Hardware branch**: if the user says the PLC is connected, switch to mode B in
>    `demo/START-HERE.md`: ask for the project name and COM port/baud/parity/station before
>    `demo start`; after SIM_PASS remind the user to download; only after explicit flash and bench
>    confirmations run `demo confirm-flash`, `demo confirm-bench`, `preflight`, `hil
>    --isolated-bench`, then re-deliver a new version.
