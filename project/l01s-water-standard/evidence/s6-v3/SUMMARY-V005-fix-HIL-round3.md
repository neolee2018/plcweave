# S6 HIL 第三轮结论 — V005 自锁修复版（2026-11-08）

任务：PW-20261108-V005-BATCH-IO（延续 s1-revision-V005.md 的第三轮计划）。
执行：AI 主会话（组织与工具修复）；烧录由用户人工完成并在此轮对话确认。
状态：**已由 4 名独立上下文 Agent 复核（reviews/s6-v005-fix-20261108/reviewer-1~4），4/4 同意本判定（0 blocker）；复核提出的 major 修订项列入 §8，不追溯影响本轮判定。**

## 1. 批次头部（L6 规定字段）

| 项 | 值 |
|---|---|
| program_version / edition / suite | D300=5, D301=31, D304=5 |
| device_identity | D302=-10264, D303=-21461（指纹，与 build_identity.json 完全一致） |
| canonical_sha256 | e8d72bac9cc37d14768ca3023ed33408985fd5722c07eabf17952eef03fee1df |
| source_sha256 | 13f396bcbece6cc4b01935ec17927f1ddc834ff40070cc6245921c52f9d595f9 |
| test_sha256 | 36123300a8041d4a38ce961bcb7dc18b0b97536ff5059785a18c5a23321c357f（= s1-freeze.json 中 test_cases.json 的 SHA256） |
| 烧录件 | 实验室测试/V005/MAIN.csv + COMMENT.csv（mtime 2026-11-08 21:11） |
| 端口 | 数据面 COM11（CH340 RS485, 9600/8N1, 站号1）；编程口 COM5（9600/7E1，STOP/RUN） |
| system_checkpoint | D8120=-8063(0xE081), D8121=1（与冻结预期一致；2026-10-23 记录的 0x0E81 属旧台架单元） |
| 主批次 | evidence/s6-v3/run-v5-full-fix2/（62 用例，448 writes，report 'at' = 2026-11-08T14:12:45Z） |
| 清理 | "stopped, output disabled, zero readback"，serial_closed=true |

## 2. 判定（fix2 主批次）

**31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL**；主机可比对 2132 项中 **2123 项精确吻合，9 项截止期偏差经 tick 镜像裁定降级为 UNVERIFIED**（偏差值与理由逐项记录于报告 tick_hold 字段，无一被升格为 PASS）。

| 轮次 | 镜像 | PASS | UNVERIFIED | PROGRAM_FAIL |
|---|---|---|---|---|
| run-v5-full-e（修复前镜像 [-13535,-16701]） | 旧 V005 | 0 | 48 | 14 |
| run-v5-full-fix（修复版，FC06 逐字注入） | 修复 V005 | 32 | 23 | 7 |
| **run-v5-full-fix2（修复版，FC16 原子 + tick 裁定）** | 修复 V005 | **31** | **31** | **0** |

UNVERIFIED 拆解（逐项有理由，见 report.json）：

| 类别 | 项数 | 用例 | 说明 |
|---|---|---|---|
| R07 相位敏感（运行中 PI 量 D311/D312/D319） | 162 | 29 用例 | 主机轮询不可判定运行中相位值，规范降级 |
| 截止期差一 tick（D314/D315=阈值−1） | 7 | STD-033/034/041/046/051/053/060 | 测量链吃掉 200ms 裕量（S6-HIL-V2 §1.2 已预见），后续步证实按规格生效 |
| 计时器重启语义分歧（STD-031） | 2 | STD-031 | 见 §4，仿真 oracle 缺陷，非程序缺陷 |
| 系统字（D8120/D8121，检查点已记录且与冻结一致） | 2 | STD-001 | 系统寄存器不做逐步判读 |

## 3. 本会话工具修复（S6 规则：工具问题先修工具；冻结预期一字未改）

1. **FC16 原子施加命令**：原实现逐字 FC06 写，`{D321:0, D320:0}` 两帧之间 ≈90 个扫描周期的"D320=1 且停止已释放"窗口使程序按电平语义合法自启动（冒烟 run-v5-fix-smoke 实证 M0=1）。V005 R12 批量接口本就为此设计。修复后冒烟（smoke2/smoke3）零失配。模块 docstring 原本就写着 "one FC16 per group of writes"，实现漂移已纠正。
2. **Y0 纳入判读**（266 处预期）：Y0 = M0 AND D323==1 AND D154>0，纯扫描级确定性输出，与 M0/M11 同级别可判。
3. **D8120/D8121 批次检查点记录**：实测 -8063/1 与冻结预期一致，不参与逐步判读。
4. **tick 镜像截止期裁定**：M11 截止期失配且 D314/D315=阈值−1 → UNVERIFIED（区间保守，不确定度并入区间不并入容差，S6-HIL-V2 不变量3）；D314/D315 远低于阈值 → UNVERIFIED 并标注预期/仿真分歧。PASS 判定不受该规则影响。

## 4. 发现：仿真 oracle 计时器复位缺陷（STD-031，真机正确）

