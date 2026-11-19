# 独立复核报告 ② — 程序、执行记录与判定复算（V005 修复版 S6 HIL 第三轮）

- 复核人角色：独立上下文 Agent ②（判定复算与记录核查），与主会话完全独立，未读取其它复核人结论。
- 复核日期：2026-11-08
- 被复核候选结论：`evidence/s6-v3/SUMMARY-V005-fix-HIL-round3.md`
- 复核方法：全部用本 Agent 自写的独立 Python 脚本（stdin 内联执行，未调用运行器 `run_hil_v3.py` 的任何函数）从原始 report.json / simulation_trace.csv / 冻结用例 / 程序源码自行复算；运行器代码仅作语义理解参考，不参与判定。
- 环境说明：解析器为 `F:\000-HBDTECH-Neo\103-plcweave\.venv\Scripts\python.exe`（`-I` 隔离模式）。除本文件外未写入/修改任何文件。

## 0. 输入清单（全部相对 project/l01s-water-standard/）

| 输入 | 说明 |
|---|---|
| evidence/s6-v3/run-v5-full-fix2/report.json | 主批次，62 用例，at=2026-11-08T14:12:45Z，port=COM11 |
| evidence/s6-v3/run-v5-full-fix/report.json | FC06 逐字注入对照轮，at=13:42:50Z |
| evidence/s6-v3/run-v5-full-e/report.json | 修复前旧镜像轮，at=12:38:03Z |
| evidence/simulation/v005/simulation_trace.csv | 109266 行仿真轨迹 |
| test_cases.json | 冻结用例（62 条） |
| source.fxil | 程序源（V005 修复版） |
| build_identity.json / manual_download.json / s1-freeze.json | 身份与烧录绑定 |
| evidence/s6-v3/readonly-probe-v005fix-20261108.json | L0 只读身份探针 |
| C:\Users\MasterNeo\.agents\skills\plc-program-development\references\s6-hil-v2.md | 方法规范 |
| 实验室测试/V005/MAIN.csv、COMMENT.csv | 烧录件（mtime 2026-11-08 21:11，实测确认） |

## 1. 判定复算（验收标准 1）— 结论：31/31/0 成立

独立四态规则（按任务给定语义，case 级聚合）：
- 任一 step 的 `mismatches` 非空 → PROGRAM_FAIL；
- 有 compared 项、全部"已断言 step"（compared/skipped/hold 非空的 step）由我自算的 step 级四态判 PASS、case 级 skipped==0、tick_hold==0 → PASS；
- 否则 UNVERIFIED。step 级 PASS 由我从 compared/mismatches/ambiguous/tick_hold/skipped 原始列表自算，不读报告内 status 字段。

自算结果 vs 报告 status 字段：

| 轮次 | 用例数 | 我自算 | 报告内 status | 差异 |
|---|---|---|---|---|
| fix2 | 62 | PASS=31, UNVERIFIED=31, PROGRAM_FAIL=0 | PASS=31, UNVERIFIED=31, PROGRAM_FAIL=0 | 0 |
| fix | 62 | 报告表 32/23/7 | PASS=32, UNVERIFIED=23, PROGRAM_FAIL=7 | 0 |
| e-old | 62 | 报告表 0/48/14 | PASS=0, UNVERIFIED=48, PROGRAM_FAIL=14 | 0 |

辅助计数全部吻合：fix2 `compared_items` 字段合计 2132 = 我从 steps 重算的 2132；skipped 合计 164（R07 相位 162 项/29 用例 + 系统字 D8120/D8121 2 项/STD-001）；ambiguous 0；tick_hold 9。与候选 §2 表及 UNVERIFIED 拆解表逐项一致。

口径说明（复算过程中发现的两处语义细节，非错误）：
1. 报告的 `compared` 列表是"可比对项及其实测值"（含 expected≠actual 的项），偏差项同时记录在 tick_hold/mismatches。因此候选 §2"2132 项主机可比对全部吻合"措辞偏宽：2132 为可比对项总数，其中 2123 项精确吻合，9 项在采样瞬间 M11=1 的预期未满足（即 9 个 tick_hold）。判级不受影响（该 9 项已按裁定规则入 UNVERIFIED）。
2. 62 用例中有 3 例（STD-037 s6、STD-042 s1、STD-044 s1）各含一个无 compared 的纯等待 step（step 级 UNVERIFIED）；按"已断言 step 全部 PASS"的 case 级语义这 3 例判 PASS 是正确的（我按更严格字面口径复算过一次得 28/34，属口径差异，已按正确语义复核为 31/31/0）。

