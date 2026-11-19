# 独立复核报告 ①：需求与测试覆盖 / 独立性复核

- 复核对象：evidence/s6-v3/SUMMARY-V005-fix-HIL-round3.md（V005 自锁修复版 S6 HIL 第三轮候选判定）
- 复核人角色：独立复核 Agent ①（需求与测试覆盖/独立性），与主会话完全独立，未采信任何既有结论，全部数字自行重算
- 复核日期：2026-11-08
- 复核方式：只读检查（python -I 解析 JSON、hashlib 重算哈希、逐 ID 对比、逐 step 核对），未修改任何被复核文件，未执行任何 HIL/仿真（无硬件介入）

## 1. 输入文件清单与自行重算的哈希

| 文件（均在 F:\000-HBDTECH-Neo\103-plcweave\project\l01s-water-standard\ 下） | 说明 |
|---|---|
| s1-freeze.json | 冻结记录（185 B，mtime 2026-11-08 20:13，早于运行 22:12:45） |
| requirements.md | 作者源（9 538 B，mtime 2026-11-08 15:17） |
| test_cases.json | 冻结用例集（142 358 B，mtime 2026-11-08 20:13） |
| run_hil_v3.py | 运行器（mtime 2026-11-08 22:12:35，先于主批次起始 22:12:45） |
| evidence/s6-v3/run-v5-full-fix2/report.json | 主批次报告（复核对象） |
| evidence/s6-v3/run-v5-full-fix/report.json、run-v5-full-e/report.json | 对照轮 |
| evidence/s6-v3/run-v5-fix-smoke / -smoke2 / -smoke3/report.json | 工具修复前后冒烟 |
| evidence/s6-v3/readonly-probe-v005fix-20261108.json | 写前 L0 只读身份探针 |
| build_identity.json、source.fxil、manual_download.json、实验室测试/V005/MAIN.csv、COMMENT.csv | 身份与烧录绑定 |

自行用 hashlib 重算的哈希（python -I）：

| 项 | 冻结记录值 | 实际重算值 | 一致 |
|---|---|---|---|
| requirements.md | b170bc942ed4ce455d7363f7a4ab99b48ff62dfab7dd0e510c2ee7929290fc02 | 同左 | 是 |
| test_cases.json | 36123300a8041d4a38ce961bcb7dc18b0b97536ff5059785a18c5a23321c357f | 同左 | 是 |
| test_cases.json 内嵌 requirements_sha256 | — | b170bc…fc02，与 requirements.md 实际哈希一致 | 是 |
| source.fxil（对照 build_identity.source_sha256） | 13f396bcbece6cc4b01935ec17927f1ddc834ff40070cc6245921c52f9d595f9 | 同左 | 是 |

build_identity.json 与 report.json identity（D300=5, D301=31, D302=-10264, D303=-21461, D304=5）、readonly 探针（13:29:46Z，写前，心跳/扫描计数推进）三者一致；canonical_sha256（e8d72bac…ee1df）为 build_identity 记录值，**未由我独立重算**（需规范解码算法，见 §6 未查项）。烧录件 MAIN.csv/COMMENT.csv mtime 2026-11-08 21:11、manual_download.json mtime 21:30，与候选 §1 一致。

## 2. 逐条实际检查

### 标准 1：冻结完整性 —— 通过
见上表。两个哈希均与 s1-freeze.json 完全一致，且 test_cases.json/requirements.md 的 mtime（20:13/15:17）均早于主批次运行（22:12:45），文件自冻结后未被改动。候选 §1 所引 test_sha256 与冻结记录一致。

### 标准 2：覆盖完整性 —— 通过
- test_cases.json 冻结 62 条（STD-001..STD-062，无重复）。
- run-v5-full-fix2/report.json：62 条，逐 ID 对比 **缺漏=[]，多余/替换=[]，顺序与冻结序完全一致**。
- 状态分布（我自行 Counter 统计）：PASS=31，UNVERIFIED=31，PROGRAM_FAIL=0，TEST_INFRA_ERROR=0 —— 与候选 §2 一致。
- report.at=2026-11-08T14:12:45Z（起始），progress.json/report.json mtime 22:33:21/22:33:22（本地，即 14:33Z 完成）；writes=448。
- compared_items 合计=2132，skipped=164，tick_hold=9，ambiguous=0，step 级 mismatches（硬失配）=0。

