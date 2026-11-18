# S1 修订记录 V006（STD-006 / N1C 诊断 + 唤醒压力 4.0 bar + 最大压力保护）

日期：2026-11-18。任务：l01s-water-standard V005 → V006（**合并版**）。
本修订取代 2026-11-18 早些时候的 V006 草稿（原草稿只有 N1C 卡满量程诊断、且未提升到根目录、
未出 runner/文档；其 `delivery\V006-n1c-bench-kit\` 已作废，**请勿烧录**）。

合并内容（用户 2026-11-18 确认）：
1. N1C PV 卡满量程诊断（原 V006 草稿，D307 bit6 / M14 / T2）；
2. 唤醒压力首扫固定 **4.0 bar**，取代 V005 的"保存设定×85%"；
3. 新增**最大压力保护**：上限可设（默认 **8.0 bar**），超限封锁输出并报警，压力回落自动恢复；
4. 命令块扩为 **17 字**（新增 D336），状态块 D316 改作最大压力生效值镜像、D307 增加 bit7。

基线：V005 源 `13f396bc…`，保留在 `delivery\V005-fix-bench-kit\source.fxil`（本修订结束时复核一致）。
本修订把**根目录** `source.fxil` / `build_identity.json` 提升为 V006（台架适配器与 runner 以根目录为活版本）。

## 1. 逐项改动清单（相对 V005）

| # | 位置 | 改动 |
|---|------|------|
| 1 | 文件头 | `version: V005` → `V006` |
| 2 | 身份块 | `MOV K5 D300` → `MOV K6 D300`；`MOV K5 D304` → `MOV K6 D304`（套件字随 STD-006 递增；D301 版次保持 31） |
| 3 | 身份块 | D302/D303 指纹由 `check_build_identity.py --write` 重算：`MUL K2 K18413 D302`、`MOV K30376 D303` |
| 4 | §01 首扫 | 删除 `MUL D325 K85 / DIV K100 / MOV D168 D326`；改为 `MOV K40 D326`、`MOV K80 D336`、`RST M40` |
| 5 | §03 钳位 | 新增 `MOV D336 D175` + 钳位 [10,160] |
| 6 | 新 §07b | 超压锁存：`SUB D175 K5 D176`；`LD M0 / AND> D100 D175 / SET M40`；`LD M8000 / AND<= D100 D176 / RST M40` |
| 7 | 新 §10b | 封锁：`LD M40 / MOV K0 D154 / MOV K0 D120`（位于 PI 之后、物理输出之前） |
| 8 | §12 | 新增 `LD M40 / ADD D307 K128 D307`（bit7）；新增 `MOV D175 D316` |
| 9 | §04（N1C） | 保留原草稿：`LD M8000 / AND>= D110 K3997 / AND<= D110 K4003 / OUT T2 K18000` + `LD T2 / OUT M14` |
| 10 | §12（N1C） | 保留原草稿：`LD M14 / ADD D307 K64 D307`（bit6） |
| 11 | #comments | 新增 M40、D336、D175、D176；D316/D326/D307/D304 注释同步；D167/D168 标为"V006 起未使用" |

指令数（项目解析器口径）：V005 280 条 → V006 **310 条**。

## 2. 器件占用核对

- **M40**：源码与 `register_map.csv` 均未使用 → 超压锁存。
- **D175 / D176 / D336**：源码 D 区最高用到 D168，三处均空闲 → 上限生效值 / 回差阈值 / 上限设定。
- **D316**：原"保留恒 0"，V006 改为最大压力生效值镜像（状态块内，不占用新地址）。
- **D307 bit6 / bit7**：bit6 为 N1C 诊断（原草稿），bit7 为超压；最大组合 255，无符号溢出。
- **T2 / M14**：沿用原草稿（100 ms 时基定时器与诊断位）。

## 3. 标识与指纹

`check_build_identity.py --write` 输出（工具重算，未手写）：

- `source_sha256`：`7eee2d2878b4508fee1169297a9a8f8df0d5b98e091a4e18cb1d1d33fc96aa09`
- `canonical_sha256`：`6fe348d1b84bd053f8703ba7bc571eb667dbf373ffd902c5918a4c5305393c2d`
- `fingerprint_words`（signed）：`[-7313, -11960]`（无符号 58223 / 53576）
- `program_version=6`、`edition=31`、`suite_version_word=6`

## 4. 静态检查

方式：`plcweave.fx.export` 导出 → `gxwlib.load_csv(..., device_profile="fx")` →
`compile_program(profile="fx3u")` → `analyze`。

- 编译 **0 error**，`analysis.complete=True`。
- **7 条 warning（GXW_MULTIPLE_WRITES）**：M0、M1、M3、M11、M12、M30（V005 既有）+
  **M40（V006 新增：SET + RST 两处写，属锁存语义，按扫描顺序）**。
- 3 条 info（GXW_NO_KNOWN_LOCAL_WRITE）：M8000 / M8002 / M8012，系统继电器。
- 首版实现曾用 `LD<=` 作比较母线，gxwlib 不支持该形式（GXW_SIM_INCOMPLETE）；
  已改为 `LD M8000 / AND<=` 串联写法，与程序既有钳位梯级一致。

## 5. 逐扫描仿真（本地指令级，非 GX Works / 非实机）

脚本：`verify_v006_behavior.py`；证据：`evidence/simulation/v006-behavior/behavior.json`。
共 22 项检查，全部 PASS：

| 场景 | 结果 |
|---|---|
| 首扫 | D326=40、D336=80、D316=80、D176=75 |
| 运行 4.0 bar | M0=1、D154>0、Y0=1、D307 bit7=0 |
| PV 升到 8.1 bar | M40=1、D154=0、Y0=0、D8050=0、D307 bit7=1 |
| 回落到恰好 8.0 bar | 锁存保持（未到 7.5 bar 不解锁） |
| 回落到 7.4 bar | M40=0、D154 恢复 >0、bit7=0（自动恢复） |
| D336=0 / D336=200 | D175 钳位 10 / 160，D316 跟随 |

## 6. 接口与工具链同步

- `run_hil_v3.py`：`BLOCK_END=336`、读 37 字、写 17 字；`RESET_WORDS`/`NEUTRAL_WORDS` 第 7 字=40、
  第 17 字=80；`ALWAYS` 增 D336。
- `src/plcweave/bench/script_projects.py`：源哈希 pin、身份五元组 (300,6)(301,31)(302,58223)(303,53576)(304,6)、
  watch 表增 D316/D336、中英文注释、`io` 展示标签（X0 启动 / X1 停止 / AD0 压力注入 / Y0 泵输出 / DA1 频率输出）。
- 台架界面：数字输入/输出（及 AD/DA）卡片按适配器映射显示"脚本启用"点位（描边 + 点位下小字 + 图例）。
- 文档：`Doc/HMI-register-map.md`、`hmi/registers.md`、`hmi/params.md`、`register_map.csv` 同步 D336/D316/D307 bit7。

## 7. 兼容性与风险

- **D326 默认值变化**（51 → 40）改变休眠/唤醒时序：V005 的 STD-005 休眠唤醒用例**全部作废**，
  第二阶段按 **STD-006** 重写；旧套件（`test_cases.json` + `s1-freeze.json`）保持原样归档，
  **禁止对 V006 运行**（身份门禁会先拒绝）。
- **命令块扩到 17 字**：若客户 HMI 自带组态写 16 字，会把 D336 留成 0 → 钳位后 1.0 bar 误锁输出。
  交付文档已注明必须写满 17 字（D336=80 或工艺上限）。
- 超压判定用换算后的 D100，触发为**严格大于**；自动恢复阈值为上限 −0.5 bar。
- 报警仅状态位 D307 bit7 + 界面提示，不占用 Y1 等物理点。

## 8. 台架 HIL 验证（STD-006 首轮，run-v6-std006-r4）

用户已于 2026-11-18 烧录 V006（身份门禁实读 D300=6/D301=31/D302=-7313/D303=-11960/D304=6，
与 build_identity 一致；D305 心跳前进）。STD-006 冻结套件经两轮预期修正（第一轮把不可观测的
内部字 M40/D154/D175/D176 改为可观测镜像/位）后，在 COM11 台架实机运行：

**7/7 用例 PASS（run-v6-std006-r4，25 次写，全部限命令块）**：
- STD6-001 首扫身份与默认值（D326=40、D336=80、D316=80）
- STD6-002 超压封锁（8.1 bar 封锁、Y0 断、bit7 置位）+ 回差带保持 + 7.4 bar 自动恢复
- STD6-003 严格大于：恰好 8.0 bar 不触发
- STD6-004 唤醒门槛 4.0 bar（4.5 bar 不唤醒、3.0 bar 唤醒）
- STD6-005 钳位 10/160 与 D316 镜像
- STD6-006 未使能路由时超压仍报警（bit7 置位、Y0 保持断）
- STD6-007 满量程 PV 触发超压；N1C bit6 短时保持清零

前两轮的 PROGRAM_FAIL/UNVERIFIED 记录保留在
`evidence/s6-v3/run-v6-std006-r1..r3/`（首轮为内部器件断言不可观测的口径问题，非程序缺陷）。

## 9. 未验证（UNVERIFIED）

- GX Works 导入/编译、HMI/上位机联调、模拟量电压电流/负载/断电保持：未验证。
- 逐扫描仿真与 STD-006 HIL 只覆盖寄存器/逻辑台架，不构成泵、驱动或现场安全验证。
