# 独立复核 1：需求、冻结、修订及双版测试

- reviewer：`/root/review_requirements_tests`，独立上下文，主Agent不计入。
- task_id：`two-phase-20261024-review-1`；owner：本复核Agent；时限：本次复核；日期：2026-10-24。
- 资源归属：仅本任务 `logs/review-two-phase-1/` 中的隔离合成工程及临时文件；未接PLC、未开串口、未操作GUI。只修改本报告，不修改实现或工具测试。
- 初次结论：**BLOCKED，等待问题修复后复查**。本报告不是客户S1或硬件验证PASS。

## 输入版本 SHA256

| 已实际阅读的文件 | SHA256 |
| --- | --- |
| docs/PART-ONE.md | 5f63d0af6e3278a119e3dae3273d7c07f7dc767fa78935dc5e2cc43f40d1931e |
| docs/PART-TWO.md | 3894fb7dc12da0160db3c3dc5c8da5020ccb35cad48bec406c111009be6e9aa6 |
| src/plcweave/workflow.py | 3636a6be825bc25057177449e7448d17490b32fb865d52c8ac10900f6d91f848 |
| src/plcweave/variants.py | 7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f |
| src/plcweave/testing.py | d497f27a50451cc03c40a419d07496e2c1d8dba937689f8729ac32d41155c692 |
| src/plcweave/markdown_suite.py | 48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e |
| src/plcweave/validation.py（有关套件校验部分） | 5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099 |
| src/plcweave/fx.py | d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98 |
| src/plcweave/projects.py（目录门禁部分） | 61fbeb8e69c19d2a4f16ac8c5e738e51a805b7c134042e3f462833744e722fe4 |
| tests/test_workflow.py | 7a3806c820b67d24e0510f25fb3607c64147df1be34f79826242f194ca0319ba |
| skills/plc-program-development/SKILL.md | b6bfb1a0bb808d079e6adb98c28436d38463028ff5e80853baacdd674478fd54 |

## 实际检查和结果

1. 读取目标流程、实现、套件解析与冻结、双版生成和测试；追踪需求/测试哈希到构建、下载确认、HIL与交付门禁。
2. 执行 `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_workflow.py -p no:cacheprovider --basetemp=logs/review-two-phase-1/pytest -q`：18 passed，1 failed，3.82秒。首次因本Agent未先创建basetemp父目录发生19个setup错误，创建父目录后重跑；不算产品失败。
3. 正式执行的一个失败为解包fixture把客户目录放在`tmp_path/extracted`，与`workspace=tmp_path`的`project/`门禁冲突。主Agent已收到并计划修正fixture路径。未据此认定交付ZIP损坏。
4. 运行自行构造的`logs/review-two-phase-1/probe.py`：两版LOCAL_PASS，而同套件、同控制核心的合成HIL返回PROGRAM_FAIL（M0预期1、实测0）。合成Bench仅用于验证调度语义，绝非硬件证据。
5. 运行`logs/review-two-phase-1/latch-probe.py`：删除共用核心`OR M0`后两版仍LOCAL_PASS，复现合成套件覆盖缺口。
6. 运行`logs/review-two-phase-1/revision-probe.py`：先正常freeze/build，再仅追加requirements并revise，遍历项目所有文件查找原需求SHA256，结果`old_requirements_content_preserved_at: []`。原需求摘要为`3228d40c7e2060e8da92644ed8408d59a1729442f400c2fda1accdcd9089a131`；证实未交付前旧基线原文缺失。

## 问题

### R1-1（阻断）：本地仿真与HIL使用不同的每例初态

位置：`testing.py` 的 `simulate()` 每例创建零态Simulator且只施加`initial_words`；`workflow.py` 的 `run_hil()` 每例先施加设计`HIL reset`再施加`initial_words`。

最小复现：现有fixture设计复位为D1000=0、D1001=1，Initial表为空。仅把首步write由`D1000=1;D1001=0`改为`D1000=1`。该套件能够冻结、构建且两版LOCAL_PASS；HIL首步D1001保持1，停止优先使M0=0，最终误归PROGRAM_FAIL。输入消费检查正常，因此无法据此区别复位调度差异和程序错误。

应使两后端执行同一初态/复位模型（包括初态建立与等待），或明确并校验每例完整初始化契约。需新增针对部分写入、跨例状态和复位的回归；不能更改冻结预期迁就后端。

### R1-2（阻断）：需求修订没有保存可用于版本比较的旧MD原文

位置：`freeze_workflow()`/`freeze_markdown()`仅存需求与测试摘要；`build_workflow()`保存摘要和生成产物而不存冻结MD；`revise_workflow()`读取旧摘要后只复制当前需求和当前测试。

用户按流程修改原requirements.md，若尚未产生独立交付，旧需求原文即不再保存在项目中。旧hash仍在，但无法据此恢复需求内容、准确比较新增/删除/修改或重现旧build。旧根目录build也被当前需求失配阻断。建议在冻结时保留不可变的MD证据快照及关联，修订同时引用旧/新基线；这些是历史证据，不引入第二套可编辑作者源。

### R1-3（测试覆盖缺口）：合成需求“启动保持，停止优先”未被套件完整验证

位置：`tests/test_workflow.py` 的SUITE、`prepared()`、`test_failed_control_regression_is_never_delivered()`。

当前步骤为启动、停止、保持停止；没有释放启动且停止无效时保持运行，也没有启动/停止同时有效。删除锁存`OR M0`后仍LOCAL_PASS。合成测试无需假装客户需求覆盖，但应让所声明的代表性控制需求有故障检出能力。建议增加保持与同时按键步骤，并验证删除锁存、取消停止优先这两个突变均能失败。

## 已确认的边界

- 需求/测试冻结在编程前，修改冻结MD会阻断旧构建；测试版与正式版从同一核心生成，差异是输入映射、身份/通信与输出路由。
- 两版分别执行冻结套件并记录哈希；旧下载确认不能直接解锁新build。双版本地PASS不能自动证明真实端子或厂家编译通过。
- requirements与测试含义的独立设计、覆盖充分性仍由AI和四名独立复核者完成；工具中四条署名记录只检查记录契约，不证明真的有四个上下文。合成测试记录明确标注fixture，未作真实复核证据。
- 未执行厂家编译、实机HIL、电气或带载检查。未建立任何客户PASS结论。

## 清理

所有运行同步退出；合成Bench由runner关闭，未创建真实串口、进程常驻、锁或GUI。保留本任务的probe脚本、合成工程及测试输出作为可复现证据；不清理用户进程或共享服务。最终结论待相关修复后由本Agent复查更新。
