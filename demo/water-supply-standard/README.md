# 恒压供水演示项目（L01S Water Standard）运行手册

这是给**客户克隆仓库后直接使用**的恒压供水完整演示流程：离线脚本测试 → GX Works2 烧录 →
实机测试 → 生产交付。项目本体在 [`project/l01s-water-standard/`](../../project/l01s-water-standard/README.md)，
本 README 是它的三步走运行手册。把本手册交给一个能在你电脑上执行终端命令的 AI Agent
（Codex CLI、Claude Code、Cursor、ZCode 等），按 Step 1 → 2 → 3 走完全程。

- **控制对象**：L01S-16M-4AD2DA 恒压供水。压力变送器 AI0（0–16 bar）→ 固定点数字 PI
  → 变频器频率输出 0–50 Hz（AO0），带休眠/唤醒、最大压力保护（超压封锁与回差自动恢复）。
- **当前程序版本**：V006（程序版本字 D300=6 / 版次 31 / 台架套件字 D304=6 / 套件 STD-006）。
- **演示硬件边界**：本演示默认在**隔离空机**上做——不接水泵、传感器以外的任何负载与执行器；
  物理输出路由默认禁止（命令块使能位 D323=0），烧录与下载始终由客户本人完成。

## 前置：安装（一次性）

按仓库根目录 [README.md](../../README.md) 第 1 节安装 Python 3.13+、Rust 1.93+，创建 `.venv`
并安装 `./vendor/gxwlib` 与 `-e ".[test]"`（实机测试再加 `.[hil]`）。也可以把根目录
[PROMPT.md](../../PROMPT.md) 的**提示词一**交给 Agent，让它自动完成安装与自检。

## 项目目录速览

```text
project/l01s-water-standard/
├── requirements.md               # 需求（作者源）
├── source.fxil                   # V006 指令表源
├── register_map.csv / io_map.csv
├── lab-tests/V006/               # ★ 烧录材料：MAIN.csv + COMMENT.csv + 粘贴版指令表
├── versions/V006/                # V006 冻结的用例套件 STD-006（test_cases + s1-freeze）
├── verify_v006_behavior.py       # ★ Step 1：离线逐扫描行为验证（无需硬件）
├── run_hil_v3.py                 # ★ Step 2：实机在环测试脚本（台架命令块接口）
├── check_build_identity.py       # 构建/源一致性核对
├── Doc/  hmi/  delivery/V006-bench-kit/  evidence/
└── ...
```

历史台架套件说明见
[project/l01s-water-standard/delivery/V006-bench-kit/README.md](../../project/l01s-water-standard/delivery/V006-bench-kit/README.md)。

---

## Step 1 设计/检查恒压供水程序（Agent 执行，无需硬件）

Agent 拿到本项目后的默认动作：

1. **检查项目**：通读 `requirements.md`、`register_map.csv`、`io_map.csv` 与 `Doc/`，
   核对三者一致（寄存器地址、量程、命令块 D320–D336 / 状态块 D300–D319 的定义）。
   如果文档存在缺漏或过时条目，先做整理——以 `source.fxil` 与 `register_map.csv` 为准修订文档，
   再继续。
2. **启动脚本测试**（离线逐扫描仿真，不接任何硬件）：

   ```powershell
   ./.venv/Scripts/python.exe project/l01s-water-standard/verify_v006_behavior.py
   ```

   期望输出：`{"status": "PASS", "checks": 22, "failed": []}`（首扫默认值、超压封锁、
   回差自动解锁、钳位与镜像、报警位共 22 项）。可选地再跑
   `check_build_identity.py` 核对源/构建身份一致。
3. **汇报**：明确告诉用户——**恒压供水程序已经生成完毕**，并指出烧录材料位置：
   `project/l01s-water-standard/lab-tests/V006/`（`MAIN.csv`、`COMMENT.csv`、
   `instruction-list-paste.txt` 粘贴版）。

> 注意：不要对项目根目录跑 `plcweave simulate`。仓库里的 62 用例 STD-005 回归套件是
> V005 时代的预期，V006 起休眠/唤醒预期已修订，跑旧套件只会得到一串假 FAIL。
> V006 的验证体系是：离线 `verify_v006_behavior.py`（22 项行为断言）+
> 实机冻结套件 `versions/V006/`（STD-006，7 条用例，由 `run_hil_v3.py` 执行）。

