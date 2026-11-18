# V002 PLC 寄存器地址表

本表为 PLC 参数资料，无 UI 或前端实现。唯一程序为 source.fxil；本表覆盖所有显式使用设备、MUL/DIV 隐式相邻结果字，以及未使用 AI 通道。机器可读版 register_map.csv 与本表同源。所有 RO 项禁止 HMI/测试写入；普通内部设备即使可被 Modbus 寻址也不构成授权。

D0 对应 holding offset 0（0x0000），D 的偏移为十进制编号；M0..M7679 对应 coil offset 0..7679；Y0 暂按 coil 0x3300。表中使用零基协议地址，不叠加 40001 显示基址。特殊 M、T 的 Modbus 映射未核实，不得猜地址连接或写入。首次联机必须按具体 L01S 手册核实并先只读验证。

数据字均为 signed16；压力单位 0.1 bar，频率 0.01 Hz，模拟量 raw counts。MUL 结果占低字及相邻高字，32 位低字在前；DIV 占商及相邻余数。各对完全独占，禁止把高字/余数字作其它存储。DIV 的正数输入保证商等于 floor。

## 完整设备表

|设备|空间/零基偏移|权限|类型/单位|首扫默认|范围/编码|含义|
|---|---|---|---|---|---|---|
|M0|coil 0 (0x0)|RO|bit; boolean|0|0/1|Application running latch; remains on during sleep|
|M1|coil 1 (0x1)|RO|bit; boolean|computed; see source|0/1|Valid source mode; zero or one only|
|M2|coil 2 (0x2)|RO|bit; boolean|computed; see source|0/1|Global rising edge of 100 ms clock; evaluated unconditionally|
|M3|coil 3 (0x3)|RO|bit; boolean|0|0/1|Previous scan 100 ms clock image; reset on first scan|
|M10|coil 10 (0xa)|RO|bit; boolean|0|0/1|Pre-sleep state; 20.00 Hz, integral cleared|
|M11|coil 11 (0xb)|RO|bit; boolean|0|0/1|Latched sleep state; frequency and physical outputs zero|
|M12|coil 12 (0xc)|RO|bit; boolean|0|0/1|Invalid-mode restart inhibit; release start in valid mode|
|M20|coil 20 (0x14)|RO|bit; boolean|computed; see source|0/1|Normal state at scan entry; excludes transition scan from PI|
|M21|coil 21 (0x15)|RO|bit; boolean|computed; see source|0/1|Final normal state after command and timer processing|
|M8000|未核实|RO|bit; boolean|computed; see source|0/1|PLC RUN monitor; system owned|
|M8002|未核实|RO|bit; boolean|computed; see source|0/1|First-scan pulse; system owned|
|M8012|未核实|RO|bit; boolean|computed; see source|0/1|100 ms clock; system owned|
|M8125|未核实|RO|bit; boolean|1|0/1|Serial communication mode enable; initialized one|
|M8196|未核实|RO|bit; boolean|1|0/1|Serial peripheral setting enable; initialized one|
|T0|未核实|RO|timer/contact; 100 ms|0; preset 50|0/1|Continuous pre-sleep delay; 100 ms base, preset 50|
|T1|未核实|RO|timer/contact; 100 ms|0; preset 30|0/1|Continuous wake delay; 100 ms base, preset 30|
|Y0|coil 13056 (0x3300)|RO|bit; boolean|0|0/1|Physical route run output; exact D193 enable required|
|D100|holding 100 (0x64)|RO|signed16; 0.1 bar|computed; see source|0..160|Clamped scaled pressure; 0.1 bar, 0 to 160|
|D102|holding 102 (0x66)|RW|signed16; 0.1 bar|validated D261 or 60|10..160|Active pressure setting; 0.1 bar, 10 to 160|
|D110|holding 110 (0x6e)|RO|signed16; integer|computed; see source|0..4000|Selected signed raw input, clamped 0 to 4000|
|D111|holding 111 (0x6f)|RO|signed16; integer|computed; see source|signed16|Rounded scaling numerator; raw plus 12|
|D112|holding 112 (0x70)|RO|signed16; integer|computed; see source|signed16|Pressure scaling DIV quotient|
|D113|holding 113 (0x71)|RO|signed16; integer|computed; see source|signed16|Pressure scaling DIV remainder; paired with D112|
|D114|holding 114 (0x72)|RO|signed16; integer|computed; see source|signed16|Wake threshold MUL low word; setting times 85|
|D115|holding 115 (0x73)|RO|signed16; integer|computed; see source|signed16|Wake threshold MUL high word; paired with D114|
|D116|holding 116 (0x74)|RO|signed16; integer|computed; see source|signed16|Wake threshold DIV quotient|
|D117|holding 117 (0x75)|RO|signed16; integer|computed; see source|signed16|Wake threshold DIV remainder; paired with D116|
|D120|holding 120 (0x78)|RO|signed16; integer|0|0..30000|Integer PI accumulator; 0 to 30000|
|D121|holding 121 (0x79)|RO|signed16; integer|computed; see source|signed16|Signed PI error; active setting minus pressure|
|D122|holding 122 (0x7a)|RO|signed16; integer|computed; see source|signed16|Proportional MUL low word; error times 10|
|D123|holding 123 (0x7b)|RO|signed16; integer|computed; see source|signed16|Proportional MUL high word; paired with D122|
|D124|holding 124 (0x7c)|RO|signed16; integer|computed; see source|signed16|Integral DIV quotient; accumulator divided by 10|
|D125|holding 125 (0x7d)|RO|signed16; integer|computed; see source|signed16|Integral DIV remainder; paired with D124|
|D126|holding 126 (0x7e)|RO|signed16; integer|computed; see source|0..3000|Clamped PI increment; 0 to 3000|
|D130|holding 130 (0x82)|RO|signed16; integer|computed; see source|signed16|Analog route MUL low word; frequency times 4|
|D131|holding 131 (0x83)|RO|signed16; integer|computed; see source|signed16|Analog route MUL high word; paired with D130|
|D132|holding 132 (0x84)|RO|signed16; integer|computed; see source|signed16|Analog route DIV quotient; product divided by 5|
|D133|holding 133 (0x85)|RO|signed16; integer|computed; see source|signed16|Analog route DIV remainder; paired with D132|
|D154|holding 154 (0x9a)|RO|signed16; 0.01 Hz|0|0 or 2000..5000|Frequency command; 0.01 Hz, zero or 2000 to 5000|
|D190|holding 190 (0xbe)|RW|signed16; integer|1|0 or 1 valid; otherwise inhibited|Source mode; 1 test input, 0 hardware AI0|
|D191|holding 191 (0xbf)|RW|signed16; integer|0|1 asserted; other values false|Start level request; only value 1 asserted|
|D192|holding 192 (0xc0)|RW|signed16; integer|0|1 asserted; other values false|Stop level request; only value 1 asserted; stop wins|
|D193|holding 193 (0xc1)|RW|signed16; integer|0|1 asserted; other values false|Physical route enable; only value 1 asserted; defaults zero|
|D194|holding 194 (0xc2)|RW|signed16; integer|0|signed16|Diagnostic external echo request|
|D195|holding 195 (0xc3)|RO|signed16; integer|0|signed16|Diagnostic echo response; copied each executed scan|
|D196|holding 196 (0xc4)|RO|signed16; integer|2|signed16|Program version word; 2|
|D197|holding 197 (0xc5)|RO|signed16; integer|31|signed16|Edition word; 31|
|D198|holding 198 (0xc6)|RO|signed16; 100 ms edge count|0 then edge count|signed16|Heartbeat edge counter; signed word wrap|
|D199|holding 199 (0xc7)|RO|signed16; scan count|0 then increment each scan|signed16|Scan counter; signed word wrap|
|D200|holding 200 (0xc8)|RO|signed16; integer|manifest fingerprint_words[0]|signed16|Canonical instruction fingerprint word 0; signed little endian|
|D201|holding 201 (0xc9)|RO|signed16; integer|manifest fingerprint_words[1]|signed16|Canonical instruction fingerprint word 1; signed little endian|
|D202|holding 202 (0xca)|RO|signed16; integer|2|signed16|Test suite version word; 2|
|D260|holding 260 (0x104)|RO|signed16; 0.1 bar|computed; see source|8..158|Inclusive pre-sleep pressure threshold; active setting minus 2|
|D261|holding 261 (0x105)|RW|signed16; 0.1 bar|retain valid 10..160; else 60|accepted 10..160 at first scan|Saved pressure setting; validated only first scan|
|D262|holding 262 (0x106)|RO|signed16; 0.1 bar|computed; see source|8..136|Inclusive wake threshold; floor active setting times 85 divided by 100|
|D1056|holding 1056 (0x420)|RW|signed16; raw counts|external; not overwritten|signed16|External simulated raw AI0 input; signed word|
|D8030|holding 8030 (0x1f5e)|RO|signed16; raw counts|hardware; not overwritten|signed16|Hardware AI0 raw input; never written by application|
|D8031|holding 8031 (0x1f5f)|RO|signed16; raw counts|hardware; unused|signed16|Hardware AI1 unused; never read or written|
|D8032|holding 8032 (0x1f60)|RO|signed16; raw counts|hardware; unused|signed16|Hardware AI2 unused; never read or written|
|D8033|holding 8033 (0x1f61)|RO|signed16; raw counts|hardware; unused|signed16|Hardware AI3 unused; never read or written|
|D8050|holding 8050 (0x1f72)|RO|signed16; raw counts|0|0..4000|Analog output 0 register route; 0 to 4000|
|D8051|holding 8051 (0x1f73)|RO|signed16; raw counts|0|0|Analog output 1; always zero|
|D8120|holding 8120 (0x1fb8)|RO|signed16; integer|-8063 (HE081)|signed16|Serial format image; HE081, signed -8063|
|D8121|holding 8121 (0x1fb9)|RO|signed16; integer|1|signed16|Serial station image; 1|