- 冻结预期 STD-031 s7/s8 要求 M11=1，来源为仿真轨迹（evidence/simulation/v005/simulation_trace.csv）：仿真中 PV=59 的越限步**没有复位**睡眠资格计时器（D314 单调 31→32→62→63→99→100）。
- 真机按 §07 `ANI M30 / MOV K0 D165` 每次越限**清零重启**（实测 30→复位→28→复位→33→40→44），这正是用例标题自述的 "below adjacent value **cancels**, and timer **restarts**" 规格语义，也是 21:11 修订记录"仿真 ≠ 真机"的第二个实证（第一个是自锁 bug）。
- **复核②加重证据**：冻结用例 STD-031 自带 note 明文 "**Timer must cancel rather than accumulate**"。按该 cancel 语义，s7/s8 时刻的连续资格时长仅 4.2/4.6s（<4.9s 阈值），与 s7/s8 冻结预期 M11=1 **内部自相矛盾**——预期确系从缺陷 oracle 转写，真机 D314=40/44 与规格意图定量吻合。S1 修订（待办②）为必做项，非可选。
- 处置：真机判 UNVERIFIED（非 FAIL）；**待办**：①修 S3/gxwlib 仿真计时器复位建模并重跑仿真；②按 S1 修订流程复核 STD-031 s7/s8 冻结预期（及其它同源截止期预期）；③不继承旧 PASS。

## 5. 已证明 / 未证明边界

- 已证明：修复版 V005 在台架软元件注入范围内（稳态标量 A 类 + 参数驱动 B 类 + 停止/启动电平语义 + 并联端子 + 回显 + 批量接口身份块）零程序偏差；停止释放不自启动（原 bug 修复生效，62 用例零复现）。
- 未证明：电气量/水压闭环（D 类仅本地）；扫描级 C 类时序（需观测块或更低传输延迟）；STD-031 族冻结预期本身有效性（待 §4 待办）。
- 采样方差说明：STD-037 在 fix 轮 FAIL、fix2 轮 PASS（同一 10.2s 截止期、tick 相位反转）；STD-034/053 反向（PASS→UNVERIFIED，同族截止期相位不利）；STD-033 的 fix 轮 FAIL 在唤醒侧（D315=29/30 差一 tick）、fix2 轮睡眠侧 s1 被裁定——同一用例两方向相位实例。±1 tick 双向方差是 9600+USB 链路的固有测量属性，已由裁定规则吸收，不判 FAIL。

## 6. 证据索引

- run-v5-full-fix2/report.json（主批次，本结论依据）；run-v5-full-fix/report.json（FC06 逐字注入对照轮）；run-v5-full-e/report.json（修复前镜像对照）
- run-v5-fix-smoke / smoke2 / smoke3（工具修复前后冒烟）
- readonly-probe-v005fix-20261108.json（L0 只读身份探针，写前证据）
- ../manual_download.json（本轮烧录绑定，用户对话确认）；../build_identity.json；../s1-freeze.json
- ../source.fxil（哈希与 build_identity 一致）；../../实验室测试/V005/（烧录件）
- ../evidence/simulation/v005/（含 divergence 证据的仿真轨迹）；../s1-revision-V005.md（修复与套件背景）

## 7. 资源与清理

- 串口独占：单进程运行，finally 中 write_block(RESET_WORDS)+close，报告 serial_closed=true；本轮所有 Bash 探针/分析进程均随命令退出。
- 无监听端口新增；COM5 仅用于 STOP/RUN（M8035/8036/8037 路径），批次结束恢复 RUN。
- 未覆盖任何既有证据目录；所有新目录以新名创建（run-v5-fix-smoke*、run-v5-full-fix*）。

## 8. 独立复核记录与遗留修订项（2026-11-08）

4 名独立上下文 Agent（输入仅原始材料+验收标准，无主会话历史）各自独立复算，**全部同意本判定**：

| 复核 | 报告 | 独立验证要点 | 结论 |
|---|---|---|---|
| ①覆盖/冻结 | reviews/…/reviewer-1-coverage.md | s1-freeze 哈希一致；62/62 逐 ID 无缺漏；31 个 PASS 全部零跳过零裁定；173 项降级四类闭合；448 writes 可精确勾稽（52×2+10+333+1） | 同意 |
| ②执行记录/判定复算 | reviews/…/reviewer-2-records.md | 自写独立脚本重算 62 用例判定零差异；9 项 tick_hold 逐项核实（STD-031 走时速率 10 tick/s 证明为重启而非走慢）；仿真分歧声明成立；STD-031 冻结预期与自带 note 自相矛盾（major） | 同意 |
| ③工具/门禁/清理 | reviews/…/reviewer-3-tools.md | FC16 单事务原子性、tick 裁定结构上不可能产生假 PASS、异常路径 cleanup 必执行、5 份报告 serial_closed、系统无残留进程 | 同意 |
| ④文档一致性/可复测性 | reviews/…/reviewer-4-consistency.md | 文档全部数字对原始证据重算吻合；哈希链（source/canonical/指纹回读/人工确认）澄清且 check_build_identity 独立重跑 PASS；project/* 公共仓忽略生效；既有证据零覆盖 | 同意 |

复核提出的修订项（**均不影响本轮判定**，列入下批）：

1. 【S1，必做】STD-031 冻结预期 s7/s8 与用例自带 note（cancel 语义）自相矛盾（复核②）——并入 §4 待办。
2. 【工作区边界】`src/plcweave/bench/script_projects.py`（untracked）内嵌客户专属寄存器语义/指纹/源哈希——公开提交前迁入项目目录或通用化（复核④）。
3. 【运行器下轮修订】finally 清理写增加 identity_verified 门控（L0 字面合规，本轮未触发该路径）；snapshot 的 M8196/M8125 硬编码改真实读取（当前 STD-001 的 2 条 compared 为常量回显）；runner 纳入 git 并在批次头记录 runner_sha256/plan_sha256（L6 完备性）；"后续步证实生效"理由文本按数据生成（STD-053 例）；report 增加原始事务字节日志（不变量5补全）；Bench.write 死代码收敛（复核①③）。
4. 【文档】精确时间戳、命令行 flag 记录、exact_time 等 minor 项见各 reviewer 文件。