### 标准 3：判读合法性（白名单 + PASS 抽查）—— 通过，附 1 项 major 缺陷（见 §3 F-1）
白名单覆盖核对（期望设备全集取自 test_cases.json 全部 62 案的 expect+invariant）：
- 期望设备全集 = {D300,D301,D304,D308,D309,D310,D311,D312,D313,D317,D320,D321,D322,D323,D325,D330,D333,D334,D335,D8120,D8121,M0,M11,M8196,M8125,Y0}。
- 其中 ALWAYS 覆盖静态/注入确定量（D300-D304、D308-D310、D313、D316-D318、D320-D335），STATE 覆盖 M0/M11/Y0，ZERO_ONLY（D311/D312/D319）仅在 M0==0 或（M11==1 且期望 0）时比对，D8120/D8121 为 SYSTEM 记录不判读。**全集内没有任何设备落入"无白名单而静默漏判"**；未判的 D305 心跳/D306 扫描计数/D307 位图计时位/D314/D315 计时镜像属运行中动态量，按 oracle_contract（主机轮询不证明扫描级 oracle）记 UNVERIFIED 是规范降级，不是漏判。唯一区间型期望 STD-029 D311{2000..4999} 被跳过（sim-oracle 材料），1 项，已计入 skipped。
- PASS 抽查：**实际核查了全部 31 个 PASS 用例（超出要求的 5 个）**，逐 step 检查 skipped、tick_hold、ambiguous、mismatches：31/31 全部为 0，无一例靠跳过换 PASS；每案 compared_items 12..223，无零比对 PASS。样例 STD-037（候选 §5 提及的方差用例）：fix 轮 PROGRAM_FAIL（step2 M11 期望1实测0）→ fix2 轮 PASS（41 compared，0 skip，0 hold），与"tick 相位双向方差、裁定规则只降级不升级"的解释一致。
- 判定逻辑核验：run_case 的 PASS 要求所有 asserted 步为 PASS 且 skipped==0；仅含 skip 的步必为步级 UNVERIFIED，从而传染到案级——不存在空洞 PASS 通路。

### 标准 4：注入边界 —— 通过
- test_cases.json 全部 459 步的 write 键去重后 16 个（D320..D335 全部 16 字），**全部落在 D320..D335**；10 个用例的 initial_words 键（D320,D321,D322,D323,D325,D333）同样全部在命令块内。
- writes=448 可精确重建：52 案×2（reset 两帧）+ 10 案×1（restart_with）+ 333 个非空 write 步×1（每步一帧 FC16）+ 1（清理）=448，与 report 一致。
- 运行器写路径审查（grep 全文）：`apply_commands` 强制校验 320..335（越界抛 ValueError）；`write_block` 固定从 D320 写 16 字；reset/清理均走 write_block；identity_gate 只读。**现行执行路径不存在写 D300..D319 的通路**。唯一隐患：`Bench.write`（FC06 单字）的 ALLOWED=D300..D335 含状态/身份区，但**全文无任何调用点**（死代码），见 §3 F-5。
- COM5 编程口仅 force M8035/8036/8037（STOP/RUN），非寄存器写，不涉 D 区。

### 标准 5：UNVERIFIED 合法性 —— 通过，1 项 minor 文本问题（F-3）
- 31 个 UNVERIFIED 用例的 step 级 mismatches（硬失配）数组**全部为空**（全局合计 0），ambiguous 合计 0——不存在被 UNVERIFIED 掩盖的真实失配。
- 逐项理由分类（我按 reason 文本自行归类并数）：

