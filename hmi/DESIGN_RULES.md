# 设计规则 — PLCWeave 手动HIL仿真台（V0.3 实现）

适用范围：`src/plcweave/bench/app.py`（tkinter 实现）及后续界面迭代。原型参考图见 [prototype/layout-v0.3.png](prototype/layout-v0.3.png)，运行截图见 [docs/assets/screenshots/](docs/assets/screenshots/)。

## 窗口与布局

- 默认窗口 **1280×800**，最小窗口 **1024×768**。AD 和 DA 使用紧凑竖条，为 AD 设定值与“应用”按钮留出空间。底部默认显示客户寄存器监控和发送栏。
- 结构：顶栏（连接/版本/状态）→ 四象限卡片网格（左上 X、右上 AD、左下 Y、右下 DA）→ 底部仿真操作栏 → 本次操作日志。
- X 与 Y 按通道编号上下对齐；每卡是白底 `tk.Frame`，`highlightbackground=BORDER` 1px 描边。

## 色板（写死在 app.py 顶部常量，勿散落硬编码）

| 常量 | 值 | 用途 |
| --- | --- | --- |
| `BG` | `#EEF1F6` | 窗口底 |
| `CARD` | `#FFFFFF` | 卡片/控件底 |
| `BORDER` | `#DDE3EC` | 卡片描边 |
| `INK` | `#0F172A` | 主文字 |
| `SUB` | `#64748B` | 次要文字 |
| `ACCENT` / `ACCENT_DARK` | `#2563EB` / `#1D4ED8` | 主按钮/目标高亮/填充条 |
| `GREEN` | `#16A34A` | ON 状态、仿真中 |
| `RED` | `#DC2626` | 故障、错误 |
| `ORANGE` | `#D97706` | 待确认/过期/结束中 |
| `LED_OFF` | `#CBD5E1` | 小灯灭 |
| `BAR_TRACK` / `BAR_FILL` | `#E2E8F0` / `#2563EB` | 竖条轨道/填充 |

## 字体

统一 `Microsoft YaHei UI`（常量 `FONT`）：标题 12 bold、正文 9、次要 8、数值 11 bold。不引入其他字体。

## 组件复用

- `make_led` / `set_led`：状态小灯（小灯与操作按钮分开，PRD A17）。
- `LedColumn`：小灯 + ON/OFF/未知/待确认/过期 文字，颜色不作唯一依据。
- `make_bar` / `set_bar`：竖直只读滑条。**不得绑定任何鼠标/滚轮/键盘事件，`takefocus=0`**（PRD A07）；层叠顺序为 轨道 < 填充；数值文字不画在条内，统一放条下方。
- `self._button(...)`：平面按钮（primary=蓝底白字）。

## 状态色映射（`STATE_COLORS`）

未连接=灰 / 连接中·启动中·结束中=橙 / 已连接=蓝 / 仿真中=绿 / 故障=红。顶栏状态徽章与 `_update_status_line()` 数据年龄/刷新耗时共用一套文字来源。

## 线程与更新纪律

- 所有串口事务只在 `BenchWorker` 线程执行；UI 通过 `worker.submit()` 提交。
- UI 更新只发生在主线程 `_process_events()`（50ms `after` 轮询事件队列）；tkinter 控件严禁跨线程直接访问。
- 值刷新统一走 `refresh_values()`；权限（按钮使能）统一走 `refresh_permissions()`，与 PRD §4.4 状态表一一对应。
- 脚本由独立 Python 宿主运行，主 worker 消费真实通讯事件，运行期间停止 GUI 的串口事务。等待本次进程树和客户端释放后再提示完成；确认后才复用实际成功端点进入手动测试。弹窗、输入框目标同步仍由 Tk 主线程执行。

## 截图管线

界面改动后必须重跑（hmi-frontend 红线：截图与代码不允许漂移）：

```bash
.venv/Scripts/python.exe hmi/prototype/scripts/screenshot.py
# 输出 hmi/docs/assets/screenshots/*.png（截图依赖支持按 Windows 窗口句柄抓取的 Pillow；使用隔离临时数据目录）
```
