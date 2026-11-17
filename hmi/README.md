# PLCWeave 手动硬件在环仿真台 — 设计与实现

**当前版本 V0.6.0。** 客户寄存器监控常驻右侧独立栏（单位/量程注释列 + 压力/频率归一化读数），四象限居左；支持 Python 测试脚本过程展示、完成确认及手动接管；仅实机模式。窗口默认 1600×860，最小 1530×740。实现代码位于 `../src/plcweave/bench/`。

## 启动方式

```bash
# 实机模式：Modbus RTU / USB-RS485
# 手动连接前须填写版本地址并加载与目标程序核对过的接口档案（confirmed=true）
.venv\Scripts\python.exe -m plcweave.bench
```

本机台架（L01S-16M-4AD2DA）：Modbus RS485 在 **COM11**（CH340，9600、8N1、站号 1，2026-11-06 只读验证正常），编程口在 **COM5**。界面连接参数保存在 `%LOCALAPPDATA%\PLCWeave\hil-bench\ui_config.json`，当前已按 COM11 配置。客户寄存器监控表和发送栏常驻右侧独立栏：新增"单位 / 量程"注释列（由工程适配器提供），压力按 0.1bar→bar、AI raw 按程序标定公式归一化为 bar，频率按 0.01Hz→Hz 显示；发送栏仍写原始整数值。实机授权字段见参数表第 5 节。

## 运行已有 Python 测试

优先接入 `project/l01s-water-standard/run_hil_v3.py`。双击根目录 **`run-water-test.bat`**，即打开界面并运行这份实机脚本。串口、站号、测试用例及原有身份检查由脚本决定：当前默认 COM11、9600、8N1、站号 1（`--port`/`--cpu-port` 可覆盖）；`--restart`（经 COM5 真实 STOP/RUN）默认不开启。未指定 `--output` 时自动使用新的 `gui-时间-随机后缀` 结果目录，不覆盖旧证据。

```powershell
# 同一实机入口；参数原样传给原脚本，例如仅选择 STD-016
.venv\Scripts\python.exe -m plcweave.bench --script project/l01s-water-standard/run_hil_v3.py --script-args --cases STD-016
```

也可以先打开实机界面，点击底部“运行测试脚本”，默认选中这份工程。参数框每行填一个参数或值。连接参数以脚本实际通讯为准，界面连接栏显示成功事务使用的参数；脚本运行期间，界面停止自行轮询和写入。

上方显示脚本实际读到的 X/Y/AD/DA，底部日志显示读取、写入、返回值、异常和脚本输出。没被读到的点位保持未知，写入值只更新目标，不冒充 PLC 生效值。CPU 原始串口收发也记录原始字节。脚本原有判断与报告保留，退出码 0 只表示脚本进程结束；`PROGRAM_FAIL` 等脚本报告会单独显示并记入记录。

测试宿主及本次派生进程退出、释放连接后，弹出“测试完毕”。**点击确定后才重新连接并开放手动测试；窗口不会自动关闭。** 实机压力工程自动核对五个程序身份字（当前绑定 V004：D196=4）；AD0 直接写注入寄存器 D1056（读回 D110），不做模式条件门禁——程序在 D190=1 测试模式下消费该值，D190=0 时写入仍在但不参与逻辑，输入模式 D190 可在寄存器面板查看。D102 是在线设定压力（10–160，单位 0.1bar），D260 是只读预休眠阈值；X0/X1 按钮映射启动/停止命令字 D191/D192（等效现场启停按钮，LED 回显请求电平）；V004 程序另有并联端子 D1072/D1073 可在客户寄存器面板直接驱动。未映射的 X 注入保持禁用（Modbus 对 X 只读）；X2–X7 小灯回落显示 FC02 直读的实机输入状态（每轮询刷新），短接端子即可在界面验证输入点。手动测试结束或关闭界面仅结束本次手动记录并断开连接；PLC 程序状态仍由原程序和操作者控制。

每次脚本和随后手动测试分别保存一条调试记录，沿用最近 30 次轮转；ZIP 增加 `script-transactions.jsonl` 原始收发证据。运行中导出分别标注主日志序号与脚本原始日志序号，可能包含尚未显示的脚本事务。完整操作、截图和验证边界见[本次验收记录](docs/acceptance-2026-11-06-script.md)。