## 状态、命令与 PI 参数

状态位组合：M0=0/M10=0/M11=0 为停止；1/0/0 为正常；1/1/0 为预休眠；1/0/1 为休眠。M10 与 M11 不能同时为 1。M12 为内部非法模式重启抑制，并非对外报警编码；本版无独立状态字/报警字。

M 线圈没有对外软按钮写入口，全部只读。软件按钮用 D191 启动、D192 停止，只有值 1 为真，停止优先；D190 仅 0/1 合法。模式非法时停止并锁定重启，恢复合法模式且观察 D191=0 后，之后 D191=1 才能再启动。D193 精确值 1 允许物理输出，首扫为 0；其它值不允许。

PI 为通用整数算法，无私有 PID 系统工作块。固定 Kp=10，积分除数 10，积累范围 0..30000，增量范围 0..3000，基础频率 2000；这些固定参数没有开放 RW 寄存器。D120 及 D110..D133 所用内部计算字均是禁写区。仅 D102 为在线 SV，在线变更不保存 D261。D261 为首扫读取的保存值，真实掉电保持未验证。

诊断 D198/D199 按 signed16 回绕；版本 D196=2、edition D197=31、suite D202=2。D200/D201 精确值以 build_identity.json 为准，不能凭相似指纹认定已烧录。身份核验必须先于任何 HIL 测试写入。

