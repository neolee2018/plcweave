# PLCWeave · 控程工坊

**面向人工与 AI Agent 的测试驱动 PLC 工程工具链。**

[English](README.md) | 简体中文

Markdown需求与测试 → 受支持FX指令执行 → 独立验证 → 受控硬件采样 → 可追溯交付。首个执行子集面向FX3U/HBDTECH L01S。目前仍在开发，不是完整PLC仿真器，也不是经过认证的生产控制器。

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
.venv/bin/python -c 'import gxwlib; from gxwlib import _core; print(_core.__file__)'
.venv/bin/python -m plcweave --help
.venv/bin/python -m pytest -q tests --basetemp=local/pytest-readme
```

2026-10-24已在Debian 13（Linux aarch64）、CPython 3.13、Rust 1.93.0验证：vendor编译、全量测试和无硬件示例通过。Debian/Ubuntu需先安装C工具链（`sudo apt install build-essential`，否则cargo报 ``linker `cc` not found``）；若 `python3.13 -m venv` 提示缺ensurepip，安装 `python3.13-venv`，或用 `--without-pip` 建venv后以 `get-pip.py` 安装pip。macOS尚未验证。POSIX下将后文Windows入口替换成 `.venv/bin/python -m plcweave`，用编辑器或Agent文件工具写入示例UTF-8文件。当前PlatformIO适配器和离线开发助手为Windows专用。

公开工具测试使用合成夹具，不依赖客户project内容。客户专用集成测试保留在各自私有项目目录。记录实际通过/失败/跳过数量，不套用私有工作区数量。

## 2. 首次运行：不连接硬件

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

s1-freeze.md绑定两份MD的原始字节。草稿/空用例、未知字段、双重作者源、创建源程序后才首次冻结都会被拒绝。[MD用例格式](.agents/skills/plc-program-development/references/markdown-cases.md)定义可执行表格，执行时内存解析，不另存测试JSON/YAML作者文件。

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

这是**安装自检证据包**，不是正式客户交付。FX/L01S正式交付仍需复核MAIN.csv、COMMENT.csv、测试/接线/完整寄存器表PDF、同源指令表详解PDF，再显式打包这四个文件。六命令CLI不会自动生成完整说明书或下载设备程序。

## 3. 开发工作流

| 阶段 | 工作与证据 |
| --- | --- |
| S0 | requirements.md记录机型、I/O/地址依据、行为、故障、时序、复位、验收等级和现场授权，提前查明测量能力。 |
| S1 | 独立写test_cases.md，覆盖正常/边界/故障/恢复；完成规定复核后冻结s1-freeze.md，再编写新源程序。 |
| S2 | 编写source.fxil，生成导入格式并实际执行受支持指令；未知指令/形式/地址阻断，不能静默NOP。 |
| S3 | 比较实际轨迹/断言，独立复核检查证据；程序缺陷与工具缺陷分别处理，S2不能改冻结预期。 |
| S4 | 提供可检查候选及真实验证等级；草稿保持MD，需要交付时再正式排版。 |
| S5/S6 | 按适用且已授权的厂家/人工下载和台架通路执行，只记录真实做过的检查；精度不足保留UNVERIFIED。 |
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

### 已支持指令子集（FX3U profile）

| 类别 | 仿真可执行 | 不支持（编译即阻断） |
| --- | --- | --- |
| 位逻辑 | LD、LDI、AND、ANI、OR、ORI、OUT、SET、RST、ANB、ORB、MPS、MRD、MPP、END | 脉冲触点/输出、STL/SFC、跳转、子程序、中断 |
| 定时器/计数器 | T、C触点，常数设定值OUT，RST | 变量设定值、32位及高速计数器 |
| 字运算 | MOV、ADD、SUB、MUL、DIV（非零常数除数），有符号16位 AND=/</<=/>/>= | 32位运算、运算标志、PID、变址/间接寻址 |
| 软元件 | X/Y0–177（八进制）、M0–7679、M8000–8511、T、C、D0–7999（D8000–8511仅作普通字映像） | 特殊寄存器背后的外设行为（UART、ADC、DAC）、掉电保持 |

表外指令一律拒绝，不会静默变成NOP。详见[执行核边界](docs/RUNTIME-CHANGES.md)。

## 4. AI Agent执行指令

将本仓库和以下任务交给Agent：

> 先读AGENTS.md、.agents/skills/plc-program-development/SKILL.md及MD参考。识别系统、Python ABI/版本、Rust和原生编译器，在主机权限内安装缺失前提；创建/使用专用.venv，先安装./vendor/gxwlib，再安装.[test]。实际执行导入、CLI帮助、测试和无硬件示例，记录命令、版本、错误与结果；依赖错误先修依赖，不改PLC逻辑。公开安装不需要公司服务、兄弟仓库、客户案例或全局技能。未指定位置时新建project子目录；指定外部位置则遵从。需求/测试只MD，规定节点组织四位独立新上下文复核，先冻结后源程序，再真实执行和比较轨迹，不改预期迎合实现。仿真/协议/硬件/未验证分开记录；没有现场授权和已知映射不访问设备或切RUN/STOP。保留旧证据，最终项目内交付目录+ZIP、核对哈希，仅清理本任务资源。复核者、前提、权限、指令或采集能力缺失时说明确切阻塞，不得伪造完成。

工作流技能位于标准项目技能目录 `.agents/skills/plc-program-development/`：在本仓内启动Codex会自动发现（也可输入 `$plc-program-development` 显式调用），AGENTS.md/CLAUDE.md也要求其他Agent在任何PLC任务前先读取。无需全局安装。tools/sync_plc_skill.py仅更新**已有旧技能**，不是通用新技能安装器。Hindsight/ZERO仅适用于已配置的公司工作区，开源用户不需要这些服务或凭据。

## 5. 可选PlatformIO与硬件

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

这是带门禁的命令，不是通用设备教程。先配置受支持适配器并复核机型/映射。内置L01S通路当前使用COM7、站号1、9600/8/N/1，不自动发现端口/型号。新MD项目需要匹配build_identity.json；HIL还需当前manual_download.json，绑定源/测试哈希、真实操作者确认/时间。没有CLI自动生成这些文件。旧端点HIL拒绝完整扫描关系套件，必须使用合格采样适配器。

SIM_PASS不是硬件验收。轮询不能证明每扫描安全、端子电压/电流、掉电保持或真实工艺性能。详见[执行核边界](docs/RUNTIME-CHANGES.md)、[蓝图](docs/BLUEPRINT.md)、[路线图](docs/ROADMAP.md)。

## 6. 常见问题

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