## 2. tick 裁定抽查（验收标准 2）— 结论：9 项 observed 全部支持分类；后续步证据 6/7 成立

fix2 全部 9 个 tick_hold（M11 expected=1, actual=0）的 observed 核实：

| 用例/步 | D314 | D315 | D327 | D328 | ticks/阈值 | 分类 | 后续步 M11=1 证据 |
|---|---|---|---|---|---|---|---|
| STD-031 s7 | 40 | 0 | 100 | 30 | 40/100 | 计时器重启分歧 | （s8 为末步，无后续） |
| STD-031 s8 | 44 | 0 | 100 | 30 | 44/100 | 计时器重启分歧 | — |
| STD-033 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | s2–s4 M11=1 ✓ |
| STD-034 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | s2、s7 M11=1 ✓ |
| STD-041 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | s2 M11=1 ✓ |
| STD-046 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | s2 M11=1 ✓ |
| STD-051 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | s2 M11=1 ✓ |
| STD-053 s1 | 99 | 0 | 100 | 30 | 99/100 | 差一 tick | ✗ 无（见下） |
| STD-060 s1 | 99 | 0 | 100 | 50 | 99/100 | 差一 tick | s2 M11=1 且 D315=38/50 ✓（与 5s 唤醒延迟定量一致） |

- 7 个"差一 tick"项 D314=99 恰等于阈值−1（D327=100），符合裁定规则；STD-031 两项 ticks=40/44 远低于阈值，符合"重启分歧"分类。D315 全程为 0（D315 是唤醒侧镜像，本批无唤醒侧 hold）；候选 §2 写"D314/D315=阈值−1"不精确，实为仅 D314。
- STD-031 计时器速率核验：s6→s7 34→40（+6/0.6s）、s7→s8 40→44（+4/0.4s），10 tick/s 正常走时，证明是"从 0 重启后走时正常"而非走时偏慢。
- STD-053 注意项：该用例 s2 起写入无效模式 D322=2（同拍清除休眠、需释放重启），后续步按设计 M11=0，因此其 tick_hold 模板理由"engagement observed in subsequent steps"对该用例不成立（无直接后续翻转证据；支撑仅有 D314=99/100 的截止期本身）。判级仍正确（UNVERIFIED），属文档瑕疵。

## 3. STD-031 仿真分歧声明核查（验收标准 3）— 结论：声明成立，且发现冻结预期内部矛盾的加重证据

(a) 仿真轨迹（simulation_trace.csv，case_id=STD-031 各 step 末行）：

| step | D330 写入 | PV(D308/D100) | D314 末值 | M11 |
|---|---|---|---|---|
| 2 | — | 60 | 31 | 0 |
| 3 | 1475 | 59 | 32 | 0 |
| 4 | 1488 | 60 | 62 | 0 |
| 5 | 1475 | 59 | 63 | 0 |
| 6 | 1488 | 60 | 99 | 0 |
| 7/8 | — | 60 | 0（已翻转） | 1 |

即 PV=59 的两个越限步（s3/s5）仿真计时器**不复位、单调累加** 31→32→62→63→99，随后达 100 使 M11=1——候选 §4"单调累加 31→32→62→63→99→100"成立（末位 100 为阈值穿越隐含值，轨迹直接观测为 99 后翻转）。仿真的 PV 模型本身正确（D308=59），缺陷被隔离在"M30 不满足时复位 D165"的建模缺失。

(b) 真机（fix2 report STD-031 各 step observed D314）：1, 30, 33, 28, 0, 34, 40, 44。两次复位均有实证：s3 采样 33（该拍 D330=1475 写入尚未被消费，属传输延迟）→ s4 采样 28 < 33，证明其间发生复位；s5 采样 0 为直接复位观测。候选括注"30→复位→28→复位→33→40→44"的次序标注与原始采样序列略有出入（实际 30→33→〔复位〕→28→〔复位→0〕→34→40→44），实质（每次越限清零重启）成立。

(c) 程序源核对：source.fxil §07 第 186–189 行确为 `LD M8000 / ANI M30 / MOV K0 D165`（M30=睡眠资格：PV≥SV 或频率≤无流转速；§08 为 `AND>= D165 D162 → SET M11`）。D165 每扫描镜像到 D314（第 312 行 `MOV D165 D314`）。真机行为与规格语义（用例标题自述 "below adjacent value cancels, and timer restarts"）一致，候选"真机行为更符合规格意图"成立。

