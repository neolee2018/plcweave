# 演示提示词

| 你的情况 | 用哪段 |
| --- | --- |
| 刚克隆，还没装环境 | 仓库根目录 [`PROMPT.md`](../PROMPT.md)：一条提示词，从安装、自检到演示交付全程自动 |
| 环境已装好（`python -m plcweave --help` 正常） | 下面第一段：无硬件全自动 |
| 接了隔离 L01S 台架 | 下面第二段：硬件版，含烧录/台架确认门 |

演示场景是固定的：**L01S 启停 + 3 秒延时输出 + 运行计时**。它不采集你的工艺需求；真实项目请
按 [`START-HERE.md`](START-HERE.md) 与仓库 README 的 S0–S7 流程另建目录。

## 无硬件全自动（复制这一段）

> 用 PLCWeave 跑 `demo/START-HERE.md` 的固定场景演示（L01S 启停 + 3 秒延时输出 + 运行计时），
> 无硬件模式、不要中途问我问题：`demo start demo-run --not-connected` → `simulate` →
> `demo status` → `demo deliver --version V001`。完成后汇报交付 ZIP 路径、`SUMMARY.md` 的
> 完成度与“S6 未执行”结论，并说明接硬件怎么继续。

## 接了 L01S 台架（复制这一段）

> 用 PLCWeave 跑 `demo/START-HERE.md` 的固定场景演示，我接了 L01S 硬件。先问我项目名，再收集
> COM 口、波特率、校验位、从站地址，然后 `demo start`；仿真通过后提醒我用 GX Works2 烧录；
> 我明确确认烧录并接好 RS485、现场是隔离空机后，才执行 `demo confirm-flash` /
> `demo confirm-bench` / `preflight` / `hil --isolated-bench`；最后打 ZIP 交付。未确认前不要
> 打开串口写设备。

## English

> Run the fixed PLCWeave demo in `demo/START-HERE.md` (L01S start/stop + 3 s delayed output +
> runtime counter), no-hardware mode, without asking me anything: `demo start demo-run
> --not-connected`, then `simulate`, `demo status`, and `demo deliver --version V001`. Afterwards
> report the delivery ZIP path, the `SUMMARY.md` completion score and the "S6 not executed"
> verdict, and how to continue with hardware.

> Run the fixed PLCWeave demo with my L01S hardware, following `demo/START-HERE.md` mode B: ask me
> for the project name and the COM port, baud rate, parity and slave address before `demo start`;
> after SIM_PASS remind me to download with GX Works2; only after I explicitly confirm the flash,
> RS485 wiring and isolated bench, run `demo confirm-flash`, `demo confirm-bench`, `preflight` and
> `hil --isolated-bench`; finish with the delivery ZIP. Never write to the device before I confirm.
