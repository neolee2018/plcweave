# 独立复核④：项目隔离、文档、交付一致性与可复测性复核

- 复核对象：`evidence/s6-v3/SUMMARY-V005-fix-HIL-round3.md`（V005 自锁修复版 S6 HIL 第三轮候选结论）
- 复核人角色：独立上下文 Agent ④（项目隔离/文档/交付一致性/可复测性），与主会话完全独立，未采信任何既有结论
- 复核日期：2026-11-08
- 方法：对文档 §1–§6 逐个数字/逐个文件用 `python -I` 对原始 report.json 重算、对实际文件重算 SHA256、用 `git check-ignore`/`git status` 验证隔离，不依赖文档自述。

---

## 1. 文档-证据一致性（§1/§2 全部数字重算）

| 文档声称 | 实际核查 | 结论 |
|---|---|---|
| 31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL | `run-v5-full-fix2/report.json`：cases=62，Counter = {UNVERIFIED:31, PASS:31}，无 PROGRAM_FAIL | 一致 |
| 2132 项主机可比对全部吻合 | 逐 case 求和 compared_items=2132；逐 step 累计 mismatch 条目=0；per-step compared 明细条目总数=2132（三口径互相印证） | 一致 |
| 62 用例、448 writes、task_id=PW-20261108-V005-BATCH-IO | report.json：writes=448、cases=62、task_id 一致；cleanup="stopped, output disabled, zero readback"、serial_closed=true | 一致 |
| D302=-10264, D303=-21461 | report.json identity = {D300:5, D301:31, D302:-10264, D303:-21461, D304:5}，与 build_identity.json fingerprint_words 完全一致 | 一致 |
| system_checkpoint D8120=-8063(0xE081), D8121=1 | report.json system_checkpoint = {D8120:-8063, D8121:1}；-8063 & 0xFFFF = 0xE081；requirements.md R10 冻结预期 D8120=HE081/D8121=1 | 一致 |
| canonical_sha256 e8d72bac… / source_sha256 13f396bc… | `check_build_identity.py` 独立重跑 PASS，输出与 build_identity.json、manual_download.json、文档三处一致 | 一致 |
| test_sha256（s1-freeze）36123300… | 实测为 **test_cases.json** 的 SHA256=36123300…，且 s1-freeze.json 内 `/test_cases.json` 字段登记同一值（s1-freeze.json 本身哈希为 8a00c0dd…） | 数值一致；标注见问题 minor-2 |
| UNVERIFIED 拆解 162/7/2/2 | skip 原因统计："Running PI…host polling cannot certify"=162 项/29 用例；"System comm word"=2 项（STD-001）；one-tick tick_hold=7 项（恰好 STD-033/034/041/046/051/053/060，D314=99/阈值100）；STD-031 s7/s8 共 2 项 tick_hold（40/100、44/100，reason 注明 expectation/simulator divergence）；四类并集=31 个 UNVERIFIED 用例 | 一致 |
| 三轮对照表 | run-v5-full-e：0/48/14（PASS/UNVERIFIED/PROGRAM_FAIL，62 例），identity=[-13535,-16701]（修复前镜像）✓；run-v5-full-fix：32/23/7 ✓；run-v5-full-fix2：31/31/0 ✓ | 一致 |
| §3.1 冒烟实证 M0=1 | run-v5-fix-smoke：2 例 PROGRAM_FAIL（STD-059/062 step5 invariant M0 expected=0 actual=1）；smoke2/smoke3 mismatch 条目=0 | 一致 |
| §3.2 Y0 纳入判读 266 处预期 | test_cases.json 中 `Y0` 键出现 267 次，其中 cases/[]/steps 下 266 次 + global_invariants 1 次 | 一致（266 指 steps 内预期） |
| §5 采样方差 STD-037/033/034/053 | fix 轮：STD-037 PROGRAM_FAIL（M11 expected 1 actual 0）、STD-033 FAIL、STD-034/053 PASS；fix2 轮：STD-037 PASS、三者均 UNVERIFIED（99/100） | 一致 |

