# 独立复核报告 ③ — 工具、异常路径、身份门禁与资源清理（V005 修复版 S6 HIL 第三轮）

- 复核人：独立复核 Agent ③（与主会话完全独立，未读取主会话结论作为前提）
- 日期：2026-11-08
- 被复核对象：`project/l01s-water-standard/run_hil_v3.py`（全文通读）＋ 候选结论 `evidence/s6-v3/SUMMARY-V005-fix-HIL-round3.md` §2/§3/§7 ＋ 证据 `evidence/s6-v3/` 下 run-v5-full-fix2 / run-v5-full-fix / run-v5-fix-smoke{,2,3} / readonly-probe-v005fix-20261108.json
- 方法规范：`C:\Users\MasterNeo\.agents\skills\plc-program-development\references\s6-hil-v2.md`（§3 设计不变量、L0/L2/L7）
- 复核方式：纯静态审查 + 证据字段抽取 + 只读系统查询；语法检查用内存 compile（未写任何 .pyc）；未运行任何会写串口的代码；未修改被复核文件。

## 0. 逐条验收结果总览

| # | 验收标准 | 结论 |
|---|---|---|
| 1 | 原子注入（apply_commands/write_block/tracking/sync） | **正确**，一处文案瑕疵 |
| 2 | 写白名单收敛到命令块 | **实际调用路径全部收敛**；`bench.write` 的 ALLOWED 过宽属死代码残留（minor） |
| 3 | 身份门禁先于写入 | **批次级成立**；restart_with 路径内 initial_words 写先于该次 gate（minor）；**finally 在门禁失败路径仍写入，违反 L0 字面规定（major）** |
| 4 | tick 裁定窄度 | **结构上不可能把失配变成 PASS**；理由文案与 SUMMARY §3.4 描述有两处不精确（minor） |
| 5 | 异常路径 cleanup | try/except/finally 结构成立，cleanup 必执行；mkdir(exist_ok=False) 生效 |
| 6 | 资源清理实证 | 5/5 报告 serial_closed=true、cleanup 达成零输出态；系统查询未见本轮残留进程/端口 |
| 7 | 语法与健壮性 | 内存 compile + AST parse 通过；发现若干 minor 健壮性/文案问题，无功能性 bug |

---

## 1. 检查清单与证据

### 1.1 原子注入（验收标准 1）— 通过

**代码事实**（行号以当前 run_hil_v3.py 为准）：

- `apply_commands`（L160–174）：先逐项校验 `D320<=addr<=D335` 并合并进 `self.command`（按槽位赋值，dict 各地址唯一，**合并顺序无关**），随后一次 `write_block(self.command)`。每步恰好一帧。
- `write_block`（L146–158）：长度硬校验 16，写址固定 320，全部 `& 0xFFFF`（负值正确转二补码），成功后回写 tracked 向量并计 writes。
- `words()`（L129–133）：读侧 `v>=32768 → v-65536` 符号还原正确。
- FC16 语义：pymodbus 3.15.0（本机 C:\Python313 默认解释器实测存在）的 `write_registers(320, [16值])` = 单条 Modbus FC16 请求，quantity=16，寻址 D320..D335 恰好 16 字，单事务内完成；PLC 在通信服务点整帧处理，用户程序下一扫描看到的是一致的全部 16 字——与仿真器原子施加语义等价。运行时证据：fix2 report `writes=448`、0 通信错误、identity/cleanup 回读正常。
- `sync_commands`（L176–179）：restart 路径中在 `identity_gate`（含心跳两读+0.3s 等待，远超首扫描）之后取 snapshot，把 **D320..D335 全部 16 字**（含题目列举的 D320/321/323/325/326/327/328/329/331/332/333/334/335 等首扫描会重初始化的字）整体覆盖为设备当前值，随后 apply_commands 从正确基线合并。无遗漏。
- 模块 docstring（L4）"one FC16 per group of writes" 与实现现已一致，印证 SUMMARY §3.1 "实现漂移已纠正" 的说法。

**瑕疵**：`write_block` 的异常文案写 `FC16 D{BLOCK_BASE}`（=D300），实际写址是 320，误导性小错误（minor m8）。

### 1.2 写白名单（验收标准 2）— 调用路径全部收敛，残留死代码