| 类别 | 我数出的项数 | 用例数 | 用例清单/佐证 | 候选 §2 表 |
|---|---|---|---|---|
| R07 相位敏感（D311=68/D312=30/D319=64） | 162 | 29 | reason="Running PI/analog value…" | 162/29 ✓ |
| 截止期差一 tick | 7 | 7 | STD-033/034/041/046/051/053/060，实测 D314=99/100 | 7/7 ✓ |
| 计时器重启语义分歧 | 2 | 1 | STD-031，step7/8 D314=40/100、44/100 | 2/1 ✓ |
| 系统字 D8120/D8121 | 2 | 1 | STD-001（批次检查点 -8063/1 与冻结一致） | 2/1 ✓ |

- 合计 173 项 = skipped 164 + tick_hold 9，闭合；四类**并集恰为 31 个 UNVERIFIED 用例，无未归类项**。
- 7 个 one-tick 用例的"后续步证实生效"抽查：STD-033/034/041/046/051/060 在 step1 后均有 M11 期望1实测1 的比对步（如 STD-033 step2-4），生效确被观测；**STD-053 例外**（见 F-3）。
- STD-031 分歧解释的独立佐证：主批次实测 D314 序列 30→33→28→**0**→34→40→44——每次 PV 跌破 SV（D308=59<60）计时器被清零重启、从未到 100，与"真机按 §07 ANI M30/MOV K0 D165 重启、仿真 oracle 单调累加"的读法相符（候选 §4 引用序列的数字顺序与实测略有出入，见 F-6，不影响结论）。因此该 2 项判 UNVERIFIED（而非 FAIL）合法：分歧源在冻结预期所依赖的仿真 oracle，处置（修 oracle、按 S1 流程复核 STD-031 族预期、不继承旧 PASS）符合仓库规则。

### 标准 6：四态纪律 —— 通过
- 冻结文件未改（标准 1 哈希证据）；运行器为精确相等比对，**无任何容差参数**；tick 裁定只把 M11 截止期失配降级为 UNVERIFIED，从不升为 PASS（fix 轮 7 个 FAIL 在 fix2 轮变为 6 UNVERIFIED + STD-037 真实 PASS，0 FAIL）。
- PASS 不靠跳过：31/31 案 skipped=0（标准 3）。
- 诚实降级链条完整：smoke（FC06 窗口，STD-059/062 FAIL）→ smoke2/smoke3（FC16 后硬失配 0、ambiguous 0，其余为合法 skip）→ fix 轮 7 FAIL 如实记录 → fix2 0 FAIL；report.status=UNVERIFIED（未把 31 PASS 拔高成整批 PASS）。
- 工具修复三项（FC16 原子施加、Y0 纳入判读、tick 镜像裁定）均为收紧或恢复冻结语义（REL-09 命令字语义、oracle_contract 原子施加），未触碰冻结预期；对照轮 run-v5-full-e（0/48/14，旧指纹 [-13535,-16701]）与 fix 轮（32/23/7）分布均与候选 §2 表逐项一致，已独立重算确认。

## 3. 发现的问题

**Blocker：无。**

**Major：**

- **F-1（运行器缺陷，未翻转任何本轮判定）**：run_hil_v3.py `snapshot()` 将 `M8196`/`M8125` **硬编码为 1**（注释称"initialized first scan"），而非真实线圈读取。test_cases.json 中恰有 STD-001 step0 对 M8196=1、M8125=1 的期望，该步的 compared 流中这两条"吻合"是伪造观测（report 中可见 expected=1/actual=1）。影响面：仅 STD-001 的 2/2132 条 compared 项；STD-001 因 D8120/D8121 为系统字已合法 UNVERIFIED，且 31 个 PASS 用例均不含 M8196/M8125 期望，故**没有任何判定被该缺陷改变**，"31 PASS/31 UNVERIFIED/0 FAIL"与 UNVERIFIED 分类不受影响。但 compared 证据流中混入非观测项违反"不自证"纪律，要求：后续修复为真实 FC01 读取（同 Y0 的 0x3300 方式）或显式列入 SYSTEM 类记录不判读，并重跑/补充该类证据。

**Minor：**

