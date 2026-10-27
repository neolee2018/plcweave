# 独立复核 1：需求、冻结、修订及双版测试

- reviewer：`/root/review_requirements_tests`，独立上下文，主Agent不计入。
- task_id：`two-phase-20261024-review-1`；owner：本复核Agent；时限：本次复核；日期：2026-10-24。
- 资源归属：仅本任务 `logs/review-two-phase-1/` 中的隔离合成工程及临时文件；未接PLC、未开串口、未操作GUI。只修改本报告，不修改实现或工具测试。
- 初次结论：**BLOCKED，等待问题修复后复查**。本报告不是客户S1或硬件验证PASS。
- 2026-10-26最终复查结论：**PASS（需求/测试/修订及双版本地工具范围）**。初查和复查过程保留下文；此结论仅适用于末尾列明的实际输入哈希，不是厂家编译或实机PASS。

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

## 2026-10-26独立复查

### 范围与版本

沿用同一reviewer、task_id及资源边界；本次任务为复核修复，不继承主Agent的通过结论。基准HEAD为`be13030ee2143e2c1956254f1c660a6c0fb4a9fe`，加当前工作树；以下文件的原始字节SHA256构成本次实际适用版本。除明确注明的有关部分外，读取了完整实现及测试；README读取安装/入口相关部分。未变更的既有材料可引用初查，但新增修订门禁、冻结回滚和路径改动已实际重读。

| 已实际复查文件 | SHA256 |
| --- | --- |
| docs/PART-ONE.md | 310f797286af6d69a3c801b0e1bea58343c7777c1f12afe81bec80c2becd3585 |
| docs/PART-TWO.md | 0f896bea36cbfda20e0bae6dbc802d6b8d9e0af1af455ff164bb9044393c3d2a |
| src/plcweave/workflow.py | 43cc72d255193c3047ff6369ac55b434af334ea658aac678b1be91319ac4a020 |
| src/plcweave/variants.py | 7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f |
| src/plcweave/testing.py | 8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60 |
| src/plcweave/markdown_suite.py | 48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e |
| src/plcweave/validation.py（套件契约有关部分） | 5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099 |
| src/plcweave/fx.py | d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98 |
| src/plcweave/projects.py | 0ab14695cd9eb2c6ed4937bab3158bbd57a6d98e56158d03612f7be5fd634b0c |
| tests/test_workflow.py | cbd5eeab9d67714b18fc3eb55191412a6c0a52451e85d8ada3e3f9f729f8d090 |
| skills/plc-program-development/SKILL.md | f8c94cc427782b5a35a616c08ec99f25f5fc5dc0bee7039b418b8c8ca2ebc965 |
| skills/plc-program-development/references/two-phase-workflow.md | 7d0300cd87891b5c5a17343aae1f25962c1a494b6aac425b60d7383c6ff390bf |
| README.md（入口/安装相关部分） | c3e20f0c3498185ecfa8f9b4bea7293df57dba699006c70ed6e7c5a8dad2ac76 |

### 执行证据

- 先对当时31项工作流测试独立运行，31 passed in 11.90s。随后修复继续发生，此结果不作为最终版本通过证据。
- 最终执行：`PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_workflow.py -p no:cacheprovider --basetemp=logs/review-two-phase-1/pytest-20261026-final -q`，**36 passed in 13.03s**，无失败/跳过。没有改写用例预期追求通过。
- 最终自行反例入口：`logs/review-two-phase-1/recheck-final-20261026.py`；结果保存在`logs/review-two-phase-1/recheck-final-20261026/result.json`。该脚本重建独立合成工程，未复用旧build或旧下载记录。
- 中间版本发现新缺口的反例及原始结果保留在`logs/review-two-phase-1/recheck-20261026.py`和其同名目录`result.json`，不覆盖为通过证据。

### 原问题复查

| 问题 | 实际检查 | 结论 |
| --- | --- | --- |
| R1-1 每例初态不同 | 原部分写入反例现在两版均PROGRAM_FAIL，构建LOCAL_FAIL，confirm-download以Both variants require SIM_PASS阻断；另建仅一稳态步骤，保留停止复位输入且明确预期M0=0，两版本地LOCAL_PASS，合成HIL PASS，串口替身已关闭。读取实现确认两版均先施加同一设计reset、运行等待并比较同一reset预期，再覆盖Initial和Steps。 | 关闭 |
| R1-2 旧需求原文缺失 | 用户只改requirements后revise，原字节出现在baseline/s1/requirements.md、build/B001/inputs/requirements.md、该build的baseline副本和revision/previous/requirements.md；需求差异包含旧内容删除及新内容增加。新修订没有s1-freeze和source，不继承旧PASS。 | 关闭 |
| R1-3 锁存/停止覆盖缺口 | SUITE增加释放启动后保持与启动停止同时有效；自行分别删除OR M0、删除ANI M101，两版均PROGRAM_FAIL/LOCAL_FAIL。对应定向突变测试也实际通过。 | 关闭 |
| 初查ZIP fixture失败 | 提取目录改为tmp_path/project/extracted，保留客户目录门禁；最终定向测试中的ZIP内容、哈希和提取后validate_build检查实际通过。 | 关闭 |