- 冻结用例全部写键：62 用例 steps.write 键 16 个，**全部落在 D320..D335**；initial_words 键 D320..D333。`apply_commands` 对越界键抛 ValueError；`write_block` 固定写 320。`reset()`/`cleanup`（finally）均走 `write_block(RESET_WORDS)`。CPU.force 仅 M8035/8036/8037，走 COM5 编程口（L7 授权路径）。
- grep 证实 `bench.write`（FC06，L135–144）在 run_hil_v3.py 内**零调用点**——是死代码。
- **残留风险**：`bench.write` 的 `ALLOWED = D300..D335`（L27–28）包含只读身份块 D300..D304 与状态块 D305..D319（心跳/位图/PI 量，程序所有，按 L2 分类不可写）。一旦未来被调用即可写穿身份区，且 FC06 逐字写会重新引入本轮修复掉的双帧窗口。建议收窄 ALLOWED 至 `{320..335}` 或直接删除该方法（minor m1，见 §2）。

### 1.3 身份门禁时序（验收标准 3）— 批次级成立；一处路径内偏差 + 一处 major

- **批次级**：`main()` 顺序为 open → `identity_gate`（L420，仅 FC03×3+sleep，纯只读）→ D8120/D8121 检查点（读）→ initial_state snapshot（读）→ 首个用例。**任何写入（首例 reset/restart）都在批次门禁之后**。✓
- `identity_gate`（L273–285）本身只读；心跳不前进（L283–284）或身份不符（L278–279）即抛异常 → 无比对发生 → 无后续写入 → TEST_INFRA_ERROR。只读探针 `readonly-probe-v005fix-20261108.json`：内容仅 FC03 型字段（D300..D306 身份+心跳 8267→8284+扫描计数前进），与 build_identity.json/manual_download.json 的身份五字 [5,31,-10264,-21461,5] 及三哈希完全一致，**记录层面确实只读**；生成脚本未留存（见 m7）。
- **restart_with 路径**（L253–270）：`apply_commands(initial_words)`（写，L255）发生在该函数内部 `identity_gate`（L263）**之前**。即"restart_with 路径内 gate 先于写"**按字面不成立**；成立的是：批次级 gate 已在所有写之前通过，且 restart 后的 gate 在任何观测判读/sync 之前。风险评估：写入面仅命令块、写值来自冻结用例、单操作员会话内固件中途被换的概率可忽略、隔离空载台架——定级 **minor**（m2）。
- **major（M1）**：`finally`（L433–441）无条件执行 `write_block(RESET_WORDS)`。当异常恰为**批次级身份门禁失败**时，finally 仍向 D320..335 写入 16 个命令字——直接违反 S6-HIL-V2 L0 失败处理规定"任一项不符 → TEST_INFRA_ERROR，关闭串口，**不写任何寄存器**"。缓解因素：隔离空载台架（L7）、RESET_WORDS 为安全态值、异固件在该地址段大概率无 Modbus 映射或写入无效果；且本轮五次运行门禁均实际通过，未触发该路径。但这是对明文不变量的违反，必须修（见 §2 M1）。

### 1.4 tick 裁定窄度（验收标准 4）— 结构上不可能产生假 PASS

- `tick_hold_reclassification`（L60–90）首行即 `if mismatch['device'] != 'M11': return None`——**只作用于 M11 失配项**。
- 分支推演（关键安全性论证）：
  - 该函数只对**已进入 mismatches 的项**调用（L353–355）；返回值只可能使该项进入 `held` → 状态 UNVERIFIED（L363–364）。**PASS 分支（L365–366）要求 hard/soft/held 全空且 compared 非空，即零失配**——held 非空必然意味失配存在，故 **PASS 结构上不可达**。真实程序偏差最多被降级为 UNVERIFIED，永远不会被升为 PASS。✓
  - 镜像缺键（ticks/threshold 为 None）→ return None → M11 属 stable_fail → **PROGRAM_FAIL**（不静默放过）。threshold==0 → 两个分支均不可达 → None → PROGRAM_FAIL，无崩溃。✓
  - 不对称性：`ticks==threshold-1` 睡眠/唤醒两侧都降级；`ticks<threshold-1` **仅睡眠侧**（expected==1）降级为"预期/仿真分歧"，唤醒侧（expected==0）远低于阈值 → None → **PROGRAM_FAIL**。代码方向保守（能降不能升）。