## 2. 可复测性

- **§6 证据索引逐项存在性**：全部存在 —— run-v5-full-fix2/fix/e 的 report.json、run-v5-fix-smoke/smoke2/smoke3、readonly-probe-v005fix-20261108.json、../manual_download.json、../build_identity.json、../s1-freeze.json、../source.fxil、../../实验室测试/V005/（MAIN.csv+COMMENT.csv）、simulation/v005/simulation_trace.csv、../s1-revision-V005.md。仅 `../evidence/simulation/v005/` 相对路径基准写法不统一（见 minor-3），目标文件存在。
- **run_hil_v3.py 命令行**：`--help` 确认支持 `--restart --all --output --port --cpu-port --cases`；`--all` 跑完整冻结套件（读 test_cases.json），输出写 `evidence/s6-v3/<name>/report.json + progress.json`，与主批次产物同构，可复现主批次形状。数据面默认 COM11(9600/8N1, 站号1)、编程口默认 COM5(9600/7E1)，与 §1 一致。
- **烧录绑定链**：manual_download.json 四个绑定字段齐全——source_sha256/canonical_sha256/fingerprint_words 与 build_identity.json 相同；confirmed_by 为用户对话原文；downloaded_at 有 confirmed_complete_before=2026-11-08T13:30:09Z（exact_time=null，见 minor-5）。
- **哈希关系实测**（任务要求说明）：
  - `source.fxil` 实测 SHA256 = 13f396bc… = **source_sha256**（指 source.fxil 原始字节流）；
  - `canonical_sha256` = e8d72bac… 是规范化指令流哈希（canonicalize：instructions 区剔除注释、剔除 BEGIN/END_IDENTITY 块后归一化），由 check_build_identity.py 从 source.fxil 独立重算 PASS；
  - `实验室测试/V005/MAIN.csv` 实测 SHA256 = 6e7f08f3…，**不等于也不应等于**上述两个哈希：MAIN.csv 是厂家工具烧录导出件，其自身哈希未进入绑定链；绑定通过「source.fxil 哈希 + 规范化指令流哈希 + 指纹字(-10264,-21461)真机 D302/D303 回读一致 + 用户烧录确认」四要素完成。COMMENT.csv 实测 SHA256 = c3de5b00…（仅登记 mtime，无哈希绑定，属既有惯例）。
  - MAIN.csv/COMMENT.csv mtime = 2026-11-08 21:11:41，与 §1 "21:11" 一致。
- **写前证据时序**：readonly-probe（readonly=true，13:29:46Z，identity_match=true，心跳/扫描计数推进）早于本轮全部写操作（smoke1 起 13:30:23Z），且晚于用户烧录完成确认（13:30:09Z 前）——时序自洽。
- **行为链时间线**：e 轮(12:38Z, 旧镜像) → 21:11 本地烧录 → probe → smoke1(FC06, M0=1) → smoke2/smoke3(修复后零失配) → fix 全量(13:42Z) → fix2 全量(14:12–14:33Z)。与 §3 叙述一致。

## 3. 项目隔离