### 复查中新发现并已修复的问题

1. 中间版本的revise只核验旧requirements快照。自行分别修改`baseline/s1/test_cases.md`和`design.md`，再修改requirements并revise，工具仍成功且`previous/`复制了篡改内容。已向主Agent报告。最终实现从s1-freeze与design-freeze读取三份旧摘要，复制前全部核验，复制到previous后再次核验；最终同一反例均返回`Old frozen snapshot missing or changed`，未生成新版修订目录。36项中的三种历史MD损坏回归也实际通过。**关闭**。
2. 中间版本对末尾无换行的旧requirements生成diff时，把删除尾行与新增行粘接。已向主Agent报告。最终实现规范化diff展示行分隔，MD原文字节仍独立原样留存；自行反例的删除与新增现为分开的行，专门回归通过。**关闭**。该展示差异用于AI理解变更，完整原文和SHA256仍是版本证据。
3. 后续通知的`require_reviews`路径统一为POSIX分隔和冻结部分写失败回滚已读取；最终定向测试覆盖解包验证与design-freeze部分写入故障，均通过。该回滚只移除本次创建文件，保留需求及复核输入。

### 最终判断与限制

本角色的需求/冻结/修订/双版测试覆盖问题已关闭，**PASS（本地工具范围）**。四类交付及双程序的确定性生成、独立冻结用例和程序修错/需求修订分支，在本次合成范围内符合目标流程；需求语义澄清、资源设计及独立测试设计由Agent执行，CLI不自称自动理解任意需求。当前技能/参考/目标流程对该分工、人工下载、新build重测、L01S稳态边界、未实现台达适配与正式版实机范围说明一致。

本结论不证明任意客户需求的覆盖充分性、不证明独立记录实际来自四个上下文，也不证明厂家导入/编译、PLC实机或物理I/O。当前设计reset对本次输入/输出契约有效；首扫、重启、保持及不可观测内部历史不由合成稳态用例升级为硬件通过。

任务结束：定向测试和自建反例均已退出；合成连接替身正常关闭。保留任务脚本/结果与隔离工程用于复测；无本任务真实串口、GUI、后台服务或共享资源残留。报告只由本复核者更新。

## 最终相邻S1异常路径补充复核（2026-10-26）

主Agent随后通知仅修复`freeze_markdown()`在新建`s1-freeze.md`部分写入后失败时的残留，并把工作流故障测试扩展为两种冻结文件。本Agent重新读取该函数和测试，未继承其他Agent结果。下列两个SHA256更新上述最终适用输入；`workflow.py`仍为`43cc72d255193c3047ff6369ac55b434af334ea658aac678b1be91319ac4a020`，其余已列输入与本角色结论沿用。

| 文件 | 最终SHA256 |
| --- | --- |
| src/plcweave/markdown_suite.py | ed5f50aee5fe10452d208dd7620aa28b8c11bda2c5a6da6114eff5baaa16d4de |
| tests/test_workflow.py | 7fdc38414f4f5385b4d1690ddaaba91876cc0360dcab8adbdd743ec920f8b763 |

实际执行与检查：

- `tests/test_workflow.py::test_partial_freeze_failure_rolls_back_owned_files`（design-freeze及s1-freeze两种）加`tests/test_markdown_projects.py`，`-p no:cacheprovider --basetemp=logs/review-two-phase-1/pytest-s1-exception-final -q`：**13 passed in 0.30s**。
- `tests/test_markdown_review.py`，`-p no:cacheprovider --basetemp=logs/review-two-phase-1/pytest-s1-markdown-review-final -q`：**8 passed in 0.07s**。两次共21项，无失败/跳过；未无故重复其他完整场景。
- 自建反例`logs/review-two-phase-1/s1-exception-probe-final.py`另检查四条路径：写入前10字符后OSError；同位置KeyboardInterrupt；已有冻结再次调用；exists检查后另一归属者抢先创建文件导致exclusive open失败。结果保存在同名目录`result.json`。前两者移除本次部分文件且作者源原字节不变，已有冻结和竞争者创建文件均保留原字节。

语义判断：`created`只在exclusive open成功后置真，BaseException路径只回收该调用创建的目标。已有冻结不被覆盖，编程前冻结、MD作者源和hash格式不变；工作流外层仍清理本次baseline及design-freeze，不删除要求或复核记录。**补充复核PASS，本角色原最终PASS继续适用至上述新输入哈希。**未连接设备。所有补充执行已退出，未留下连接或后台任务，反例文件作为证据保留。