## 首次联机核实清单

- 只读确认 D/M/Y 映射、设备型号、COM7、站号 1、9600/8/N/1；未核实映射不得写。COM5 为人工应用下载通路，本工具不自动烧录。
- 核对当前候选身份、源文件 hash 与新的人工 V002 烧录确认；旧版确认不能沿用。
- D1056 仅在 D190=1 时作为模拟 AI0；硬件 HIL 不写 D8030..D8033，三条本地 ADC 用例保留 local-only。
- 串口初始化只证明寄存器镜像，实际协议/模拟量电压电流、负载、断电保持、厂商编译均需各自证据。
- 当前为空隔离 PLC；寄存器测试通过不构成泵、驱动或现场安全验证。

---

# V006 批量接口段（HMI/SCADA 用，2026-11-18）

> 上节 V002 表为历史记录（D190–D195 接口自 V005 起已废止）。V005 起的对外接口是
> **批量块 D300–D336**；本节为 V006 的权威登记，与 `source.fxil`（V006）和
> `versions/V006/requirements-V006.md` 同源。机器可读版见 `hmi/registers.md`。

> **刷新约定**：一轮 = FC03 读 **D300–D336（37 字）** + FC16 写 **D320–D336（17 字）**，
> 各一帧原子下发。命令块自 V006 起为 17 字，HMI 必须写满，缺 D336 会被钳位成 1.0 bar 而误锁输出。