(d) 加重证据（本复核新发现，major）：冻结用例 STD-031 自带 `expected_behavior_note` 明文写着 **"Timer must cancel rather than accumulate"** 且 "Event oracle requires 4.9..5.1s **continuously** high before each sleep transition"。按 cancel 语义，s7/s8 采样时刻的连续高电平时长仅约 3.6+0.6=4.2s / 3.6+0.6+0.4=4.6s，均不足 4.9s，故 s7/s8 应为 M11=0——与冻结预期 s7/s8 的 M11=1 **内部自相矛盾**。即冻结预期系从缺陷仿真 oracle 机械转写而来，且与本用例自身的 note 冲突。真机实测 D314=40/44 与 cancel 语义预测的 ~42/46 定量吻合。这使候选 §4 待办②（按 S1 修订流程复核 STD-031 s7/s8 冻结预期）更加必要；候选未擅自改冻结预期、判 UNVERIFIED 的处置正确。

## 4. 方差声明核查（验收标准 4）— 结论：STD-037 与 STD-034/053 成立；STD-033 描述不准确（实质仍支持）

| 用例 | fix 轮 | fix2 轮 | 核实细节 |
|---|---|---|---|
| STD-037 | PROGRAM_FAIL | PASS | fix s2：M11 exp=1 act=0，D314=99/100；fix2 同步（同一 10.2s 截止期）：M11=1、D314=0（已触发清零）。"tick 相位反转"属实 ✓ |
| STD-034 | PASS | UNVERIFIED | fix2 s1 hold 99/100，反向 ✓ |
| STD-053 | PASS | UNVERIFIED | fix2 s1 hold 99/100，反向 ✓ |
| STD-033 | **PROGRAM_FAIL** | UNVERIFIED | fix 轮失败点在 **s5 唤醒侧**（M11 exp=0 act=1，D315=29/30，唤醒差一 tick），不是 PASS→反向；候选"STD-033/034/053 反向"对 033 表述不准确（minor） |

fix 轮 7 个 PROGRAM_FAIL 全部为 M11 边界/分歧（STD-031: D314=39/43；STD-033: D315=29；STD-037/046/047/051/060: D314=99/100），fix2（FC16 原子注入 + tick 裁定规则）归零。"±1 tick 双向方差被裁定规则吸收"的实质有数据支撑：边界处 5 个用例在两轮间翻转方向不一。另核实 fix 轮 tick_hold=0、fix2 才有 9，证实裁定规则为本会话新增（候选 §3.4 叙述一致）；"PASS 判定不受该规则影响"亦核实（所有含 hold 用例均为 UNVERIFIED，无因 hold 而 PASS 者）。

## 5. 身份与清理（验收标准 5）— 结论：全部一致，writes=448 可完全勾稽

- identity 五字：D300=5 / D301=31 / D302=−10264 / D303=−21461 / D304=5，与 build_identity.json（program_version 5、edition 31、fingerprint [−10264,−21461]、suite_version_word 5）逐字一致 ✓；也与 manual_download.json、readonly-probe（identity_match=true、心跳与扫描计数均前进、13:29:46Z 早于批次 14:12:45Z）一致 ✓。
- system_checkpoint：D8120=−8063（即 0xE081 的有符号值）/ D8121=1 ✓。
- cleanup="stopped, output disabled, zero readback"、serial_closed=true；cleanup_state 实测 M0=0、M11=0、Y0=0、D311=0、D312=0、D320=0（停机零输出）✓。
- writes=448 独立勾稽：52 例 × reset 2 帧 + 10 例（STD-001..010 有 initial_words）× restart 1 帧 + 333 个带写入 step 的 FC16 各 1 帧 + finally 清理 1 帧 = 104+10+333+1 = **448**，精确吻合 ✓。
- 哈希自算验证：sha256(source.fxil)=13f396bc…95f9、sha256(test_cases.json)=36123300…357f、canonical e8d72bac…e1df，均与 build_identity/manual_download/候选表一致 ✓（注：候选把 test_sha256 标注为"（s1-freeze）"，其值实为 test_cases.json 文件哈希，可追溯但标注不严谨，minor）。
- e-old 轮 identity D302=−13535/D303=−16701，证实该轮跑的是修复前旧镜像，与候选对照表一致 ✓。
- 烧录件 实验室测试/V005/MAIN.csv、COMMENT.csv mtime 实测 2026-11-08 21:11，与候选一致 ✓。

## 6. 反向验证（验收标准 6）— 结论：通过，未发现误判