- **证据核对**：fix2 共 9 项 tick_hold——7 例 one-tick（STD-033/034/041/046/051/053/060，均 D314=99/100 睡眠侧）+ 2 项 STD-031 分歧（40/100、44/100），与 SUMMARY §2 拆解表**逐项一致**；fix 轮 9 项硬失配（含 STD-037/047）在 fix2 中消失、STD-033/034/053 反向新增为 one-tick——±1 tick 双向漂移与 SUMMARY §5 方差说法吻合。
- 文案不精确（minor）：
  - m3：reason "engagement observed in subsequent steps" 是**硬编码断言**，函数并未检查后续步骤。本轮 7 例用例级状态（后续步确有 M11=1）未逐项追溯，文案普适性未证实（裁定值 UNVERIFIED 本身不受影响）。
  - m4：SUMMARY §3.4 "D314/D315 远低于阈值 → UNVERIFIED 并标注预期/仿真分歧" **漏写了唤醒侧不对称**：唤醒侧远低于阈值按代码是 PROGRAM_FAIL。代码比文档更严（安全方向），但候选文档描述不精确，应补正。

### 1.5 异常路径（验收标准 5）— 通过，两处保留意见

- `main()`（L396–456）：try 内任何异常（通信、restart 失败、用例中途抛错）被 `except Exception` 捕获置 TEST_INFRA_ERROR；`finally` 无条件执行 cleanup（write_block RESET + 150ms + snapshot 回读 + bench.close + cpu.close）。`finally` 对 BaseException（如 KeyboardInterrupt）同样执行。cleanup 内部再包 try/except，写失败时记 `restore_unconfirmed` 并照常 close。progress.json 逐用例落盘，中断时保留部分证据。✓
- `out.mkdir(parents=True, exist_ok=False)`（L410）在 try **之前**：目录已存在则 FileExistsError 直接中止，此时串口尚未打开，无资源；**不可能覆盖既有证据目录**。实测 evidence/s6-v3/ 下全部运行目录名互异，无覆盖。✓（SUMMARY §7 陈述成立）
- 保留意见：cleanup 成功字符串（L438）**未校验** cleanup_state 即置位（本轮事后核验 M0=0/Y0=0/D311=0 成立，m5）；CPU 路径异常若发生在 stop 成功之后、start 之前/中途，PLC 停于 STOP，Modbus 面失效 → finally 写入失败 → restore_unconfirmed，**无 RUN 恢复尝试**（L7 字面"异常路径 try/finally 恢复 RUN"未实现），也无"PLC 处于 STOP"的显式提示——方向偏安全但需人工恢复（m6）。

### 1.6 资源清理实证（验收标准 6）— 通过

- **报告证据**：fix2 `cleanup='stopped, output disabled, zero readback'`、`serial_closed=True`、cleanup_state M0=0/Y0=0/D311=0/D312=0/D319=0；smoke/smoke2/smoke3/fix 四份报告同样 serial_closed=true 且 cleanup_state 为零输出态。5/5 一致。
- **系统查询**（只读）：`tasklist` 现有 33+ python 进程，逐一归属判定：PID 10720 pythonw = `hermes_cli gateway`（监听 0.0.0.0:8644，**非本轮**）；PID 35188 = QElectroTech MCP 服务器；PID 31580 = uvicorn（127.0.0.1:8088，betmaster dev，PORT-REGISTRY 有记载）；其余为 ZCode/插件基础设施。**没有归属本轮 HIL 运行器的残留进程**（运行器是单次执行脚本，main 返回即退出）。
- **端口**：run_hil_v3.py 导入列表无 socket/listen/bind（grep 证实），本轮**无新增监听端口需求** ✓。8644（hermes 网关）不在 PORT-REGISTRY 现行登记中（注册表记 hermes=3188），属既有常驻服务登记漂移，与本轮无关，建议另行刷新登记（超出本复核范围）。
- **限制声明**：Windows 内置工具（tasklist/netstat）不暴露串口句柄归属，无法以系统查询 100% 证明 COM11/COM5 无残留句柄；本结论基于 5/5 报告 serial_closed=true + 单次运行设计 + 未发现任何疑似持有者的进程归属分析。

### 1.7 语法与健壮性（验收标准 7）— 通过

- 内存 `compile()` + `ast.parse()` 均通过（未写任何文件）。
- 专项推演结论：dict 合并顺序无关（槽位赋值）；`observed.get` 缺键路径——D8120/D8121 期待项经 comparable() 返回 False 走 skipped（正是 fix2 中 2 项 system-word skip），不会以 actual=None 误判；ZERO_ONLY 分支依赖的 M0/M11 恒存在；threshold==0 不崩溃且判 FAIL（安全方向）；RESET_WORDS 常量未被原地修改（reset 用 `list(...)` 拷贝）；PASS 判定要求零 skipped（用例级保守）；command-echo（D320..335 属 ALWAYS）失配 → 硬 FAIL，正确。
- 已知健壮性/文案问题集中列于 §2。

