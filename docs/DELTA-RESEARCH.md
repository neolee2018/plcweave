# 台达 DVP 官方资料核查笔记

核查日期：2026-10-26。范围：优先 DVP-ES2、DVP-SA2、DVP-SX2；SS2 仅作同族参照；AS/AH 为后续独立适配范围。

task_id：delta-primary-research-20261026；owner：Codex 独立资料研究上下文；时限：本轮研究；资源：官方网页与搜索索引、本文。本文不代表软件编译、模拟器或硬件测试通过，不是可直接启用的设备映射。

## 证据等级与本轮限制

- **A／官方全文**：已打开官方网页或 PDF 全文，可核查上下文。
- **B／官方索引片段**：搜索结果指向厂商拥有的 PDF，能核实所列文字及印刷页码，但本轮直开手册被官网 `terms-of-use/verify` 重定向阻断。表格列对齐、脚注、型号适用性尚未完成原页截图核验。
- **U／未证实**：没有取得足以支持结论的一手证据，必须留给指定版本厂家软件离线试验或授权硬件试验。

本轮只采用 `deltaww.com`、`filecenter.deltaww.com` 的证据。搜索过程中出现的第三方教程、手册转载均未用作结论来源。已尝试官方 PDF 截图请求；可读目录的截图调用未返回可供本上下文目视核对的图像，受阻手册也未取得截图。因此下文所有寄存器和地址表均保留 B 级，不能当作已核验可写映射。未绕过网站条款入口，未下载或向仓库加入厂商手册。

## 1. 型号和软件边界

| 事项 | 核查结果 | 证据／置信度 |
| --- | --- | --- |
| 首批系列命名 | 官方目录用 **DVP-ES2**、SA2、SX2。完整料号中存在 `DVP32ES200RC/TC` 等 `ES200` 字段；没有找到独立“DVP-ES200”系列的证据。不能只凭口语“ES200”判断全部规格。 | [S1] 印刷 p5、p6、Ordering Information；A，高。 |
| WPLSoft 范围 | 目录将 WPLSoft 列为 DVP 系列编程软件。该表不是“任意新旧 DVP 型号均支持”的保证。ES2/SA2/SX2 应按具体 CPU、固件和软件版本锁定。 | [S1] p48；A，高。 |
| ISPSoft 范围 | 同一目录将 ISPSoft 列为 AH、AS、DVP 的软件；官方 FAQ 也确认 DVP 可用 ISPSoft。不同系列能选的语言及系统功能不能从总宣传表直接外推。 | [S1] p48、[S2]；A，高。 |
| AS/AH | 应作为独立目标做指令、存储、系统位和工程配置核验。软件相同并不说明 DVP 工程或寄存器可以直接套用。 | 前半为官方软件范围；“独立目标”是工程建议，并非厂家迁移承诺。 |
| 新 DVP 反例 | ES3 官方手册明确不使用 WPLSoft；2024 编程手册还区分 ES300TEC/EX3/SV3/SX3 只使用 DIADesigner。故“DVP”不能充当唯一软件兼容条件。 | [S3] §1.1.1，p1-2；B，中高。 |

