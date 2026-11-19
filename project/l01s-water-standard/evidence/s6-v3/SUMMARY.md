# S6 软元件注入批次结果（V002 实机）

方法：写程序预留的注入寄存器（D190/D1056/D191/D192/D193/D102/D261/D194）→ 读输出软元件 → 与冻结 test_cases.json 逐项比对。

**53 项用例：PASS 30、UNVERIFIED 23、PROGRAM_FAIL 0**；累计写入 892 次。

判定口径：
- PASS = 全部断言被实机比对且相符，无跳过、无边界歧义。
- UNVERIFIED = 已比对项相符，但存在主机轮询无法证明的瞬时值或定时器边沿歧义。
- PROGRAM_FAIL = 稳定量（D100/D102/D260/D262/D190–D197/D202/D8120/D8121/M0 等）与冻结预期不符。

| 用例 | 标题 | 判定 | 已比对 | 跳过 | 边界歧义 |
|---|---|---|---|---|---|
| STD-001 | First scan rejects preloaded request | PASS | 33 | 0 | 0 |
| STD-002 | Saved SV first scan -32768 | PASS | 14 | 0 | 0 |
| STD-003 | Saved SV first scan -1 | PASS | 14 | 0 | 0 |
| STD-004 | Saved SV first scan 9 | PASS | 14 | 0 | 0 |
| STD-005 | Saved SV first scan 10 | PASS | 14 | 0 | 0 |
| STD-006 | Saved SV first scan 11 | PASS | 14 | 0 | 0 |
| STD-007 | Saved SV first scan 159 | PASS | 14 | 0 | 0 |
| STD-008 | Saved SV first scan 160 | PASS | 14 | 0 | 0 |
| STD-009 | Saved SV first scan 161 | PASS | 14 | 0 | 0 |
| STD-010 | Saved SV first scan 32767 | PASS | 14 | 0 | 0 |
| STD-012 | Non-one command words -32768 are una | PASS | 30 | 0 | 0 |
| STD-013 | Non-one command words -1 are unasser | PASS | 30 | 0 | 0 |
| STD-014 | Non-one command words 2 are unassert | PASS | 30 | 0 | 0 |
| STD-015 | Non-one command words 32767 are unas | PASS | 30 | 0 | 0 |
| STD-016 | Signed raw clamp and every rounding  | PASS | 248 | 0 | 0 |
| STD-019 | Invalid mode -32768 inhibits held-st | PASS | 47 | 0 | 0 |
| STD-020 | Invalid mode -1 inhibits held-start  | PASS | 47 | 0 | 0 |
| STD-021 | Invalid mode 2 inhibits held-start r | PASS | 47 | 0 | 0 |
| STD-022 | Invalid mode 32767 inhibits held-sta | PASS | 47 | 0 | 0 |
| STD-024 | Online active SV clamp recomputes bo | PASS | 152 | 0 | 0 |
| STD-025 | Changing saved word online does not  | PASS | 19 | 0 | 0 |
| STD-037 | SV lower and upper threshold boundar | PASS | 56 | 0 | 0 |
| STD-042 | Stop dominates a newly arriving full | PASS | 24 | 0 | 0 |
| STD-044 | Jitter 0/full-scale every100ms canno | PASS | 192 | 0 | 0 |
| STD-048 | Echo accepts all signed words on the | PASS | 20 | 0 | 0 |
| STD-049 | Diagnostic signed counter wrap and h | PASS | 16 | 0 | 0 |
| STD-051 | Online SV updates wake threshold whi | PASS | 37 | 0 | 0 |
| STD-053 | Invalid mode same-scan clears sleep  | PASS | 43 | 0 | 0 |
| STD-054 | Invalid mode same-scan clears wake_p | PASS | 50 | 0 | 0 |
| STD-055 | Diagnostic wrap during active PI can | PASS | 15 | 0 | 0 |
| STD-011 | Start latches, requests persist, sto | UNVERIFIED | 44 | 3 | 0 |
| STD-023 | Invalid mode blocks even simultaneou | UNVERIFIED | 34 | 1 | 0 |
| STD-026 | Normal PI first two updates and hold | UNVERIFIED | 13 | 10 | 0 |
| STD-027 | Integer division PI fractional integ | UNVERIFIED | 8 | 22 | 0 |
| STD-028 | PI uses latest online SV and persist | UNVERIFIED | 12 | 6 | 0 |
| STD-029 | Signal loss zero reaches full freque | UNVERIFIED | 25 | 3 | 0 |
| STD-030 | PI remains active while output gate  | UNVERIFIED | 16 | 24 | 0 |
| STD-031 | Pre-sleep equality, below adjacent v | UNVERIFIED | 31 | 8 | 0 |
| STD-032 | Pre-sleep does not complete at 4.8s; | UNVERIFIED | 26 | 3 | 0 |
| STD-033 | Sleep persists above wake threshold  | UNVERIFIED | 45 | 1 | 1 |
| STD-034 | Wake cancellation at adjacent above- | UNVERIFIED | 62 | 2 | 0 |
| STD-035 | Changing SV changes pre-sleep thresh | UNVERIFIED | 17 | 7 | 0 |
| STD-036 | Large negative error/full-scale cann | UNVERIFIED | 19 | 4 | 0 |
| STD-038 | Stop same-scan overrides normal | UNVERIFIED | 35 | 4 | 0 |
| STD-039 | Stop same-scan overrides pre_sleep | UNVERIFIED | 38 | 6 | 0 |
| STD-040 | Stop same-scan overrides sleep | UNVERIFIED | 42 | 4 | 0 |
| STD-041 | Stop same-scan overrides wake_pendin | UNVERIFIED | 49 | 4 | 0 |
| STD-043 | Enable gate toggles within normal/pr | UNVERIFIED | 48 | 8 | 0 |
| STD-045 | Single-scan input glitches reset sle | UNVERIFIED | 24 | 3 | 3 |
| STD-046 | Single-scan wake-region exit resets  | UNVERIFIED | 33 | 6 | 2 |
| STD-047 | Stop during timer then restart does  | UNVERIFIED | 77 | 4 | 0 |
| STD-050 | Diagnostics remain live during norma | UNVERIFIED | 9 | 2 | 0 |
| STD-052 | Invalid mode same-scan clears pre_sl | UNVERIFIED | 39 | 2 | 0 |

## 运行目录

- run-v3-b
- run-v3-c
- run-v3-e
- run-v3-init
- run-v3-init2
- run-v3-long
- run-v3-long2
- run-v3-wrap
- run-v3-local
- run-v3-extra

## 说明

- run-v3-init：STD-001–010，真实 COM5 STOP/RUN 让 D261 首次扫描生效。
- run-v3-init2：STD-001 复跑（快照补齐 D200–D202/M8196/M8125/D8120–D8121）。
- run-v3-long / long2：长时序用例；long2 对定时器边沿歧义改判 UNVERIFIED。
- run-v3-wrap：STD-049/055 计数器回绕，340 s 等待期间每 10 s 抽样检查不变量。
- STD-017/018 未执行：实测写 D8030 会在 50 ms 内被 ADC 刷新覆盖（见 adc-probe 记录），需要 V003 程序钩子或真实模拟量源。