### 1.8 候选结论数字核对（抽样）

| SUMMARY 声称 | 实测 | 一致 |
|---|---|---|
| fix2 = 31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL（62 用例） | 62 用例，31/31/0 | ✓ |
| 2132 项主机可比对全部吻合 | compared=2132，mismatch=0 | ✓（其中 2 项为常量比对，见 m2） |
| 448 writes | 448 | ✓ |
| UNVERIFIED 拆解 162+7+2+2 | skipped=164（162 R07 + 2 系统字）+ tick_hold=9（7 one-tick + 2 STD-031） | ✓ |
| 身份五字与三哈希 | probe/build_identity/manual_download 三方一致 | ✓ |
| Y0 纳入判读 266 处预期 | 冻结套件 Y0 预期 266 处，fix2 实际比对 266 项 | ✓ 精确 |
| D8120=-8063/D8121=1 检查点 | report system_checkpoint 相同 | ✓ |
| 修复前 smoke 实证自启动（M0=1） | run-v5-fix-smoke：STD-059/062 step5 M0 exp=0 act=1；smoke2/smoke3 零失配 | ✓ |
| 无监听端口新增、串口独占、不覆盖证据目录 | 见 §1.5/§1.6 | ✓ |

---

## 2. 发现的问题

### Blocker
无。

### Major
- **M1｜finally 在身份门禁失败路径上仍写入**：`main()` 的 finally 无条件 `write_block(RESET_WORDS)`（L433–441）。当异常为批次级 identity_gate 失败（或 restart 后 5 次重试均身份不符）时，会向（可能非 V005 的）固件 D320..335 写 16 个命令字，违反 S6-HIL-V2 L0"任一项不符 → 关闭串口，不写任何寄存器"的明文规定。建议：增加 `identity_verified` 标志，门禁未通过则 finally 跳过写、仅 close。缓解因素（不改变定级）：隔离空载台架、写值为安全态、本轮五次运行未触发该路径、写入对异固件大概率无效。
- **M2｜工具修改前基线不可追溯**：`run_hil_v3.py` 无 git 历史（git log/status 均为空），"四处修改"的修改前代码无法从版本库核对，修复前行为的唯一实证是 run-v5-fix-smoke 的 M0 失配记录。S6-HIL-V2 §3.5 要求证据可复算、L6 要求 runner_sha256 入头部——当前批次头未记录 runner 哈希，工具版本与报告之间缺一条可复核的绑定链。建议：工具入库 + 批次头补 runner_sha256（本轮报告已生成、无法补，列为下轮修订项）。注：四处修改的**必要性**仍由 smoke→smoke2 对照充分实证，本条不质疑其效果。

### Minor
- **m1**：`bench.write`（FC06）ALLOWED 含 D300..D319（身份块+状态块），且方法无调用点（死代码）。残留"可写身份区"与"双帧窗口"两条风险通道。建议收窄至 {D320..D335} 或删除。
- **m2**：restart_with 内 initial_words 写（L255）先于该路径 identity_gate（L263）；批次级门禁满足、风险有界，但与"任何写前均有该路径门禁"的字面预期不符，建议在函数 docstring 写明门禁时序。
- **m3**：tick_hold reason "engagement observed in subsequent steps" 硬编码、未实际核查后续步骤；本轮 7 例未逐项追溯佐证。
- **m4**：SUMMARY §3.4 "远低于阈值 → UNVERIFIED" 漏写唤醒侧不对称（唤醒侧远低于阈值 = PROGRAM_FAIL）；文档应补正（代码更严，方向安全）。
- **m5**：cleanup 成功字符串无条件置位，未校验 cleanup_state；本轮事后核验成立，但代码层面无保证。
- **m6**：CPU 路径异常（stop 成功后 start 失败）留 PLC 于 STOP，无 RUN 恢复尝试与显式提示（L7 字面偏差；方向偏安全，需人工恢复）。
- **m7**：只读探针的生成脚本未留存，"确实只读"仅能由记录内容（FC03 型字段、心跳/扫描计数前进）+ identity_gate 只读实现佐证，无法从脚本本体复核。
- **m8**：write_block 异常文案写 D300（BLOCK_BASE），实际写址 320。
- **m9**：apply_commands 先合并后校验，非法地址时 tracked 向量已被部分污染（未发送）；因异常直达顶层中止批次而无实害，validate-then-write 更稳。
- **m10**：timeout 固定 0.5s，未按 L1.5"帧时间+余量"计算（retries=0 符合规范）。
- **m11**：STD-029 的 range 断言（D311 {min,max}）走 skipped 通道但复用"运行中 PI 量"理由文案；本例语义恰好相近，文案通道未区分 dict 预期与相位预期。
- **m12**：snapshot 硬编码 `M8196=1`/`M8125=1`（L199–200），STD-001 step0 的 2 个 compared 项是常量回显而非实测（2132 项"全部吻合"含此 2 项）；有心跳前进 + D8120 检查点吻合的间接佐证，属系统寄存器弱观测，建议报告标注。
- **m13**：批次头缺 pymodbus 版本（本机默认解释器实测 3.15.0）等运行环境字段（L6 完备性）。