- fix2 全部 62×steps 的 `mismatches` 均为空（合计 0）；compared 中 expected≠actual 的项恰为 9 项，与 9 个 tick_hold 一一对应（同一批 case/step/device），无漏记或隐藏失配。
- 无"compared 实测缺失（None）"项（0 项）；所有 step 的 observed 字典完整（≥20 键，含 M0/M11/Y0/D300..D335），不存在 observed 缺失导致的误判。
- 含 tick_hold 的 8 个用例全部判 UNVERIFIED，无 hold 却 PASS/PROGRAM_FAIL 的用例；ambiguous 全批 0。
- fix 轮 7 个 FAIL、e-old 轮 14 个 FAIL 均逐一核实存在非空 mismatches，FAIL 判定与失配记录一致，无空判 FAIL。

## 7. 问题清单

**blocker：无。**

**major（1 项，加重候选既有待办而非推翻候选）：**
- M1：冻结用例 STD-031 的 s7/s8 预期（M11=1）与其自身 `expected_behavior_note`（"Timer must cancel rather than accumulate"、连续高电平 ≥4.9s 才触发）内部矛盾；预期系从缺陷仿真 oracle 转写。候选已将该用例判 UNVERIFIED 并列入待办②，处置正确，但 S1 修订前不得将 STD-031 族任何同源截止期预期当作有效 oracle（含其它由同一仿真轨迹转写的截止期预期）。

**minor（6 项，均为记录/措辞精度，不影响判级）：**
- m1：§2"2132 项主机可比对全部吻合"措辞偏宽——2132 为可比对总数，其中 9 项采样瞬间未吻合（已入 tick_hold/UNVERIFIED）。
- m2：§5"STD-033/034/053 反向"对 STD-033 不准确：其 fix 轮为 PROGRAM_FAIL（唤醒侧 D315=29/30 差一 tick），非 PASS→反向。
- m3：STD-053 tick_hold 理由模板"engagement observed in subsequent steps"对该用例不成立（后续步按设计 M11=0），宜逐项定制理由文本。
- m4：§2"D314/D315=阈值−1"不精确，实为仅 D314=99（D315 全 0，为唤醒侧镜像）。
- m5：§1 批次时间"at 2026-11-08T14:24:53Z 前后"与报告字段不符：report at=14:12:45Z（批始），report.json mtime=14:33:22Z（批末）。
- m6：report 头未含 L6 要求的 runner_sha256/plan_sha256/scan_period_ms/operator/downloaded_at 字段（runner sha 实测 b4b2db84…6a1c，operator/下载信息在 manual_download.json 中可追溯），建议后续批次补齐报告头。

## 8. 独立结论

**同意候选判定。**

理由：① 62 用例四态（31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL）由本 Agent 独立脚本从 step 原始 compared/mismatches/ambiguous/tick_hold/skipped 重算，与报告完全一致，无差异；② 9 个 tick_hold 的 observed 数值全部支持其分类，6/7 的截止期用例有后续步 M11=1 直接翻转证据；③ STD-031 仿真 oracle 计时器复位缺陷（越限不复位、单调累加）经仿真轨迹、真机采样、程序源 §07 `ANI M30 / MOV K0 D165` 三方独立证实，真机行为与用例自身标题及 note 的规格语义一致；④ 两轮方差确为 ±1 tick 采样相位差异，裁定规则吸收合理且未把任何不确定项拔高为 PASS；⑤ 身份、系统检查点、清理态、writes=448、哈希与烧录绑定全部独立核实一致；⑥ 反向验证未发现任何失配被掩盖或误判。候选整体收敛为批次 UNVERIFIED（不宣称全 PASS）与 S6-HIL-V2 不变量 2/3/4 一致。

## 9. 未查项（本角色范围之外或证据不可得）

1. 原始 Modbus 事务字节级日志（请求/响应帧）未留存于 report.json（仅有 compared/observed/observed_at_ms/chunk_checks），本复核未找到逐帧原始记录文件；S6-HIL-V2 不变量 5 的"原始事务留存"仅部分满足（有时间戳与比对值，无帧字节）。是否另有轨迹文件未查。
2. 未实际复跑硬件或串口通信，COM5 STOP/RUN 的物理执行仅有设计推断（10 个 initial_words 用例需重启，报告无 COM5 操作日志）。
3. 仿真 oracle 源码（S3/gxwlib 计时器复位建模缺失点）未定位——属程序/仿真实现复核角色。
4. Y0 判读口径（266 处预期）的逐项正确性未逐条复核，仅确认其存在于 compared 中且无失配。
5. 其它复核角色（覆盖完整性、工具链、一致性）的范围项未涉及。