- **F-2**：候选 §2 "2132 项主机可比对全部吻合"表述不精确：实测 2123/2132 条 expected==actual，9 条 M11（期望1实测0）经 tick_hold 重分类为 UNVERIFIED。候选自己的 §2/§4 表已如实列出这 9 条，属措辞夸大而非掩盖，建议改为"2132 项比对，2123 项吻合、9 项按 tick 裁定降级"。
- **F-3**：STD-053 的 tick_hold 理由模板声称 "engagement observed in subsequent steps"，但该案 step2 起冻结预期即为 M11=0（无效模式清除休眠→释放→重启），后续步从未观测到 M11=1，"生效被证实"对 STD-053 不成立。分类仍为 UNVERIFIED（保守、无纪律问题），但理由文本是模板而非逐案事实，应修正措辞或对该案改用"无法在主机采样下证实生效"。
- **F-4**：run_hil_v3.py 未纳入 git（`??` 未跟踪），report.json 也未记录运行器哈希；其 mtime（22:12:35）仅先于运行起始（22:12:45）10 秒，内容一致性目前只有旁证（fix2 报告的 tick_hold 字段、系统检查点、理由文本与现行代码逐字吻合；fix 轮报告案级无 tick_hold_items，恰与"裁定规则在 fix 轮之后加入"的叙述一致）。建议：将运行器纳入版本管理并在 report 头部写入其 SHA256。
- **F-5**：`Bench.write` 的 ALLOWED=D300..D335 含状态/身份区（死代码，无调用点），建议收紧到 D320..D335 或删除，消除未来误用通路。
- **F-6**：候选 §1 引用主批次时间"at 2026-11-08T14:24:53Z 前后"，而 report.at=14:12:45Z、完成 14:33:22Z；§4 引用的 STD-031 D314 序列数字顺序与实测（30→33→28→0→34→40→44）略有出入。均为引用瑕疵，不影响判定。

## 4. 独立结论

**同意候选判定**（31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL；主批次 run-v5-full-fix2 证据链成立）。

理由：六项验收标准全部独立重算通过——冻结哈希一致且先于运行；62 条用例零缺漏零替换；PASS 全部为真实比对（无跳过换 PASS，31/31 逐步干净）；注入严格限于命令块且 writes=448 精确闭合；31 个 UNVERIFIED 全部有合法降级理由、无硬失配被掩盖、分类计数与候选表格逐项一致；无放宽容差/改预期/降级换 PASS 迹象。发现 1 项 major（F-1 运行器伪造 M8196/M8125 观测）经验证未影响任何本轮判定（受影响用例本就 UNVERIFIED，PASS 用例不含该类期望），作为待修项记录，不阻断本候选判定成立，但该缺陷修复并补证前，STD-001 涉及 M8196/M8125 的 compared 证据不应被引用为"已观测吻合"。

## 5. 未查项（明确声明）

1. 未执行/复跑任何 HIL 或仿真（本轮为纯只读证据复核；COM11/COM5 上的真实设备行为无法由我独立复现）。
2. 未独立重算 canonical_sha256（e8d72bac…）——需按 S2 规范化算法从指令表解码，超出本角色范围；仅核对了 source.fxil 与 build_identity.source_sha256 一致。
3. 未审计 source.fxil 指令级实现正确性与 V005 R12 批量接口本身（S2/S5 范畴），仅核对其哈希与身份绑定。
4. 未复核 S1 需求覆盖充分性（R01..R12 是否被 62 案完整覆盖的充分性论证）——本轮只验证"冻结的 62 条被完整执行"，需求↔用例映射质量属 S1 复核范畴。
5. 未读取 evidence/simulation/v005/simulation_trace.csv 亲自复现仿真 oracle 缺陷（以主批次实测 D314 序列独立佐证了真机侧重启语义，仿真侧未独立验证）。
6. 未复核 hmi/、delivery/、archive/ 及 run-v3/v4 历史目录；未复核 L01S 台架接线/CH340 映射的物理事实（采信只读探针与 identity_gate 的记录）。
7. 未验证烧录动作本身（用户人工烧录）；仅核验烧录后设备内的身份块与探针/报告一致。