---

## 3. 独立结论

**同意候选判定 §2（fix2 主批次 31 PASS / 31 UNVERIFIED / 0 PROGRAM_FAIL）与 §3 的核心主张"四处工具修改安全且必要"，附带 §2-M1/M2 两项下轮修订要求。**

理由：

1. **必要性成立**：修复前 FC06 逐字注入的自启动危害有直接证据（run-v5-fix-smoke：STD-059/062 M0 exp=0 act=1），修复后 smoke2/smoke3 零失配、fix2 62 用例零复现；模块 docstring 本就要求单帧 FC16，属实现漂移纠正而非规范变更。冻结预期一字未改（我核对的三份身份/哈希绑定文件相互一致，s1-freeze 未被本轮触碰）。
2. **安全性成立（写入面）**：全部实际写入路径收敛为"命令块 D320..D335 单帧 FC16"（冻结用例写键 16 个全在块内 + apply_commands 硬校验 + write_block 固定址），COM5 仅 M8035/36/37。`bench.write` 的宽 ALLOWED 是死代码残留（m1），不构成本轮实际暴露。
3. **安全性成立（判定面）**：tick 裁定结构上只能把已失配的 M11 项降级为 UNVERIFIED，PASS 分支要求零失配、镜像缺键反而升级为 PROGRAM_FAIL；不可能是"真实偏差变 PASS"。fix2 的 9 项 tick_hold 与 SUMMARY §2 拆解逐项吻合。
4. **门禁与清理**：批次级身份门禁先于一切写入、心跳不前进绝不写入且本轮从未触发降级路径；5/5 报告 cleanup 达成零输出态且 serial_closed=true，系统查询未见本轮残留进程/端口，证据目录零覆盖。
5. **不阻塞性**：M1/M2 均为"门禁失败才触发/链条完备性"问题，本轮五次运行门禁全部实际通过、写入全部发生在有效身份下，不追溯影响本轮判定有效性；但必须在下一轮工具修订中落实（M1 加 identity_verified 门控，M2 工具入库 + runner_sha256 进批次头）。

同时要求修正两处文档不精确（不改变判定）：m4（§3.4 唤醒侧不对称）与 m3（reason 文案的普适性表述）；§4 STD-031 的 UNVERIFIED 处置与待办链路（仿真 oracle 修复 → S1 修订复核 → 不继承旧 PASS）保持不变。

## 4. 未查项

1. 未逐项追溯 7 个 one-tick 用例（STD-033/034/041/046/051/053/060）的后续步骤，以核实 reason 中"engagement observed in subsequent steps"的逐例真实性（仅核对了 tick_hold 明细的镜像值/阈值/用例归属）。
2. 未做 L01S 固件内部对 FC16 的原子性实证（从 Modbus 事务语义 + PLC 通信服务模型 + 448 次零错运行推断；规范要求的固件级验证不可由主机侧完成）。
3. 未复核 COM5 编程口 force 帧与 L01S GX 协议的逐字节符合性（仅做结构合理性审查；其正确性由本轮 62 用例正常 stop/run 序列间接佐证）。
4. 未验证 COM11/COM5 当前句柄归属（Windows 内置工具限制，见 §1.6 限制声明）。
5. 未核对 run-v5-full-e（修复前镜像对照轮）与本轮工具修改的交互（该轮在工具修改前执行，属另一复核人范围）。
6. 未复核 frozen test_cases.json 预期值本身的有效性（S1 范畴，属复核 ①/② 职责）；本复核只核对了写键/预期键的地址面与判定通路。
