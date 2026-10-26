# PLCWeave 演示：一条提示词，从需求到交付

这个演示面向**第一次克隆仓库的人**。目标不是展示一个复杂工艺，而是用最小程序证明整条链路
真实可跑：需求 → 冻结用例 → 程序 → 仿真 → 人工烧录 → S6 硬件在环 → 六项交付 ZIP。

**演示场景是固定的**（L01S 启停 + 3 秒延时输出 + 运行计时）。它不采集你的工艺需求，也不替代
真实项目的 S0 需求访谈；提示词描述的就是本次演示需求。真实客户项目请另建目录，按 S0–S7 定制。

- 演示程序：L01S 启停 + 3 秒延时输出 + 运行计时，默认物理输出禁止。
- 无硬件也能完成 D0–D3 和离线打包；S6 会明确写“未执行”，不会伪造 PASS。
- 有 L01S、USB-RS485 和隔离空机时，可以继续 D5，得到真实抽样报告。

演示有两种模式，Agent 按 PLC 是否连接选择：

- **模式 A：无硬件（默认，全自动）。** 不向客户提问，直接 `demo start <项目名> --not-connected`
  → `simulate` → `demo deliver`。全程不打开串口；D4/D5 跳过，S6 写“未执行”。刚克隆仓库的人可
  以直接把根目录 [`../PROMPT.md`](../PROMPT.md) 交给 Agent，它会连安装带演示一次跑完。
- **模式 B：接硬件（有确认门）。** 按 D1 采集串口参数，D4 烧录、D5 台架都必须由客户本人明确
  确认后才能继续；确认前 Agent 不得打开串口写设备。

## 0. 前置

按仓库 README 完成安装（或把根目录 [`../PROMPT.md`](../PROMPT.md) 交给 Agent 连安装一起做），
确认下面命令能跑：

```powershell
./tools/plcweave.ps1 --help
./.venv/Scripts/python.exe -c "import gxwlib; from gxwlib import _core; print(_core.__file__)"
./.venv/Scripts/python.exe -m pytest -q tests --basetemp=local/pytest-demo
# S6 需要串口依赖；干净安装只装了 .[test] 时先补：
./.venv/Scripts/python.exe -m pip install -e ".[hil]"
```

Linux/macOS 把 `./tools/plcweave.ps1` 换成 `.venv/bin/python -m plcweave`，串口名用
`/dev/ttyUSB0` 这类路径。Windows 若禁止未签名脚本，改用
`./.venv/Scripts/python.exe -m plcweave ...`，不要改全局执行策略。
然后把 `demo/PROMPT.md` 里的提示词发给 Agent。

## 1. 演示流程（D0–D6）

| 步骤 | 谁做 | 动作 | 通过条件 |
| --- | --- | --- | --- |
| D0 启动 | 客户 | 粘贴提示词（根 `PROMPT.md` 或本目录 `PROMPT.md`） | Agent 读到本文件，不擅自开串口 |
| D1 建项目 | Agent + 客户 | 模式 A 不提问，`--not-connected` 直接建；模式 B 先问项目名和连接参数再 `demo start` | 需求/用例先冻结，再出现 `source.fxil` |
| D2 编程 | Agent | 渲染固定演示程序与串口参数 | `source.fxil` 与 `bench_config.json` 一致 |
| D3 仿真 | Agent | 跑冻结用例 | `SIM_PASS`；否则不得进入烧录 |
| D4 烧录 | 客户 | GX Works2 导入、编译、下载、RUN | 客户明确回复“已烧录并 RUN”，编译结果已记录 |
| D5 S6 | Agent + 客户 | 接 485，跑 `preflight`/`hil` | 身份匹配；抽样结果如实记录 |
| D6 交付 | Agent | `demo deliver` | `delivery/<版本>/` 和 ZIP 生成，哈希可核 |

## 2. 模式 B：接硬件时 Agent 必须问的问题

模式 A（无硬件）**不提问**：项目名默认 `demo-run`（已存在则递增），直接 `--not-connected`。
只有客户说明 PLC 已连接（模式 B）时，才先问**项目名**（默认 `demo-<日期>`），再问：

> **PLC 现在是否已连接到这台电脑？**

如果客户回答“已连接”，继续问：

