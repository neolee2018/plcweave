# S1 修订记录 V003（suite STD-003）

日期：2026-10-24。任务：PW-20261024-S6-AI0-PARALLEL。

## 原因

STD-017/018 原先直接写硬件 AI0 地址 D8030。实测（adc-write-probe-20261023）写 D8030 后
50 ms 内被 ADC 刷新覆盖，主机无法注入；这是测量方式与技能"统一内部输入变量层"不一致，
不是程序缺陷。

## 修订

- 程序新增并联测试软元件：D1071=1（且 D190=0）时用 D1070 代替 D8030，D1071=0 保持真实
  AI0 路径不变；首次扫描 D1070=D1071=0。
- STD-017/018 的激励由 `D8030=x` 改为 `D1071=1, D1070=x`，并把 D1056 置 4000 以证明
  模式 0 下测试输入被忽略。
- 预期值、容差、其他 53 条用例一律不变。
- 程序版本 2→3，测试套件版本 2→3，指纹随规范化指令重算为 [7757, -31026]，
  用例与全局不变量中的 D196/D202 预期同步改为 3。
- 采样器 `scaling_settings` 与 `diagnostics` 两处判定改为按套件/并联输入通用处理
  （见 docs/RUNTIME-CHANGES.md），不放松任何预期。
- 本地 S3：55/55 SIM_PASS（source 285cc68c…，套件 16d52aae…）。

## 版本绑定

| 文件 | V002 哈希 | V003 哈希 |
|---|---|---|
| requirements.md | aafc680c5d7cfe8dc2d47826e5cfc2316c6fc19fbbd581d0a934e46d34a4f282 | a45d670b6518293bb3bdc1790a40b67231c333629ccf8fd33e6e97cbd12aa0a3 |
| test_cases.json | b8702dc680b52990c180bbdfa320a477cbc5562ef71c9bf625012d9679475106 | 16d52aaed24aa08bdbd8624a417cd7b9584325415eae606d15f8609ddfe6fa51 |

程序源 V003：`285cc68c59995caef0811132b2cc6f7e4e0e18e9b28521c9275edbab8fa83e29`
（规范化 4d1ece86…，182 条指令）。烧录件：`实验室测试/V003/MAIN.csv`、`COMMENT.csv`。

旧冻结保留在 `s1-freeze-V002.json`，不覆盖。
