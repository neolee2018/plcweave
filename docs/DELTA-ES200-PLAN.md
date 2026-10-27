# 台达 DVP-ES200 适配方案（规划稿）

日期：2026-10-26。状态：**规划，未实施**。在适配实际完成并验证前，AGENTS.md/README 中
"台达适配未实现"的表述保持不变；本文不宣称任何已完成能力。

目标一句话：让"一条提示词 + 两阶段工作流"对**台达 DVP-ES200**走通与 L01S 同等深度的链路：
MD 需求/用例 → 冻结 → 台达指令表源 → 本地仿真 → ISPSoft 人工烧录 → COM2 RS485 Modbus RTU
受控采样 → 交付 ZIP。自动下载器、厂商软件再分发、削弱安全确认门都不在范围内。

## 0. "兼容 ES200"的验收定义

| 层 | 验收标准 | 不要求 |
| --- | --- | --- |
| S0/S1 | requirements.md/test_cases.md/design.md 对 `target: delta-es200` 可用，冻结与复核门复用 | 用例格式品牌化 |
| S2/S3 | `source.dvpil`（台达助记符）经静态校验与本地扫描仿真执行，冻结用例 SIM_PASS；未知指令 BLOCKED 不 NOP | 全指令集覆盖；与 ISPSoft 仿真等价 |
| S4 | 生成 ISPSoft/WPLSoft 可导入的指令表交付物（导入通路经 WP0 核实），双版（HIL/正式）同核 | 自动生成 .dvp 工程文件 |
| S5 | 客户在 ISPSoft 编译下载并确认（人工，同 GX Works2 路径边界） | 自动下载 |
| S6 | COM2 RS485 Modbus RTU：身份绑定→白名单注入→采样比较→清理回读，隔离空机 | 逐扫描时序/电气/带载（仍 UNVERIFIED） |
| S7 | delivery/<版本>/ + ZIP + 完成度报告，无硬件口径 60% | 冒充实机验收 |

## 1. 事实基线（已核实 / 待核实）

### 已核实（2026-10-26 网络检索，公开来源）

