# PLCWeave · 控程工坊

**面向人工与 AI Agent 的测试驱动 PLC 工程工具链。**

[English](README.md) | 简体中文

Markdown需求与测试 → 受支持FX指令执行 → 独立验证 → 受控硬件采样 → 可追溯交付。首个执行子集面向FX3U/HBDTECH L01S。只想先看它跑起来，直接走[快速演示](#2-快速演示一条提示词)；要直接开发自己的控制程序，用第 2 节末尾的[两阶段编程提示词](#一条提示词开始真实项目编程两阶段工作流)。目前仍在开发，不是完整PLC仿真器，也不是经过认证的生产控制器。

客户定制项目使用[两阶段工作流](skills/plc-program-development/references/two-phase-workflow.md)：用户只修改需求，AI维护设计、独立测试和共用控制程序，第一阶段交付HIL测试版及正式版两份指令表；第二阶段由用户编译下载后，AI采集PLC寄存器、比较并迭代。新增 `workflow init/freeze/build/deliver/confirm-download/test/status/revise`；当前仅覆盖受支持FX子集和L01S稳态采样，台达适配尚未实现，厂家编译下载保留人工通路。

## 1. 安装

### 前提

| 项目 | 要求 |
| --- | --- |
| Python | 标准、启用GIL的CPython **3.13+**，推荐3.13；vendored绑定不支持PyPy和自由线程版本。 |
| Rust | **1.93+**、Cargo和原生链接器；vendor的rust-toolchain.toml将rustup固定为 **1.93.0**。 |
| Windows构建工具 | MSVC C++ Build Tools、Desktop development with C++工作负载、兼容Windows SDK。 |
| 源码 | 本仓完整内容，包括vendor/gxwlib、src、tools、skills。 |

克隆公开仓库，或解压源码包：

```text
git clone https://github.com/neolee2018/plcweave.git
cd plcweave
```

下面命令都在包含pyproject.toml的仓库根目录执行。不能从其他私有兄弟项目补文件。

**安装步骤总览**（各平台完整命令见下文小节）：

1. 装系统前提：CPython 3.13+、Rust 1.93+、本机 C++ 构建工具/链接器（Windows 另需 MSVC C++ 工作负载与 Windows SDK）；
2. 在仓库根目录创建专用 `.venv`；
3. 先安装本仓执行核 `./vendor/gxwlib`（maturin 编译 Rust，需联网，几分钟属正常）；
4. 再安装 PLCWeave 本体 `-e ".[test]"`；需要 S6/USB-RS485 硬件在环时加装 `.[hil]`；
5. 验证：gxwlib 导入、`plcweave --help`、测试套件全部通过。

### 安装工作流技能（AI Agent建议安装）

工作流就是本仓技能 **`plc-program-development`**（`skills/plc-program-development/SKILL.md`）及其 `references/` 目录。直接阅读本仓技能即可，全局安装可选；若要让Agent在本仓库之外的项目目录中也能按该工作流执行，建议安装。

安装时把**整个** `skills/plc-program-development/` 目录复制或链接到所用Agent平台的技能目录，目录名必须保持 `plc-program-development`（与 `SKILL.md` 的 `name:` 字段一致）；`SKILL.md` 与 `references/` 不能拆开。更新仓库后重新同步该目录，保持仓库技能为唯一来源。`tools/sync_plc_skill.py` 仅更新**已有旧技能**，不是通用安装器。

缺少系统前提时，遵循官方[Python](https://www.python.org/downloads/)、[Rust/rustup](https://www.rust-lang.org/tools/install/)、[Windows Rust/MSVC](https://learn.microsoft.com/en-us/windows/dev-environment/rust/setup)安装说明。Windows可使用 `winget install --exact --id Python.Python.3.13` 和 `winget install --exact --id Rustlang.Rustup`，仍需安装C++工作负载/SDK。安装后重新打开终端。AI安装系统软件须遵守主机安装/提权权限。

### Windows / PowerShell

使用专用venv，无需激活终端环境或全局安装Python包：

```powershell
py -3.13 --version
rustc --version
cargo --version
# 使用rustup时准备vendor要求的版本和组件：
rustup toolchain install 1.93.0 --profile minimal --component rustfmt --component clippy

py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m ensurepip --upgrade
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install ./vendor/gxwlib
./.venv/Scripts/python.exe -m pip install -e ".[test]"
# 可选：S6/USB-RS485 依赖（pymodbus、pyserial）
./.venv/Scripts/python.exe -m pip install -e ".[hil]"

./.venv/Scripts/python.exe -c "import gxwlib; from gxwlib import _core; print(_core.__file__)"
./.venv/Scripts/python.exe -m plcweave --help
./.venv/Scripts/python.exe -m pytest -q tests --basetemp=local/pytest-readme
```

不得覆盖无关的已有.venv。没有py启动器时使用目标CPython完整路径。若已经配置适用的独立Rust工具链，可以省略rustup命令。

**先安装本仓执行核。** 仅安装PLCWeave主包不会带上它；PyPI同名上游包可能缺少本仓扩展，不能替代。pip使用vendor的[maturin构建配置](https://www.maturin.rs/installation)编译原生绑定，首次需要联网取得构建依赖/crates。不需要内部盘符、原项目、公司服务或tools/import_runtime.py。

tools/plcweave.ps1会选择本仓venv、设置源码导入/UTF-8并恢复调用者环境。若主机策略禁止未签名PowerShell脚本，改用 `./.venv/Scripts/python.exe -m plcweave ...`，不必更改全局执行策略。

### Linux / macOS

安装支持venv的标准CPython3.13，以及Rust、GCC/Clang/链接器（Linux）或Xcode Command Line Tools（macOS），见[Rust官方指南](https://doc.rust-lang.org/book/ch01-01-installation.html)。然后：

```sh
python3.13 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
rustup toolchain install 1.93.0 --profile minimal --component rustfmt --component clippy
.venv/bin/python -m pip install ./vendor/gxwlib
.venv/bin/python -m pip install -e '.[test]'
# 可选：S6/USB-RS485 依赖
.venv/bin/python -m pip install -e '.[hil]'
.venv/bin/python -c 'import gxwlib; from gxwlib import _core; print(_core.__file__)'
.venv/bin/python -m plcweave --help
.venv/bin/python -m pytest -q tests --basetemp=local/pytest-readme
```

这是源码安装路径，不代表这些平台已经验证。现有本地验证在Windows完成。POSIX下将后文Windows入口替换成 `.venv/bin/python -m plcweave`，用编辑器或Agent文件工具写入示例UTF-8文件。当前PlatformIO适配器和离线开发助手为Windows专用。

公开工具测试使用合成夹具，不依赖客户project内容。客户专用集成测试保留在各自私有项目目录。记录实际通过/失败/跳过数量，不套用私有工作区数量。

## 2. 快速演示（一条提示词）

克隆仓库后，把仓库根目录 [`PROMPT.md`](PROMPT.md) 的提示词一（安装 + 演示）复制给你的 AI
Agent，剩下的它全做：安装前置条件与工具链、跑测试套件、执行**固定**的 L01S 场景（启停 +
3 秒延时输出 + 运行计时）、打出带核验清单的交付 ZIP 并向你汇报。要求 Agent 能在本仓库目录
执行终端命令（Codex CLI、Claude Code、Cursor、ZCode 等）；没有本机执行能力的纯聊天窗口跑
不了本流程。

默认是**无硬件全自动**模式：Agent 不提问、不打开串口，S6 在交付报告里如实写“未执行”（完成度
60%）。环境已装好想要更短的提示词，用 [`demo/PROMPT.md`](demo/PROMPT.md)。接了隔离 L01S 台架
就发提示词时说明，Agent 会切换到 [`demo/START-HERE.md`](demo/START-HERE.md) 的硬件流程：采集
串口参数，等你本人用 GX Works2 烧录并明确确认烧录/台架状态后，才做 S6 抽样。

```powershell
./tools/plcweave.ps1 demo start demo-run --not-connected
./tools/plcweave.ps1 simulate project/demo-run
./tools/plcweave.ps1 demo status project/demo-run
./tools/plcweave.ps1 demo deliver project/demo-run --version V001
```

预期：`SIM_PASS`（8/8 用例通过），得到 `project/demo-run/delivery/V001/` 和
`project/demo-run/delivery/demo-run-V001.zip`。压缩包内含演示场景需求、测试用例、`MAIN.csv`、
`COMMENT.csv`、区分“已完成/未测试”的 S6 报告，以及带完成度（无硬件 60%）和“演示验收/正式验收”
结论的总结报告。演示只证明工作流，不是生产控制程序；轮询限制
和电气/带载缺口保留为 UNVERIFIED。

### 一条提示词开始真实项目编程（两阶段工作流）

演示只证明工作流；要开发你自己的控制程序，把下面整段提示词复制给能在本机执行终端命令的
AI Agent，并在【我的控制需求】处填入你的控制要求（写不清楚也没关系，Agent 会先提问澄清
再动工）。内容与根目录 [`PROMPT.md`](PROMPT.md) 的提示词二保持一致。

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

## 3. 首次运行：不连接硬件

本示例只检查安装和CLI，不访问PLC，不代表客户程序验收，也不代替独立复核。若project/quickstart已存在，请换名称并替换全部路径，不能删除旧证据。

### A. 建项，先写测试再写源程序

```powershell
./tools/plcweave.ps1 init quickstart
```

只创建requirements.md、test_cases.md、README.md。用户指定外部目录可用 `init my-project --directory D:/PLCProjects/my-project`；仓库内客户目录只能放在project下。

在创建source.fxil**之前**写需求和测试：

```powershell
@'
# Requirements
R01: In virtual RUN, M0 shall be 1 on every observed scan.
R02: M0 stays within 0..1. No physical I/O is used.
'@ | Set-Content -Encoding utf8 project/quickstart/requirements.md

@'
# Test cases
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

## TC-001: RUN indication
### Initial
| device | value |
| --- | --- |

### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | M0=1 | M0=1 | Observe two complete scans |
'@ | Set-Content -Encoding utf8 project/quickstart/test_cases.md

./tools/plcweave.ps1 freeze project/quickstart
```

s1-freeze.md绑定两份MD的原始字节。草稿/空用例、未知字段、双重作者源、创建源程序后才首次冻结都会被拒绝。[MD用例格式](skills/plc-program-development/references/markdown-cases.md)定义可执行表格，执行时内存解析，不另存测试JSON/YAML作者文件。

### B. 实现，再执行冻结测试

```powershell
@'
#meta
project: Quickstart
#instructions
LD M8000
OUT M0
END
#comments
M0 Virtual RUN indication
'@ | Set-Content -Encoding utf8 project/quickstart/source.fxil

./tools/plcweave.ps1 simulate project/quickstart
```

预期TC-001 PASS、最终SIM_PASS、退出码0。基础套件在项目内candidate/V001生成MAIN.csv、COMMENT.csv、runtime.csv、simulation_report.json、simulation_trace.csv；复杂独立关系套件当前默认evidence/simulation/latest。执行返回前再次核对冻结输入，不能直接改冻结记录使测试通过。

### C. 打包安装自检证据

```powershell
./tools/plcweave.ps1 package project/quickstart --version smoke-V001 --file candidate/V001/MAIN.csv --file candidate/V001/COMMENT.csv --file candidate/V001/simulation_report.json
```

预期生成project/quickstart/delivery/smoke-V001文件夹和project/quickstart/delivery/quickstart-smoke-V001.zip。文件夹含选定文件和带SHA-256的MANIFEST.md，ZIP包含相同内容；已有版本拒绝覆盖。

这是**安装自检证据包**。客户定制交付使用上述 `workflow` 入口，包含需求、设计、用例、HIL/正式版两份指令表及说明和配套证据；PDF按用户需要额外生成。工具不会自动完成自然语言设计、厂家编译或程序下载。

## 4. 开发工作流

| 阶段 | 工作与证据 |
| --- | --- |
| S0 | requirements.md记录机型、I/O/地址依据、行为、故障、时序、复位、验收等级和现场授权，提前查明测量能力。 |
| S1 | 独立写test_cases.md，覆盖正常/边界/故障/恢复；完成规定复核后冻结s1-freeze.md，再编写新源程序。 |
| S2 | 编写source.fxil，生成导入格式并实际执行受支持指令；未知指令/形式/地址阻断，不能静默NOP。 |
| S3 | 比较实际轨迹/断言，独立复核检查证据；程序缺陷与工具缺陷分别处理，S2不能改冻结预期。 |
| S4 | 提供可检查候选及真实验证等级；草稿保持MD，需要交付时再正式排版。 |
| S5/S6 | 按适用且已授权的厂家/人工下载和台架通路执行，只记录真实做过的检查；精度不足保留UNVERIFIED。S6 HIL方法见[S6-HIL-V2](skills/plc-program-development/references/s6-hil-v2.md)。 |
| S7 | 执行受影响回归及依赖，完成复核，在项目内建立交付目录和ZIP，校验哈希，释放任务资源。 |

**四位独立复核者**：S1冻结、S3/重大修订、S6判定、最终交付复核节点，使用四个不同、独立上下文Agent；主Agent组织/修复，不计入四位。每人仅接收相关原始材料、版本/哈希、验收标准和资源边界，不传完整主会话或预设结论。

四个视角：需求/测试；程序/执行/判定；工具/异常/身份/清理；隔离/文档/交付/可复测性。并发不足分批，失败或不可用表示未完成，不计PASS；不能假扮四位或静默豁免。实际检查/结果存入reviews/<节点>；修复后复查相关问题。旧结论仅在版本/哈希匹配且明确范围时引用。

STATIC_PASS、SIM_PASS、厂家验证、硬件观测、电气/带载分别记录。核心判定区分PASS、PROGRAM_FAIL、TEST_INFRA_ERROR、UNVERIFIED，各命令另有汇总状态；preflight的PROTOCOL_READ_PASS不证明应用行为或电气正确。

```text
skills/ src/ tools/ tests/ vendor/ docs/      # 技能、工具、工具测试和说明
project/
  customer-project/                         # 公共Git默认忽略
    requirements.md  test_cases.md  s1-freeze.md
    source.fxil
    Doc/  evidence/  reviews/
    delivery/<version>/
    delivery/customer-project-<version>.zip
```

每客户独立文件夹，支持明确指定的外部目录；客户内容不能放进工具代码、测试、说明或技能中。新草稿仅MD，历史冻结JSON可兼容读取但不改写；真实执行报告/轨迹可用JSON/CSV。交付只选定项目成果，不打包环境、凭据、其他客户或整个仓库。

## 5. AI Agent执行指令

将本仓库和以下任务交给Agent：

> 先读AGENTS.md、skills/plc-program-development/SKILL.md及MD参考。识别系统、Python ABI/版本、Rust和原生编译器，在主机权限内安装缺失前提；创建/使用专用.venv，先安装./vendor/gxwlib，再安装.[test]。实际执行导入、CLI帮助、测试和无硬件示例，记录命令、版本、错误与结果；依赖错误先修依赖，不改PLC逻辑。公开安装不需要公司服务、兄弟仓库、客户案例或全局技能。未指定位置时新建project子目录；指定外部位置则遵从。需求/测试只MD，规定节点组织四位独立新上下文复核，先冻结后源程序，再真实执行和比较轨迹，不改预期迎合实现。仿真/协议/硬件/未验证分开记录；没有现场授权和已知映射不访问设备或切RUN/STOP。保留旧证据，最终项目内交付目录+ZIP、核对哈希，仅清理本任务资源。复核者、前提、权限、指令或采集能力缺失时说明确切阻塞，不得伪造完成。

可以直接阅读仓库技能，全局安装可选（安装方法见第1节“安装工作流技能”）。tools/sync_plc_skill.py仅更新**已有旧技能**，不是通用新技能安装器。Hindsight/ZERO仅适用于已配置的公司工作区，开源用户不需要这些服务或凭据。只要“自动安装+跑演示”的话，直接把根目录 [PROMPT.md](PROMPT.md) 的提示词一交给Agent（见第2节）；真实项目编程用同文件的提示词二（同见第2节末尾）。

## 6. 可选PlatformIO与硬件

### PlatformIO：当前适配器Windows专用

本地仿真不依赖PlatformIO；需要编排时安装到项目venv，已测试版本基线6.1.19：

```powershell
./.venv/Scripts/python.exe -m pip install "platformio==6.1.19"
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location) 'local/pio-core'
```

初版MD草稿完成后建立project/quickstart/platformio.ini：

```ini
[platformio]
default_envs = fx_demo
platforms_dir = ../../local/pio-platforms

[env:fx_demo]
platform = file://../../tools/pio-platform
custom_workspace = ../..
```

```powershell
./.venv/Scripts/python.exe -m platformio run --project-dir project/quickstart -t simulate
# 本地平台源码变更后，重跑前刷新已安装副本：
./.venv/Scripts/python.exe -m platformio pkg install --project-dir project/quickstart --platform file://../../tools/pio-platform --force
```

相对路径仅适用于上述布局。外部项目使用绝对platform（file://<工具仓库路径>/tools/pio-platform）、绝对custom_workspace并明确缓存位置，参见[PlatformIO安装说明](https://docs.platformio.org/en/latest/core/installation/methods/pypi.html)。

默认simulate、preflight只读；显式bench需要项目内独立验证的custom_hil_script、新custom_hil_output和隔离台架授权。本仓没有适用于每个客户的通用合格台架脚本。**upload明确阻断：没有已验证的L01S应用编译/下载器。** 适配器不会把PLC当通用MCU替换运行固件。

### 硬件前提

```powershell
./.venv/Scripts/python.exe -m pip install -e ".[hil]"
./tools/plcweave.ps1 preflight project/my-project
./tools/plcweave.ps1 hil project/my-project --isolated-bench
```

这是带门禁的命令，不是通用设备教程。先配置受支持适配器并复核机型/映射。内置L01S默认COM7、站号1、9600/8/N/1，可用`bench_config.json`覆盖，不自动发现端口/型号。新MD项目需要匹配`build_identity.json`；HIL还需当前`manual_download.json`，绑定源/测试哈希、真实操作者确认/时间；演示项目还需要`demo confirm-bench`生成的`bench_ready.json`。核心CLI不会自动生成这些文件，演示命令会。旧端点HIL拒绝完整扫描关系套件，必须使用合格采样适配器。

SIM_PASS不是硬件验收。轮询不能证明每扫描安全、端子电压/电流、掉电保持或真实工艺性能。详见[执行核边界](docs/RUNTIME-CHANGES.md)、[蓝图](docs/BLUEPRINT.md)、[路线图](docs/ROADMAP.md)。

## 7. 常见问题

| 现象 | 处理 |
| --- | --- |
| 缺pip | 用目标venv Python执行-m ensurepip --upgrade，后续始终同一解释器调用pip。 |
| 缺gxwlib/_core | 在该venv构建安装./vendor/gxwlib，查Python ABI、Rust、编译器/链接器和日志，不替换不相关wheel。 |
| 缺plcweave | 安装-e ".[test]"，使用目标venv/入口；纯源码运行需PYTHONPATH=src。 |
| Rust/MSVC/链接失败 | 安装缺失工具、工作负载/SDK，重开终端重试失败构建，不改PLC预期。 |
| 下载/权限错误 | 处理具体依赖的网络/代理/主机权限并保留日志，不关闭证书校验或假称离线安装成功。 |
| 草稿/冻结变更/双源被拒 | 完成契约或建立独立复核修订，不静默回退JSON或重写旧冻结。 |
| PlatformIO找不到新任务 | 如上刷新本地平台已安装副本并核对源码/版本。 |
| 采集精度不足 | 保留UNVERIFIED，说明缺少的测量能力，不放宽容差/重跑无关全量。 |

tools/build_runtime.py是Windows**离线开发助手**，要求已有venv、Rust缓存及编译器，不是首次安装器。PDF另需文档排版/渲染工具，基础安装不含专有工程软件或厂家授权。

## 许可

原创代码采用[Apache-2.0](LICENSE)，归属见[NOTICE](NOTICE)、[第三方清单](THIRD_PARTY_NOTICES.md)。vendored gxwlib为MIT并保留嵌套许可/声明，分发须保留。docs/runtime-provenance.json是历史来源记录，不是安装依赖。无硬件工作流不需要客户程序、专有手册、凭据、GX Works2安装或公司服务。本项目与三菱电机无隶属或认证关系。