- 本轮新产物全部位于 `project/l01s-water-standard/` 内：evidence/s6-v3/run-v5-fix-smoke*、run-v5-full-fix*、reviews/s6-v005-fix-20261108/、SUMMARY-V005-fix-HIL-round3.md、manual_download.json、run_hil_v3.py 均在项目内。未发现客户程序/需求/测试/证据写入 src/、tests/、docs/、技能目录。
- **project/ 忽略验证**：仓库根 `git check-ignore` 确认 `.gitignore:18 project/*` 覆盖 SUMMARY 与 reviews 目录；`git status --porcelain` 输出不含任何 `project/` 条目——客户内容不会进入公共仓。
- **git status 公共区改动甄别**：改动包括 README*、docs/RUNTIME-CHANGES.md、docs/DVP-CONVERSION.md、src/plcweave/validation.py、src/plcweave/bench/、tests/test_bench_*(10个)、demo/bench-script-demo.py、hmi/、run-water-test.bat、tools/build_dvp_prompt_page.py。按 mtime 判定：均属当日更早的台架/工具链开发（bench 12:00、app.py 16:10、validation.py 18:14 等），**不是本轮 V005 第三轮（20:38–22:41 本地）新增**。其中 `src/plcweave/bench/script_projects.py`（mtime 21:16，落在本轮执行窗口内）内嵌了客户项目专属适配数据（l01s-water-standard 路径绑定、D300–D335 寄存器语义表、指纹字、source_sha256），见问题 major-1。
- 结论：本轮本身未向公共区新增客户文件；但工作区公共区存在当日累计的未提交改动，其中一处含客户派生数据，须在提交前处置。

## 4. 证据不可覆盖性

- 既有证据全部在位且未改名/未覆盖：SUMMARY-V003.md(2026-10-24)、SUMMARY.md、summary*.json、adc-write-probe-20261023.json、readonly-probe-20261023.json、soft-element-smoke-20261023.json、output-demo-*(2026-10-24)、run-v3-* 全部 18 个目录（逐目录核查：0 个文件今日修改）、gui-20261106-182601（0 个文件今日修改）。
- run-v4-full-1110 / run-v4-restart-1139 为**当日更早会话**所建（at 11:10/11:39 本地，identity 为 V004 时代 D196/D197 寄存器组），非本轮覆盖对象。
- 本轮新目录均为新名且今日新建：run-v5-fix-smoke/smoke2/smoke3、run-v5-full-fix、run-v5-full-fix2（与更早的 run-v5-full-1928/b/c/d/e 不重名，后者保留旧镜像 -13535/-16701 原始记录）。
- SUMMARY-V005-fix-HIL-round3.md（22:41 新建）未覆盖 SUMMARY.md/SUMMARY-V003.md。
- 结论：§7 "未覆盖任何既有证据目录" 属实。

## 5. 边界声明（§5/§4）

- §5 "已证明" 明确限定为"台架软元件注入范围内……零程序偏差"，逐类列举（A 类稳态标量、B 类参数驱动、停止/启动电平语义、并联端子、回显、批量接口身份块）；"未证明" 明确列出电气量/水压闭环（D 类仅本地）、扫描级 C 类时序、STD-031 族冻结预期有效性。**无任何把软元件台架结果升级为电气/带载/安全验证的表述**。
- §4 明确标注仿真 oracle 计时器复位分歧为"仿真 oracle 缺陷，非程序缺陷"，处置为真机 UNVERIFIED（非 FAIL）+ 三条**待办**（修 S3/gxwlib 仿真建模并重跑、按 S1 修订流程复核 STD-031 族冻结预期、不继承旧 PASS）——是待办而非已修复，表述合规。
- 独立抽查支撑事实：仿真轨迹 STD-031 D314 采样序列 31→32→62→63→99→（M11=1 时回 0），越限步（PV=59）未复位，与文档"单调 31→32→62→63→99→100"实质一致；真机 fix2 实测 0,1,30,33,28,0,34,40,44（两次越限重启，终点 40/44），与 §4"复位重启"结论一致（文档压缩链顺序略异，见 minor-6）。

## 6. 复核节点合规

- 文档头部第 5 行明确："**待 4 名独立上下文 Agent 复核（见 reviews/s6-v005-fix-20261108/），复核通过前本结论为候选判定**"。
- fix2 report.json 顶层 status 为 UNVERIFIED（整批判定），未把 31 UNVERIFIED 升格为整体 PASS；delivery/ 仅有 V002/V003，无过早的 V005 交付物，与"候选判定"状态自洽。合规。

---

## 问题清单

**Blocker：无。**

**Major：**