> 请提供 RS485 侧的四个参数：
> 1. 端口号（USB-RS485 在电脑上的 COM 口，例如 `COM7`；不是编程口 `COM5`）
> 2. 波特率（默认 `9600`）
> 3. 校验位（`N`/`E`/`O`，默认 `N`）
> 4. 从站地址（默认 `1`）

如果客户回答“未连接”，使用默认 `COM7 / 9600 / N / 1` 继续编程和仿真，并明确告诉客户：
**D5 不会执行，交付报告的 S6 一栏会写“未执行”。**

D4 烧录后还要问并记录：

> 1. 烧录操作者姓名
> 2. 使用的 GX Works2 版本
> 3. 编译结果（客户报告）
> 4. PLC 是否已切到 RUN

D5 之前还要问：

> PLC 已 RUN？USB-RS485 已接 Modbus 口？现场是隔离空机、未接传感器/执行器/负载？

三项都确认后才能运行 `demo confirm-bench` 和 `hil`。不要替客户猜端口，也不要在客户确认烧录前
打开串口写设备。

## 3. 命令序列

以下命令都在仓库根目录执行。`<项目名>` 由客户指定，重复会报错，不会覆盖旧项目。

模式 A（无硬件）只要四条：

```powershell
./tools/plcweave.ps1 demo start demo-run --not-connected
./tools/plcweave.ps1 simulate project/demo-run
./tools/plcweave.ps1 demo status project/demo-run
./tools/plcweave.ps1 demo deliver project/demo-run --version V001
```

模式 B（接硬件）按 D1–D6 走完整序列：

```powershell
# D1/D2：建项目、冻结、生成程序。把端口参数换成客户给的；
# 客户在模式 B 里改口“没接 PLC”时，改用 --not-connected（其余步骤同模式 A）。
./tools/plcweave.ps1 demo start <项目名> --port COM7 --baud 9600 --parity N --station 1

# D3：执行冻结用例，生成 MAIN.csv / COMMENT.csv / 仿真报告
./tools/plcweave.ps1 simulate project/<项目名>

# 查看进度和下一步
./tools/plcweave.ps1 demo status project/<项目名>
```

`demo start` 会先写 `requirements.md`、`test_cases.md` 并冻结，再写 `source.fxil`；这不是为了
走形式，而是保证 S1 冻结确实早于程序。串口参数会同时写入程序的 `D8120/D8121` 和
`bench_config.json`，避免“程序里一套、台架上一套”。

## 4. D4：客户烧录（人工）

候选文件在 `project/<项目名>/candidate/V001/`：

- `MAIN.csv`：指令表，按 GX Works2 列表导出方言生成（引号制表符、CRLF）；
- `COMMENT.csv`：软元件注释（制表符、CRLF）；
- `source.fxil`：程序源在**项目根目录**（不在 `candidate/V001/`）。

**能力边界：** 本仓没有经过验证的 L01S 编译/下载器，也不声称已在你的 GX Works2 中完成导入。
`MAIN.csv` 的方言已能被本仓 GX 列表解析器读取，但厂商导入/编译结果由客户现场确认和报告。

步骤：

1. 用你现场的 GX Works2 导入或转换 `MAIN.csv`/`COMMENT.csv`；若版本不兼容，用
   `source.fxil` 的 `#instructions` 段按你的工具支持的格式导入。导入和编译结果由客户报告，
   本工具不独立验证。
2. 通过编程口（通常 `COM5`）只下载应用层程序；不修改原厂运行固件，本工具不提供下载器。
3. 切到 RUN，确认 `D196=1`、`D197=41`、`D198` 持续变化、`D193=0`、`Y0=0`。
4. 客户明确回复：**“已烧录并 RUN，编译结果 …，GX Works2 版本 …，操作者 …”**。
5. Agent 才执行（把编译结果和 RUN 状态换成客户原话/实际值）：

```powershell
./tools/plcweave.ps1 demo confirm-flash project/<项目名> --operator <姓名> --software "GX Works2 <版本>" --compile-status "<客户报告>" --run-state RUN
```

这一步会把当前源/测试哈希、操作者、GX Works2 版本、编译/RUN 状态和时间写进
`manual_download.json`。没有这条记录，S6 不能写设备，总结报告也不会写“达到演示验收要求”。
同一条确认记录不能重复覆盖；确需重新确认时加 `--force`，并在报告/沟通中说明原因。

## 5. D5：S6 硬件在环