## Step 2 烧录程序（客户操作）→ 实机测试（Agent 执行）

**客户操作（烧录必须由客户本人完成）：**

1. 打开 GX Works2 工程，导入 `project/l01s-water-standard/lab-tests/V006/COMMENT.csv` 与
   `MAIN.csv`（或在工程里粘贴 `instruction-list-paste.txt` 的 310 条指令）。
2. **确认编译零错误后**下载到 PLC，并把 PLC 切到 RUN。
3. 只读身份核对（可用任意 Modbus 主站或台架界面）：`D300=6`、`D301=31`、`D304=6`、
   `D302/D303 = -7313/-11960`，且 `D305` 心跳持续变化。
4. 烧录完成后回复 Agent，例如：**"已烧录并 RUN，编译零错误"**（附上烧录时间与软件版本更好）。

**Agent 收到烧录确认后，先问三件事，全部确认才开实机测试：**

> 1. PLC 已切 RUN？
> 2. USB-RS485 已接到 PLC 的 Modbus 口？
> 3. 现场是隔离空机，未接水泵/负载/执行器？

三项确认后执行（默认 COM11 = RS485、COM5 = 编程口，可用 `--port` / `--cpu-port` 覆盖）：

```powershell
# V006 冻结套件 STD-006 共 7 条用例（STD6-001..007），必须带 --restart（真实 STOP/RUN 首扫）
./.venv/Scripts/python.exe -m plcweave.bench --script project/l01s-water-standard/run_hil_v3.py --script-args --restart --all
# 也可只跑指定用例：--script-args --restart --cases STD6-001,STD6-003
```

或者用台架界面手动/半自动验证（右上角 Language 可切中文/English/Français/Português/Español/العربية）：

```powershell
./.venv/Scripts/python.exe -m plcweave.bench
```

界面里按 `delivery/V006-bench-kit/README.md` 的「烧录后的台架验证」逐项做（上电默认值、
超压封锁、回差恢复、钳位）。测试证据由脚本写入项目 `evidence/` 目录，判读口径：
`PASS / PROGRAM_FAIL / TEST_INFRA_ERROR / UNVERIFIED`，不能把 UNVERIFIED 说成 PASS。

## Step 3 项目交付（客户输入"项目交付"，Agent 执行生产导出）

客户确认测试完毕后，输入：**"项目交付"**（或"测试完毕，导出生产程序"）。
Agent 按仓库工作流的[生产导出规则](../../.agents/skills/plc-program-development/references/two-phase-workflow.md)执行：

1. **剔除全部仿真寄存器**：从正式版程序中删除仅仿真/台架使用的寄存器与段
   （命令块中的压力注入 D330、测试注入 D322、并联 AI/并联使能、bench 旁路等），
   同步剔除 `register_map.csv`、`Doc/HMI-register-map.md` 与程序说明中的对应条目
   （或明确标注"仅存在于测试版"）。
2. **重建并静态检查**正式版指令表（语法 + 逻辑关系静态检查通过）。
3. **导出交付**：需求、设计、程序说明、正式版 `MAIN.csv`/`COMMENT.csv`、寄存器表、
   实机测试报告与轨迹、MANIFEST 哈希清单，放入 `delivery/<版本>/` 并打成 ZIP；
   不覆盖已有版本。
4. 客户拿到 **可直接使用的工程文件包**（ZIP）后，本演示流程结束。

---

## 安全与边界（全程适用）

- 烧录、下载、RUN/STOP 与任何现场动作由**客户本人**完成并明确确认；Agent 不自动写设备。
- 实机测试只允许在隔离空机上进行；未接负载前禁止使能物理输出（D323=0）。
- 所有结果如实记录：仿真/实机哪一项没验证就写 UNVERIFIED，不伪造 PASS。
- 命令块必须按 **17 字**整块写（V006 起 D336 加入最大压力设定），16 字旧写法会把
  上限钳到 1.0 bar 导致误封锁。