[S1] [Delta DVP Series catalogue，2022-09-06](https://www.deltaww.com/IA/downloadcenter/catalogue/3.Control/DVP/DELTA_IA-PLC_DVP_TP_C_EN_20220906.pdf)。原文短摘：`Programming software for DVP Series`（6 words）。

[S2] [Delta FAQ 551：ISPSoft／WPLSoft 差异](https://www.deltaww.com/zh-TW/service-support/faq/551)。官方页面说明 ISPSoft 有任务、功能块和变量声明，并向下兼容 WPLSoft；不能据此声称存在公开的 `.dvp` 文件生成规格。

[S3] [DVP-ES3/EX3/SV3/SX3 Programming Manual，2024-03-06](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_DVP-ES3-EX3-SV3-SX3_PM_EN_20240306.pdf)。

## 2. 程序进入厂家软件的真实通路

| 通路 | 官方已取得证据 | 尚不能声称的能力 |
| --- | --- | --- |
| WPLSoft 原生工程 → ISPSoft | ISPSoft 手册的 Open previous project 表列出 `WPL Files (*.dvp)`；打开并保存后转换成 `.isp`。 | 不能把“能打开既有 `.dvp`”说成 PLCWeave 已能生成 `.dvp`，也不是 `.txt`／GX CSV 导入。 |
| ISPSoft POU 导入／导出 | 手册确有 §5.4.5 Exporting POU Program、§5.4.6 Importing POU Program。 | 本轮未核实包内格式、扩展名、可否由外部直接生成、任务绑定及不同 CPU 的兼容性；不得把任意 IL 文本改扩展名当 POU。 |
| ISPSoft Export Programs to Text | §2.3.3 明确用途为专利申请，不能从这种导出文本恢复程序。 | 不能用它设计“导出文本→改写→导入”的往返管线。 |
| ISPSoft IL 编辑器 | 2020 手册目录明确存在第12章 Instruction List，含结构、注意事项、编辑 IL。 | 未取得该版本相关正文，尚不能确定 ES2/SA2/SX2 的语言选择、直接文件导入、剪贴板规则或完整语法。 |
| WPLSoft 指令表文本 | 官方 TP70P Quick Start 明确 WPLSoft User Manual 可在 WPLSoft 内找到。 | 本轮未找到公开的正式纯文本导入／导出格式说明；“没有找到”不等于“软件没有”。需检查实际安装版本的 Help 与离线编辑器。 |

证据：[S4] ISPSoft User Manual 2021-03-29，p1-2、Open previous project p2-21、§2.3.3 p2-41、§5.4.5–5.4.6 p5-25–5-26（B，中高）；[S5] 2020-03-12 版第12章目录，§12.1.1 p12-2、§12.1.3 p12-5、§12.2.2 p12-8（B，中）；[S6] TP70P Quick Start §1.2 p1-2（B，中高）。

[S4] [ISPSoft User Manual，2021-03-29](https://filecenter.deltaww.com/Products/download/06/060302/Manual/DELTA_IA-PLC_ISPSoft_UM_EN_20210329.pdf)。原文短摘：`would not be able to revert back to programs`（9 words）。

[S5] [ISPSoft User Manual，2020-03-12](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_ISPSoft_UM_EN_20200312.pdf)。

[S6] [TP70P Quick Start，2022-10-06](https://filecenter.deltaww.com/Products/download/06/060302/Manual/DELTA_IA-TP_TP70P_Q_EN_20221006.pdf)。

**必须做的离线探针（建议，不是完成记录）**：记录 WPLSoft／ISPSoft 实际版本、CPU 类型与固件选项；人工创建最小原生工程；测试单个触点、输出、TMR、计数器、常数、注释、嵌套分支的输入方式；保存重开并编译；再从厂家软件导出样本研究格式。分别保留失败文本与错误信息。语法、编码、换行、常数表示、结束标记和任务分配必须通过样本确定。GX Works CSV 不能称为 Delta 导入文件。候选节号“2.14.1 Importing from a Text File”未找到可靠官方来源，本文不采用。

## 3. DVP 通信映射：候选资料与危险断点

官方 DVP Application Manual §2.12 p2-135、后续页，以及 Starter Kit §4.4.2 p4-15–4-16 给出设备通信地址。后者有效范围栏只针对 SS2／SE，不能拿它单独证明 ES2／SA2／SX2 的可用上限。[S7][S8]

以下是 **B 级候选 PDU 偏移**，仅供后续原表核验和测试设计：

| 设备 | 候选规则 | 必须核验的限制 |
| --- | --- | --- |
| X / Y | X0 起 `0x0400`；Y0 起 `0x0500`；X/Y 编号按八进制解释 | 不等于实物拥有全部 X0–X377／Y0–Y377；X 通常按离散输入读。 |
| S | S0 起 `0x0000` | 不可默认所有 S 可被测试写入。 |
| T | T0 起 `0x0600`，同号有 bit 状态及 word 当前值 | 功能码决定访问空间，不能把位状态与当前值混成一个变量。 |
| M | M0–M1535 对应 `0x0800`–`0x0DFF`；M1536 起跳 `0xB000` | **不是全范围 `0x0800 + n`**；M1000 起有系统位。 |
| D | D0–D4095 对应 `0x1000`–`0x1FFF`；D4096 起跳 `0x9000` | **不是全范围 `0x1000 + n`**；型号有效范围另查。 |
| C | 16／32位计数器有状态、word／double-word 的不同映射 | 官方索引出现混排和疑似错行，本轮不给可执行公式。 |

表中 `404097` 等六位 Modbus 参考号不是报文内直接发送的起始地址；例如 D0 的原始偏移为 `0x1000`。实现时需将“参考号、零基 PDU 偏移、功能码、位／字宽度”分开验证；这是基于官方表的工程解释。高地址断点、八进制 X/Y、32位顺序均需边界用例；未完成前禁止以公式猜写设备。

[S7] [DVP-PLC Application Manual，2022-04-07](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_DVP-PLC_PM_EN_20220407.pdf)，§2.12 p2-135 起；B，中。索引在 S256、D255 边界等处存在可疑文本，必须回看原页，不能机械抄录。

[S8] [DVP Starter Kit Manual，2024-08-12](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_DVP-StarterKit-UT-14SS2-A1_OM_EN_20240812.pdf)，§4.4.2 p4-15–4-16；B，中。只作为同族地址断点交叉证据。

## 4. ES2／SA2／SX2 通信和系统位

2024 同族编程手册 §2.8、§2.13、§2.16 的官方索引支持以下规则，但仍须原表截图复核。[S9]

- M1002 是 RUN 激活时的单次正脉冲；不是 FX 首扫位地址。M1000 为运行监视常开触点。不可把 FX 的 M8000／M8002 等名称照搬。
- D1120 表示 COM2 通信格式；D1121 为 COM1／COM2 站地址。M1120 为 COM2 格式保持，M1143 选择 RTU。仅设置 D1120 不能证明已进入 RTU。
- 手册要求 RTU 使用 8 数据位；串口、站号、波特率、校验、停止位及保持位需一致。D1120 默认 H86 不能当成“默认 RTU”。
- SA2 的 COM3 为 RS-485；SX2 的 COM3 为 USB 从站，不支持 I160 通信中断。不要用统一 COM3 写入流程。
- ES2-C 与普通 ES2 还需区分：手册注明 ES2-C 无 COM3，且固件 V4.0 以后不支持 600bps。完整料号与固件是连接前的必要输入。

[S9] [DVP-ES2/EX2/EC5/SS2/SA2/SX2/SE/SE2 & TP Operation Manual – Programming，2024-10-31](https://filecenter.deltaww.com/Products/download/06/060302/Manual/DELTA_IA-PLC_DVP-ES2-EX2-EC5-SS2-SA2-SX2-SE-SE2-TP_PM_EN_20241031.pdf)，SA2/SX2 p2-8；D1120/D1121 p2-53；COM Port Function p2-76；B，中高。原文短摘：`RTU supports 8 data bits only`（6 words）。

## 5. 与 FX 不能共用默认值的语义

以下项目是同族官方资料能支持的差异检查项；不能从“助记符看起来相近”推断程序行为相同。

| 项目 | 官方资料发现 | 适配含义 |
| --- | --- | --- |
| 定时器指令 | 示例使用 `TMR T0 K100`；100ms 时为10秒。普通计时器失能清零，积算型中断计时保留。 | 不把 FX 的 OUT Tn 语法直接输出为 Delta；时间基数、断电／失能行为要显式建模。 |
| 时间基数 | T127 为1ms；T246–T249 为1ms积算；T200–T245 有10ms／1ms选择；T64–T126 受 M1028 影响。 | 编译器需按计时器编号和模式计算，不能统一假定100ms。 |
| 扫描时序 | 手册写计时器在 END 更新；T184–T199 是副程序／中断专用计时范围。 | 扫描模型、跳转／副程序中的计时更新必须单独验证。 |
| 保持区 | SA2/SX2 表把 D408–D599、D2000–D3919列为保持区；D1000–D1999为特殊区，部分保持。 | HIL邮箱不能随意选 D1000 起；冷启、STOP→RUN、断电恢复不能沿用 FX 默认。 |
| 型号差异 | ES2 普通32位计数器到 C231；SA2/SX2 到 C232，后续高速计数器分界不同。 | 同族共用解析器可以，地址能力表仍需独立。 |
| 地址和扩展 | X/Y 八进制；SA2/SX2 的 D9800以上关联扩展模块。 | 资源分配需排除系统／模块保留区，并确认实际模块占用。 |

来源：[S10] 2023-12-21 同族手册 §2.1 p2-2、§2.10 p2-30（定时行为）；[S11] 2022-08-19 §2.3 p2-6–2-7（SA2/SX2 保持、计数器、端口）；[S12] 繁体2023-01-04 §2.1 p2-2、§2.3 p2-8（时基、保持与端口交叉核查）。全部 B，中；表格的最终数值必须以原页和具体固件复核后冻结。

[S10] [DVP 同族编程手册，2023-12-21](https://filecenter.deltaww.com/Products/download/06/060302/Manual/DELTA_IA-PLC_DVP_ES2-EX2-EC5-SS2-SA2-SX2-SE-TP_PM_EN_20231221.pdf)。

[S11] [DVP 同族编程手册，2022-08-19](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_DVP-ES2-EX2-SS2-SA2-SX2-SE-TP_PM_EN_20220819.pdf)。

[S12] [DVP 同族操作手册程式篇，2023-01-04](https://filecenter.deltaww.com/Products/download/06/060301/Manual/DELTA_IA-PLC_DVP-ES2-EX2-EC5-SS2-SA2-SX2-SE-TP_PM_TC_20230104.pdf)。

## 6. 尚未完成的证据门

1. 从合法可访问的厂家页面或用户现有资料取得相关原页，目视核验表格列、脚注、读写权限；不把当前 B 级表作为已审定映射。
2. 获取实际 WPLSoft Help／User Manual：正式文本导入是否存在、指令表剪贴板语法、原生 `.dvp` 是否有公开格式，均为 U。
3. 在实际 ISPSoft 版本分别选择 ES2、SA2、SX2，核实 IL／POU 可选模式、最小程序、保存重开和编译，以及 `.dvp` 转换的限制；不从总目录的语言宣传推断每个模式可用。
4. 锁定首块 PLC 完整料号、硬件／固件、通信口和测试邮箱；授权后先只读辨识，再测试邮箱。物理 X 写入、RUN/STOP、真实 Y 动作均不能混入“读取寄存器”的授权。
5. 厂家模拟器与真实硬件分别留证。官方 [FAQ 332](https://www.deltaww.com/en-US/service-support/faq/332) 明确模拟计时受 PC 效率影响、结果不等于实机，且多条通信／高速指令不支持；A，高。

## 结束与资源清理

本轮实际完成：官方软件边界、原生 `.dvp` 打开转换、不可逆文本导出、同族系统位／通信／存储断点的资料定位；未完成原页表格截图复核与厂家软件试验。产物仅本笔记，未改工具代码，未编辑客户程序，未运行厂商 GUI，未连接或写 PLC，未创建后台进程、串口、锁、临时工程或下载文件；cleanup：无本任务新增的系统资源待释放。未产生任何适配 PASS。