| 地址(零基) | 权限 | 类型/单位 | 首扫 | 含义 |
|---|---|---|---|---|
| D300 | RO | signed16 | 6 | 程序版本字 |
| D301 | RO | signed16 | 31 | 版次字 |
| D302/D303 | RO | signed16 | -7313/-11960 | 指令指纹字（与 build_identity 一致） |
| D304 | RO | signed16 | 6 | 测试套件字（STD-006） |
| D305 | RO | signed16 | 0 | 心跳边沿计数（回绕） |
| D306 | RO | signed16 | 0 | 扫描计数（回绕） |
| D307 | RO | bit 字段 | 0 | bit0 运行 / bit1 休眠 / bit2 休眠计时 / bit3 唤醒计时 / bit4 测试 / bit5 使能 / bit6 PV 卡满量程诊断 / **bit7 超压封锁** |
| D308 | RO | 0.1 bar | — | 实际压力（D100） |
| D309 | RO | 0.1 bar | 60 | 在线设定（D102，10–160） |
| D310 | RO | 0.1 bar | 40 | 唤醒压力生效值（D160） |
| D311 | RO | 0.01 Hz | 0 | 频率（D154） |
| D312/D313 | RO | raw | 0 | AO0/AO1 镜像 |
| D314/D315 | RO | 100 ms | 0 | 休眠/唤醒计时 |
| D316 | RO | 0.1 bar | 80 | **最大压力生效值（D175 镜像，V006 起；V005 为保留恒 0）** |
| D317 | RO | signed16 | 0 | 回显响应（=D333） |
| D318 | RO | raw | — | 选中原始码（D110） |
| D319 | RO | 0..30000 | 0 | PI 积分（D120） |
| D320/D321 | RW | 1=asserted | 0/0 | 启动/停止请求，停止优先 |
| D322 | RW | 0/1 | 1 | 信号源：1=注入 D330，0=AI0 |
| D323 | RW | 1=asserted | 0 | 物理路由使能（Y0/AO0 门） |
| D324 | RW | 0.1 bar | 60 | 在线设定（钳位 10–160） |
| D325 | RW | 0.1 bar | 60 | 保存设定（首扫校验 10–160） |
| D326 | RW | 0.1 bar | **40（4.0 bar）** | 唤醒压力设定（V005 为 SV×85%，V006 起固定 4.0 bar，在线钳位 0–160） |
| D327 | RW | 100 ms | 100 | 休眠延时（10–600） |
| D328 | RW | 100 ms | 30 | 唤醒延时（5–300） |
| D329 | RW | 0.01 Hz | 2000 | 不出水速度（2000–3000） |
| D330 | RW | raw | 0 | 测试 PV 注入（D322=1 生效） |
| D331/D332 | RW | raw / 0-1 | 0 | 并联 AI0 台架输入及使能 |
| D333 | RW | signed16 | 0 | 回显请求 |
| D334/D335 | RW | 1=asserted | 0 | 并联端子启/停（与 D320/D321 同语义 OR） |
| **D336** | RW | 0.1 bar | **80（8.0 bar）** | **最大压力设定（V006 新增）**；在线钳位 10–160 入 D175；D100 > D175 即封锁输出并置 D307 bit7，回落到 D175−5 自动解除 |

## 超压保护行为（V006）

- 判定：运行中（M0=1）且 `D100 > D175`，**严格大于**；等于上限不触发。
- 封锁：D154=0、D120=0（Y0 与 AO0 随之归零），锁存期间每扫描保持。
- 报警：D307 bit7（值 128）。
- 自动恢复：`D100 <= D175-5`（0.5 bar 回差）即解除，无需人工复位；停机不清锁存，压力回落后同样清除。