| 事实 | 来源 |
| --- | --- |
| ES200 属 DVP 系列；Delta 官方编程软件为 ISPSoft（IEC 61131-3，支持 LD/FBD/SFC/ST/IL），WPLSoft 为传统工具 | [Delta ISPSoft 产品页](https://www.deltaww.com/en-US/products/PLC-Programmable-Logic-Controllers/3598)、[Delta FAQ 326](https://www.deltaww.com/en-US/service-support/faq/326) |
| ISPSoft 可 File > Import > WPLSoft 工程（*.dvp），带逐条转换日志，个别指令需手工修 | [ISPSoft/WPLSoft 入门说明](https://industrialmonitordirect.com/blogs/knowledgebase/getting-started-with-delta-wplsoft-and-ispsoft-for-dvp-and-as) |
| DVP 系列 COM2 为 RS485、可作 Modbus ASCII/RTU 从站；串口格式特殊寄存器 D1120、站号 D1121、M1120 锁存协议设置、M1143=ON 选 RTU；通信端口 COM1(RS232)+COM2(RS485) | Delta 下载中心 DVP-ES/EX 系列手册（编程/通信章节） |

### 待核实（WP0 清单，全部以官方手册页码为准，不得凭印象写进代码）

1. **WPLSoft 是否支持 ES200**（当前判断：很可能仅 ISPSoft ≥ 某版本；决定 S4 导出主通路是
   WPLSoft 指令表 TXT → .dvp → ISPSoft 导入，还是 ISPSoft IL/LD 直接粘贴/人工录入）。
2. ES200 的 D1120 位定义表、默认 COM2 参数（DVP 惯例 ASCII 9600,7,E,1 站 1；RTU 位组合值）
   及 DIP 开关对通信/RUN 的影响。
3. ES200 Modbus 地址映射表（D、M、Y、X 各银行起始与范围；DVP-ES2 惯例是 D/M 分段映射，
   不同于 L01S 的 D→保持寄存器平铺；D196-D202 身份字换算后的实际 Modbus 地址）。
4. 指令子集事实：TMR/CNT 的编号分组与基准（100ms/10ms/1ms 段）、M1000/M1002 等特殊继电器
   语义（候选对应 M8000/M8002）、X/Y 编号制（8 点一组？）、保持区边界（D 哪段断电保持）、
   立上升/下降沿指令形式（LDP/LDF 或 LDP/ANDF…）与 FX 差异。
5. 与 100-dvp-pid-water 客户现场（DVP-EX/EX2 + WPLSoft）指令兼容性：ES200 是否完全向后
   兼容 DVP 指令集、有无删改。

## 2. 现有品牌耦合点盘点（代码级）

| 位置 | 现状 | ES200 需要什么 |
| --- | --- | --- |
| `src/plcweave/fx.py` | fxil 解析（助记符中性）+ **GX Works2 列表方言** CSV 导出（UTF-16，"FXCPU FX3U/FX3UC" 头） | 解析框架可复用；导出走独立 Delta 生成器 |
| `src/plcweave/testing.py` | `simulate()` 绑定 `gxwlib.load_csv(..., device_profile="fx")` + `profile="fx3u"`；engine_gate 夹具为 FX 风格 | 按 target 分发到 Delta 执行器；engine gate 同纪律 |
| `src/plcweave/hil.py` | Modbus RTU 客户端通用；但 D→保持寄存器**平铺直读**（D196 即 HR196）、M 线圈映射 `M0-7679→0..7679`、`M8000-8511→0x1E00+`、`Y→0x3300+八进制`（均为三菱/L01S 惯例）；`ALLOWED_WRITES` 为 L01S 演示白名单 | Bench 增加地址映射 profile；白名单来自 design 表；身份/心跳寄存器地址按 ES200 映射换算 |
| `src/plcweave/variants.py` | `_internal` 限定 M≤7679/D<8000 且排除 D196-D202；`_physical` 限定 L01S 特定 D8030+/D8050+；`read_design` 显式拒绝 Delta；`render_variant` 渲染 FX 特殊寄存器（M8002/M8196/M8125/D8120/D8121/M8000） | target 注册表加 `delta-es200`；设备表、物理表、变体前导（M1002/D1120/D1121/M1143/M1120）全部按 profile 参数化 |
| `src/plcweave/workflow.py` | `from .demo import serial_format`（FX D8120 编码）硬依赖 | 串口字编码按 target（D1120 位表） |
| `src/plcweave/demo.py` + `demo/scenario/` | 场景模板为 FX 助记符与 D8120/D8121/D196-D202 惯例 | Delta 场景模板变体；身份寄存器惯例可沿用（100 项目已实战 D196/D197） |
| `skills/.../SKILL.md` 及 references | FX/L01S 视角 | 增加 delta-es200 目标章节 |

正面条件：MD 用例模型、冻结/复核门、比较器与 TraceOracle、构建/交付/ZIP、demo 编排、
pymodbus 客户端本身都是品牌中立的，**全部直接复用**；100-dvp-pid-water 的
D196/D197 版本寄存器惯例与本仓 HIL 身份方案（D196-D202）天然一致。

## 3. 目标架构：TargetProfile 适配层

```text
target profile（注册表）
  ├── l01s        （现有，行为不变）
  ├── fx3u        （现有，行为不变）
  └── delta-es200 （新增）
        ├── 指令签名表 + 设备表（M/D/X/Y/T/C 范围、八/十进制、特殊区、保持区）
        ├── 仿真引擎绑定（Delta 扫描执行器，Python；未知指令 BLOCKED）
        ├── 导出方言（WPLSoft/ISPSoft 指令表 TXT，通路按 WP0 结论）
        ├── Modbus 映射（D/M/Y→Modbus 地址函数；身份/心跳寄存器方案）
        ├── 串口配置（D1120 位表编码、D1121、M1143/M1120、台架默认参数）
        └── 变体前导/物理表（M1002 初始脉冲、测试注入层、X/Y 物理映射）
```

原则：`simulate()/export/Bench/render_variant` 一律先查 profile 再执行；profile 缺项即
UNSUPPORTED，绝不静默回退到 FX 行为。FX 两个既有目标的所有现有测试保持绿色。

## 4. 复用资产与引入规则

| 来源 | 可复用 | 边界 |
| --- | --- | --- |
| `100-dvp-pid-water/tools/`：`dvp_parser.py`（.dvpil 解析）、`check_dvp_il.py`（静态校验+寄存器占用审计）、`gen_dvp_il.py`（WPLSoft 指令表 TXT 生成，**客户实验室已验证可导入**）、`sim_dvp.py`（扫描仿真+场景） | WP2/WP3 直接起点，显著降低工作量 | 只复用工具代码，**不带任何客户程序内容**（bn.dvp、pid pressure.txt 等留在原项目）；按 AGENTS.md 合并规则登记来源、commit、许可、哈希与修改范围 |
| `100-dvp-pid-water` 现场经验 | D196/D197 身份字先例、WPLSoft 导入注意事项、寄存器占用审计思路 | 经验条目化后进技能 references，不搬原始记录 |
| `vendor/gxwlib`（FX 引擎） | 不动，继续服务 l01s/fx3u | 不给 gxwlib 加 Delta 支持（避免污染上游基线） |
| `101-gxworks-agent` / `102-plc-s2-engine` / `20-modbus-hc` | 本方案不需要新动 | 维持现状 |

## 5. 工作包分解

> 工作量为粗估（人日，含测试与文档，不含四独立复核的等待时间）；TBD 项在 WP0 后修正。

### WP0 事实库建设（1–2 天，无代码，可立即开始）

- 通过官方渠道获取 DVP-ES200 编程手册、通信手册（只登记版本/页码引用，手册文件不进仓库）。
- 逐项核对第 1 节"待核实"清单，产出 `docs/es200-facts.md`：每条事实附手册名、版本、页码。
- 同时确认目标硬件：ES200 具体型号/点数、是否需要 USB-RS485 之外的配件、台架条件。
- **验收**：第 1 节所有待核实项闭合；导入通路（WPLSoft TXT vs ISPSoft 导入 vs 人工）定稿。

### WP1 TargetProfile 抽象层（2–3 天）

- 新建 `src/plcweave/targets.py`（或 targets/ 包）：profile 注册表与查询接口。
- 把 `testing.simulate`、`fx.export` 调用、`hil.Bench` 地址映射、`variants.render_variant`、
  `demo.serial_format` 改为经 profile 分发；l01s/fx3u 行为逐字节不变。
- **验收**：现有 137 项测试全绿；`target: delta` 在注册表缺席时给出明确的 UNSUPPORTED 错误
  （替换 variants.py 中现有硬编码拒绝）；新增 profile 注册/查询的单元测试。

### WP2 Delta 指令子集与本地执行器（4–6 天）

- 以 `dvp_parser.py`/`sim_dvp.py` 为起点，移植为 plcweave 内的 Delta 执行器，接到统一用例
  模型（frozen_suite、TraceOracle、compare）与统一报告结构。
- 首个子集对齐演示与两阶段共同核所需：LD/LDI/AND/ANI/OR/ORI/ANB/ORB/MPS/MRD/MPP、
  OUT/SET/RST、TMR/CNT、MOV/ADD/SUB/MUL、CMP/触点比较、END、M1000/M1002 等特殊继电器。
- 每条指令：先写语义微测试（依据 WP0 手册页码），再实现；执行器 engine gate 与 FX 同纪律
  （BOGUS/越界/未实现一律 BLOCKED）。
- **验收**：Delta 目标的合成夹具用例 SIM_PASS；未知指令 fixture 全部 BLOCKED；寄存器占用
  审计（复用 check_dvp_il 思路）跑通。

### WP3 导出方言与导入通路（2–3 天）

- 移植/适配 `gen_dvp_il.py` 为 ES200 profile 的导出器（CRLF/ASCII 指令表 TXT + 注释表）。
- 按 WP0 定稿的通路生成对应交付物（如需 .dvp 中转，文档写清客户侧两步操作）。
- **验收**：导出物被本仓 Delta 解析器回读一致（往返测试）；导入/编译结果仍由客户现场确认
  并记录（同 GX 路径边界，不宣称"已验证导入"）。

### WP4 ES200 Modbus HIL 适配（3–4 天 + 台架时间）

- `Bench` 地址映射参数化：D/M/Y→Modbus 地址换算按 ES200 映射表；身份/心跳沿用
  D196-D202 惯例（地址经映射换算）；注入白名单来自 design 表而非硬编码。
- HIL 变体前导 Delta 化：M1002 初始脉冲写入身份字；D1120/D1121/M1143/M1120 渲染串口配置
  （等价于 FX 变体里的 D8120/D8121）；串口格式编码函数按 D1120 位表（WP0）。
- 台架默认参数进 profile（如 RTU 9600/8/E/1 站 1，按手册修正）。
- **验收**：`preflight` 只读身份/心跳；`hil --isolated-bench` 白名单注入+回声确认+清理回读；
  未确认烧录/台架前不打开串口（与 L01S 完全同门）。

### WP5 两阶段工作流目标扩展（2 天）

- `variants.read_design` 接受 `target: delta-es200`；`_internal/_physical` 设备表按 profile；
- `render_variant` 双版（HIL/正式）渲染 Delta 助记符；测试注入层结构与 HBDTECH 建议一致
  （正常模式走物理 X/AI，测试模式走注入 D，共用同一控制核）。
- **验收**：同一控制核生成两版、各自本地回归、同版全 PASS 才允许第二阶段打包（沿用现有门）。

### WP6 演示场景 Delta 变体（1–2 天）

- `demo/scenario/` 增加 Delta 模板；`demo start --target delta-es200`（默认仍 l01s）。
- 根 PROMPT.md 无需改写——提示词只说"跑演示"，目标由参数选择。
- **验收**：无硬件模式 ES200 演示链路一次跑通，完成度 60%，S6 写"未执行"。

### WP7 文档/技能/状态更新（1 天）

- SKILL.md 与 references 增加 delta-es200 章节（含导入通路操作卡、串口参数表）；
  README 双语、BLUEPRINT/ROADMAP、AGENTS.md 状态行按**实际完成度**更新（能力声明如实）。

### WP8 验证与评审计划（贯穿）

- 每个 WP 完成后走仓库既定四独立上下文复核门（S1 冻结、S3、S6 结论、交付前）。
- 回归策略：FX 路径全量测试每轮必跑；Delta 路径建立黄金用例库（指令语义微测试+端到端）。
- 真机验收标准：身份四对齐→只读预检→白名单注入回声→采样比较→清理回读为零；
  `PROTOCOL_READ_PASS` 不等于行为通过；逐扫描/电气/带载保持 UNVERIFIED。

## 6. 里程碑

| 里程碑 | 内容 | 前提 | 完成后能说什么 |
| --- | --- | --- | --- |
| M1 | WP0+WP1 | 无 | "适配层就绪，FX 行为不变" |
| M2 | WP2+WP6 | M1 | "ES200 目标本地需求→仿真→打包全链路可用（完成度 60% 口径）" |
| M3 | WP3+WP5+WP7 | M2 | "ES200 两阶段第一阶段交付可用；导入通路已文档化，编译由客户确认" |
| M4 | WP4 | M3 + **ES200 真机 + USB-RS485 隔离台架 + 客户授权** | "ES200 隔离空机 S6 采样完成（稳态标量口径）" |

没有真机时项目停在 M3，交付报告如实写"S6 未执行"——这与 L01S 路径的诚实边界完全一致。

## 7. 总量估计

代码+文档约 **15–21 人日**（WP0–WP7 之和），加 4 道复核门的编排时间；M4 台架工作另行
按现场条件估。若 WP0 发现 WPLSoft 完全不支持 ES200 且 ISPSoft 导入通路受限，WP3 可能
退化为"文档化人工录入"路径，工作量下降但客户侧操作成本上升。

## 8. 主要风险与决策点

1. **导入通路不确定**（最大风险）：WPLSoft 大概率不支持 ES200；.dvp→ISPSoft 导入是否
   允许目标为 ES200 待 WP0 验证。备选：ISPSoft IL 编辑器粘贴/人工录入（照 100 项目经验，
   纯指令表录入量可控）。**决策点在 M1 末，WP0 收口时。**
2. **DVP→ES200 兼容性假设**：100 项目经验基于 ES2/EX2；指令语义/编号分组若有差异，以
   WP0 手册为准逐条对照，不搬运未核实的 ES2 结论。
3. **Modbus 映射银行化**：D/M 分段映射比 L01S 平铺复杂，读块合并、125 寄存器上限与
   跨银行问题需在 WP4 单测覆盖；身份字实际地址必须由映射函数计算而非硬编码。
4. **执行器双轨**：FX 走 gxwlib、Delta 走 Python 执行器，两套引擎能力清单分开记账
   （沿 BLUEPRINT 第 4 节验证等级），不得互相冒充。
5. **范围蔓延**：不做 ST/FBD、不做多机型 Delta 家族泛化（先 ES200 一个 profile）、
   不做自动下载、不做 .dvp 工程文件生成器。
6. **许可与来源**：100 项目工具代码引入前完成来源/commit/许可/哈希登记；客户程序内容与
   厂商手册一律不进公共仓库。

## 9. 立即可做的第一步（不需要写代码）

1. 执行 WP0：拿 ES200 编程/通信手册，闭合第 1 节待核实清单，定稿导入通路。
2. 确认 ES200 真机与隔离台架条件（型号、点数、USB-RS485、授权边界）。
3. 对 100-dvp-pid-water 的 tools 做引入前评估（许可、依赖、代码量、与 plcweave 用例模型
   的接口差距），产出引入登记记录。