## 目录

- [PRD.md](PRD.md)：V0.4 需求与验收口径（A01–A18）。
- [params.md](params.md)：硬件只读点表、本机连接参数、输入接口契约与建议分配。
- [DESIGN_RULES.md](DESIGN_RULES.md)：色板/字体/组件/线程纪律 + 截图管线。
- [prototype/main.md](prototype/main.md)：文字线框（历史设计稿）；[prototype/layout-v0.3.png](prototype/layout-v0.3.png)：布局参考图。
- [docs/screens/main.md](docs/screens/main.md)：主画面运行截图 + 组件/绑定/交互/状态变体说明。
- [docs/index.md](docs/index.md)：画面清单与截图再生成命令。
- [history/](history/)：V0.1–V0.3 历史快照，仅供追溯。

## 多语言（i18n）

界面文案字典位于 [`../src/plcweave/bench/i18n.py`](../src/plcweave/bench/i18n.py)，当前提供 6 种语言：**中文（默认）、English、Français、Português、Español、العربية**（顶栏右侧“语言”下拉框，切换即时生效并写入 `ui_config.json`，下次启动按记录恢复）。设计约定：

- 界面静态文案以稳定 key 收录在 `STRINGS`（key → {zh, en, fr, pt, es, ar}）；缺译文回退中文，缺 key 回退 key 本身，便于渐进补齐新语言。
- 引擎/存储产生的数据词（State、日志 action/result/reason、会话状态、X 交互模式、监控权限）保持中文原值为唯一权威：落盘记录、`ui_config` 与 engine 比较逻辑不翻译，仅在界面显示边界经 `tr()` 映射、下拉框选择经 `untr()` 还原（映射表 `DATA_KEYS`）。
- 字体：界面统一使用 Tk 命名字体（`bench7`–`bench12b`），切换语言时改 family 即全界面（含 ttk 样式）生效。微软雅黑无阿拉伯字形，阿拉伯语界面切换为 Segoe UI；Segoe UI 无 CJK，阿拉伯语界面下中文监控名称可能显示为方框，属已知限制。
- RTL：Tk 8.6 不做布局镜像，阿拉伯语文本按系统文本引擎整形显示、版式仍为从左到右；混合拉丁 token（D8050、PLC 等）处的标点/顺序可能出现双向文本瑕疵。
- 新增语言：在 `LANGUAGES` 注册显示名并为每个 key 补齐译文，再为 app.py 的宽度表（`BTN_WIDTHS` 与各 `_bind_button` 字典）补一列宽度；`tests/test_bench_i18n.py` 校验各语言 key/占位符齐全、zh 与既有界面文案逐字一致、数据词往返映射完整。

## 实现与验证边界（如实陈述）

| 范围 | 状态 |
| --- | --- |
| 界面布局/交互/状态机/日志/轮转/导出 | 已实现，验证结果见[验收记录](docs/acceptance-2026-11-04.md) |
| 通讯与契约 | 自建 Modbus RTU（FC01/02/03/06/16）+ 回环传输层，经虚拟 PLC 全链路自动化验证 |
| **实机验证** | **脚本通道已有实机记录**：`run_hil_v3` 于 2026-10-24 在 COM7 台架完成 V003 冻结用例（55 项：PASS 31 / UNVERIFIED 24 / PROGRAM_FAIL 0，见 `project/l01s-water-standard/evidence/s6-v3/SUMMARY-V003.md`）；2026-11-06 在 COM11 台架完成只读通讯验证，机上程序身份 (3,31) 与本脚本门禁一致。四象限手动会话的实机验收仍未做；常规整组仿真须核对版本地址并加载已确认完整接口档案（`confirmed=true`）后现场 RS485 联调。压力工程手动接管按源哈希和五字身份检查实际输入定义。PRD §10 中 A03/A04/A05/A10/A11/A12 需实机证据 |
| 输入接口地址 | D8100–D8143 为虚拟演示地址。实机接口须按目标程序分配在 D0–D7999，并经档案、版本、构建标识和存活检查 |

无监听端口；本机数据保存在 `%LOCALAPPDATA%\PLCWeave\hil-bench\`（调试记录 + 界面配置），可在“版本与接口设置”打开目录。客户 PLC 程序、接口档案、证据和交付继续放在各自 `project/<名称>/`。
