# V006 STD-006 HIL 首轮摘要（run-v6-std006-r4）

- 时间：2026-11-18T12:02:08.784781+00:00
- 串口：COM11（COM5 编程口做逐用例 STOP/RUN）
- 身份门禁实读：{"D300": 6, "D301": 31, "D302": -7313, "D303": -11960, "D304": 6}（与 build_identity.json 一致）
- 结果：**PASS**，7/7 用例 PASS，25 次写（全部限命令块 D320–D336）

| 用例 | 判定 |
|---|---|
| STD6-001 | PASS |
| STD6-002 | PASS |
| STD6-003 | PASS |
| STD6-004 | PASS |
| STD6-005 | PASS |
| STD6-006 | PASS |
| STD6-007 | PASS |

前序轮次（r1 内部器件口径、r2/r3 冻结迭代）记录保留于 `evidence/s6-v3/`。
证据 JSON：项目 `evidence/s6-v3/run-v6-std006-r4/report.json`。