前提：PLC 已烧录并 RUN；USB-RS485 接在 Modbus 口（不是编程口）；现场是**隔离空机**，
不接传感器、执行器、变频器或负载。先记录这三项确认：

```powershell
./tools/plcweave.ps1 demo confirm-bench project/<项目名> --operator <姓名> --isolated-bench --rs485-connected --plc-running
```

然后：

```powershell
./tools/plcweave.ps1 preflight project/<项目名>
./tools/plcweave.ps1 hil project/<项目名> --isolated-bench
```

- `confirm-bench` 把台架/485/RUN 确认与源/测试哈希绑定；演示项目没有它会拒绝 `hil`。
- `preflight` 只读身份和心跳；失败会写 `TEST_INFRA_ERROR`，不会写寄存器。
- `hil` 只写白名单注入寄存器，结束恢复停止态并回读。
- 轮询只能证明稳态标量。报告会把抽样通过和正式 PASS 分开写；逐扫描时序、端子电气、带载
  和掉电保持保留为 UNVERIFIED。

## 6. D6：打包交付

```powershell
./tools/plcweave.ps1 demo deliver project/<项目名> --version V001
```

输出：

```text
project/<项目名>/delivery/V001/
project/<项目名>/delivery/<项目名>-V001.zip
```

ZIP 内至少包含约定的六项：

| 文件 | 内容 |
| --- | --- |
| `requirements.md` | 需求文档（演示场景） |
| `test_cases.md` | 测试用例文档 |
| `MAIN.csv` | 程序指令表（CSV） |
| `COMMENT.csv` | 寄存器/软元件注释（CSV） |
| `HIL-REPORT.md` | 硬件在环报告：哪些完成、哪些未测试 |
| `SUMMARY.md` | 总结报告：项目完成度、是否达到演示要求 |

另附 `MANIFEST.md`（SHA256 清单）、`source.fxil`、`s1-freeze.md`、`build_identity.json`、
`simulation_report.json`；有烧录/台架确认时附 `manual_download.json`/`bench_ready.json`，
有 S6 报告时附 `hardware_report.json`。

### 完成度怎么算

- 需求与冻结用例：20 分；
- 本地仿真：30 分，按 MUST 用例 PASS 比例；
- S6 抽样：40 分，按抽样 PASS 比例，未执行记 0；
- 交付包装：10 分。

因此：

- 只做仿真、不接硬件：60%，结论“未达到演示验收要求”；
- 仿真 + 烧录确认 + 台架确认 + S6 抽样全通过 + 清理回读为零：100%，结论“达到演示验收要求，
  正式验收未评估”；
- 正式 PASS 需要合格采样/观测块与电气、带载证据；工具只报告导入的 S6 报告字段，不独立验证
  电气/带载证据。演示不冒充正式验收。

## 7. 常见情况

| 情况 | 处理 |
| --- | --- |
| 客户不想接硬件 | 用 `--not-connected`；照常打包，S6 写“未执行”，完成度 60% |
| GX Works2 导入失败 | 本工具不保证厂商导入；改用 `source.fxil` 的 `#instructions` 段或按你的 GX 版本转换，并如实记录“未导入成功”，不要改冻结预期 |
| PowerShell 禁止脚本 | 改用 `./.venv/Scripts/python.exe -m plcweave ...`，不要改全局执行策略 |
| 想放外部目录 | `demo start` 加 `--directory D:/路径/项目`；ZIP 名按目录名生成，不一定是 `<项目名>` |
| 端口打不开 | 检查 USB-RS485 驱动、COM 号是否被占用；不要改程序预期 |
| `preflight` 身份不符 | 说明烧录的不是当前版本，或 D196/D197 不匹配；停止，不写设备 |
| 客户临时改波特率/校验/站号 | 重新建一个项目重新烧录；不要只改 `bench_config.json` 造成程序与台架不一致 |
| 交付版本已存在 | 换新版本号；工具不覆盖旧交付 |
| 只想看文档 | 直接读 `demo/scenario/` 下的需求、用例和程序模板 |

## 8. 安全边界

- 演示只用软元件与隔离输出，不驱动真实负载；不接安全回路。
- 客户未明确确认烧录前，不打开串口写设备。
- 不把 `PROTOCOL_READ_PASS` 或“抽样检查 PASS”写成应用行为、电气或带载 PASS。
- 仓库里的 `project/` 案例不参与本演示；每次演示新建自己的项目目录。