1. **公共区工具链内嵌客户派生数据（隔离隐患，未提交状态）**：`F:\000-HBDTECH-Neo\103-plcweave\src\plcweave\bench\script_projects.py`（mtime 2026-11-08 21:16，在本轮执行窗口内被改动）硬编码了 l01s-water-standard 的路径绑定、D300–D335 全量寄存器语义/量程表（压力/水位业务语义）、指纹字 (302,55272)/(303,44075) 与 source.fxil 哈希 13f396bc…。按 AGENTS.md"客户资料全部存入客户项目目录、公共区只维护通用工具链"，该适配内容应迁入 project/（或改为通用配置加载）。当前 src/plcweave/bench/ 整体处于未跟踪（untracked）状态，尚未进入 Git 历史，无实际公开泄露；但 `git add -A` 类操作会将其带入公共仓，须在提交前解决。此问题属工具链开发遗留，非本轮判定结论的缺陷，不影响 HIL 数据有效性，但属项目隔离复核职责内的必报项。

**Minor：**

1. §1 "主批次……at 2026-11-08T14:24:53Z 前后"：fix2 实际起 14:12:45Z、写盘 14:33:22Z，14:24:53 落在窗口内但与起止均不符；建议改写为起止区间。
2. §1 "test_sha256（s1-freeze）=36123300…"：该值是 test_cases.json 的哈希（s1-freeze.json 内登记），不是 s1-freeze.json 文件本身的哈希（8a00c0dd…）；标注易误读，建议写为"test_sha256 = test_cases.json 哈希（见 s1-freeze.json 登记）"。
3. §6 "../evidence/simulation/v005/" 相对路径基准与同节其它条目不一致（其余相对 s6-v3 目录；该条按同基准应为 `simulation/v005/`）；目标存在，仅写法问题。
4. report.json 未记录命令行 flag（--restart/--all/--port 等），复测者需依赖文档/修订记录推断第三轮使用了 --restart；建议 runner 把 argv 写入报告。
5. manual_download.json downloaded_at.exact_time=null（仅有 confirmed_complete_before=13:30:09Z）；有界证据可用，但建议补记用户确认时刻。
6. §4 实测压缩链"30→复位→28→复位→33→40→44"与原始观测序列（0,1,30,33,28,0,34,40,44）顺序略异；实质结论（越限复位重启、终点 40/44）不受影响。

## 独立结论

**同意候选判定（fix2 主批次 31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL，2132 项比对全部吻合）。**

理由：§1/§2 全部数字经我独立对三份 report.json 重算一致；UNVERIFIED 拆解 162/7/2/2 与用例归属逐项核实；身份链（source.fxil→canonical 指令流→指纹字→D302/D303 回读）经 check_build_identity.py 独立重跑 PASS 且与烧录绑定、只读探针三处互证；§6 证据索引完整在位、runner 参数可复现主批次形状；旧证据零覆盖；边界声明未越权、仿真分歧明确为待办；候选判定状态标注合规。上述 1 项 major 属公共区工具链隔离遗留（未提交、不影响本轮 HIL 证据），6 项 minor 属表述/记录级，均不推翻判定；修复建议不改变"31 PASS/31 UNVERIFIED/0 PROGRAM_FAIL、整体 UNVERIFIED（候选）"的判定内容。

## 未查项

- §3.1 "两帧之间 ≈90 个扫描周期窗口"无法从现余证据独立复算（原 FC06 逐字实现已被替换，无该版本代码留档）；以 smoke1 的 M0=1 实证与 smoke2/3 零失配作为行为链佐证。
- 公共区未提交改动的逐行内容审查（属仓库治理，非本轮范围）；gui-20261108-* 三个 GUI 会话记录未逐条审阅。
- COM5 STOP/RUN 硬件动作的实际正确性与现场授权（无法在本复核中上电验证）。
- HMI 三件套与 PLC 程序同步演进状态（超出本轮复核范围）。
- 仿真 oracle 缺陷修复与 STD-031 族冻结预期复核（§4 待办，尚未发生，无法查证）。
