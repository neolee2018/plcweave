# 两阶段工具修改独立复核 3

> 最新复查（2026-10-26，最终增量）：**PASS（本复核范围）**。初查 R3-1 至 R3-5 及最终增量发现的 R3-6 均已关闭；以下内容保留各轮历史。复查针对 HEAD `be13030ee2143e2c1956254f1c660a6c0fb4a9fe` 加工作树中的修复，以最末 SHA256 表为准确输入版本，不声称只覆盖该提交。

- reviewer_id: `/root/review_resources`
- task_id: `two-phase-20261024-review-3`
- 日期：2026-10-24
- 范围：资源映射与写入隔离、未知机型/指令、初始化/异常/超时、连接清理、路径与版本、脚本及证据绑定。
- 结论：**CHANGES_REQUIRED**。本报告仅基于本上下文阅读及独立执行，不继承主 Agent 结论。
- 边界：全程无真实 PLC、串口和 GUI 操作；仅使用合成程序与 DummyBench。没有厂家编译、下载或硬件通过声明。
- 资源：只创建 `logs/review-two-phase-3/` 下的反例与合成客户目录；运行均已退出，没有创建后台进程、连接、锁或 GUI。

## 输入版本 SHA256

| 文件 | SHA256 |
| --- | --- |
| docs/PART-ONE.md | 5f63d0af6e3278a119e3dae3273d7c07f7dc767fa78935dc5e2cc43f40d1931e |
| docs/PART-TWO.md | 3894fb7dc12da0160db3c3dc5c8da5020ccb35cad48bec406c111009be6e9aa6 |
| src/plcweave/workflow.py | 3636a6be825bc25057177449e7448d17490b32fb865d52c8ac10900f6d91f848 |
| src/plcweave/variants.py | 7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f |
| src/plcweave/projects.py | 61fbeb8e69c19d2a4f16ac8c5e738e51a805b7c134042e3f462833744e722fe4 |
| src/plcweave/hil.py | a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125 |
| src/plcweave/fx.py | d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98 |
| src/plcweave/testing.py | d497f27a50451cc03c40a419d07496e2c1d8dba937689f8729ac32d41155c692 |
| tests/test_workflow.py | 7a3806c820b67d24e0510f25fb3607c64147df1be34f79826242f194ca0319ba |

## 实际检查与执行

1. 阅读两份目标规范及上述实现文件，跟踪 build → confirm-download → test → delivery 的文件、源和工具哈希校验。
2. 检查指令签名白名单、物理 X/Y/D8xxx 阻断、注入寄存器禁止进入共用核心、MUL 高字保护；HIL 只开放设计中 injection 的 FC06 写入，先校验版本/指纹/套件与心跳。
3. 检查 `_child` 与 `_location`、Windows 保留名、交付成员路径、版本独占创建、阶段构建临时目录清理；正常串口异常进入 finally，close 失败不标记 serial_closed。
4. 执行 `.venv/Scripts/python.exe -m pytest tests/test_workflow.py -q -p no:cacheprovider --basetemp=logs/review-two-phase-3/pytest-rerun`，`PYTHONPATH=src`：**18 passed, 1 failed**。失败是 ZIP 测试将包解到 workspace 下 `extracted/` 而非 `project/`，随后被 `_location` 拒绝。第一次运行因本复核未先建 basetemp 父目录而产生 fixture setup 错误，已纠正后重跑；该首次错误不归因于实现。
5. 独立故障注入脚本：`logs/review-two-phase-3/probes.py`；结果：`probe-results.json`。
6. 独立超时脚本：`logs/review-two-phase-3/timeout-probe.py`；结果：`timeout-result.json`。

## 发现

### R3-1 [P2] 最后一次采样超时后仍可给出 PASS

位置：`workflow.py:336–341,369–382`。

`sample()` 只在实际通信前检查 deadline，通信后以及最终批次判定前都不再检查。真实读取在自身 0.5 秒通信超时内完成，仍可能跨过批次 deadline。若该调用恰是最后的 settled sample，后续没有下一个 `check_time()`，批次能够以 PASS 结束。

复现：合成正常启停用例，第 7 次（最后一步 settled）采样延迟 0.2 秒，`timeout_s=0.15`。结果实际约 0.372 秒，返回 **PASS**。建议采样完成后及最终通过判定前再次检查 deadline；清理使用单独的有界收尾路径。

### R3-2 [P2] HIL 被取消时虽关闭连接但不生成最终报告

位置：`workflow.py:383–414`。

运行期间 `KeyboardInterrupt` 不属于 Exception；finally 会执行复位与 close，但随后异常继续传播，跳过 finally 外的 trace 哈希、next_action 和 report.json 写入。这使用户中断批次只剩 trace，缺少明确未完成结论与实际 cleanup/close 状态，不符合异常退出保存断点及清理结果要求。

复现：DummyBench 的第二次 sample 抛出 KeyboardInterrupt，观察到 cleanup 两个输入已写回且 closed=true，`trace.jsonl` 存在，**report.json 不存在**。建议在保证最终报告持久化后重新抛出中断，且不能把中断计为通过。

### R3-3 [P2] 两阶段初始化后半段失败遗留不可重试的半成品目录

位置：`workflow.py:91–102`。

`create_project()` 只为自己的草稿写入提供回滚；`init_workflow()` 随后的 design.md 和 README.md 写入没有初始化事务清理。若该阶段磁盘/权限故障，本次创建的目录被保留，第二次相同项目名初始化会因已存在而阻断。

复现：仅对 design.md 的 Path.write_text 注入 OSError。异常后项目目录仍在，并含 README.md、requirements.md、test_cases.md，缺 design.md。建议仅回收本次新建目录，并保留对重定向/归属的检查。

### R3-4 [P2] 交付哈希清单丢失双版本文件相对路径

位置：`projects.py:105`。

清单使用 `dest.name`，因此 HIL 与 production 的 MAIN.csv、source.fxil、COMMENT.csv 和各仿真文件都以相同文件名重复出现，无法从 MANIFEST.md 识别某个哈希属于哪一个版本。BUILD.json 另有完整路径绑定，可以作为补充证据，但不能消除交付清单本身的歧义。

复现：打包 `hil/MAIN.csv` 与 `production/MAIN.csv`（内容分别 a、b），MANIFEST.md 两行均为 MAIN.csv，哈希不同但无所属路径。建议清单直接记录 filename 的规范相对路径。

### R3-5 [P2, 测试] ZIP 自包含复验测试当前失败

位置：`tests/test_workflow.py:249–251`。

测试指定 workspace=tmp_path，却把包解在 tmp_path/extracted；此目录违反项目必须位于 workspace/project 下的约束。测试在进入产物哈希验证前即失败，当前不能把整个测试文件标为全通过。应调整该合成测试解压目录或指定正确的工具工作区，再实跑确认自包含复验。

## 可确认的行为与限制

- 已有合成测试实际证明：输入/产物变更阻止旧版解锁，版本不能覆盖，三人/过期复核阻止冻结，正常/程序错误/通信错误/身份错误路径关闭 DummyBench，连续不变量不会被轮询升级为硬件 PASS。
- 阅读确认：真实 RUN/STOP 与下载不由该工作流执行；未知 target 与不在签名表中的指令明确抛出；fx3u HIL 在串口前阻断；只允许声明注入寄存器写入，没有向派生输出写入以制造通过的路径。
- 路径安全结论限于静态路径检查与现有测试，未对有权限的并发进程进行文件替换攻击测试；不主张实现具备对抗性沙箱能力。
- 当前结论为 CHANGES_REQUIRED；修复后须按新 SHA256 重查相关反例，不能将此报告作为修复版本 PASS 证据。

## 2026-10-26 独立复查

- task_id: `two-phase-20261026-review-3-recheck`
- owner: `/root/review_resources`
- 时限与结束：本轮复查当日完成，无后台工作或待执行设备操作。
- 最终结论：**PASS（资源隔离、故障与超时、路径、版本发布及对应证据范围）**，没有未关闭的本复核阻断项。此次结论由实际重跑与独立故障注入获得，没有采用主 Agent 提供的测试结果作为证据。
- 范围不扩展到厂家导入兼容性、物理端子、电气、带载、现场下载或硬件执行；文档与技能同步情况由其对应复核单独判定。

### 重查原发现

| 发现 | 实际复查 | 结论 |
| --- | --- | --- |
| R3-1 最终采样跨 deadline | 阅读 sample 后与最终判定前的 check_time；独立合成时钟在第 5 步 settled 采样增加 1 秒，0.5 秒批次返回 TEST_INFRA_ERROR / TimeoutError，清理和关闭确认 | CLOSED |
| R3-2 中断缺报告 | 第二次 sample 抛 KeyboardInterrupt，确认 report.json 已写、status=TEST_INFRA_ERROR、error_type=KeyboardInterrupt、trace 哈希匹配、cleanup=CONFIRMED、serial_closed=true，并向调用者重新抛出中断 | CLOSED |
| R3-3 初始化半成品 | 在 design.md 写入注入 OSError，确认本次 failed 目录消失；另一个 existing 项目及其需求哈希保持原值 | CLOSED |
| R3-4 清单双版歧义 | 定向测试实际生成交付包，确认清单用 build/B001/hil/MAIN.csv 与 build/B001/production/MAIN.csv 相对路径分别对应哈希 | CLOSED |
| R3-5 ZIP 解压复验测试 | 测试现在解到 project/extracted，完整实际运行通过；验证进入构建哈希校验且不再因项目位置提前失败 | CLOSED |

### 新增发布重试检查

阅读 `_publish` 及 build/交付两个调用位置，并独立执行以下反例，全部通过：

1. Path.rename 持续 PermissionError：5 次尝试，捕获的总等待量为 0.75 秒，随后传播错误；源仍在，目标未发布。
2. 第一次 PermissionError 同时由另一个拥有者创建目标：下次尝试抛 FileExistsError，原目标内容与待发布源都保持原值。
3. 交付文件夹已发布但 ZIP 发布持续失败：删除本轮已发布文件夹并清除包临时目录；delivery 目录为空，无虚假完成版本。
4. B002 构建发布持续失败：没有 B002 与 `.build-*` 残留，已有 B001/BUILD.json 哈希保持不变。
5. 重新检查共用核心 MOV 到声明注入 D1000：validate_core 明确阻断。

该检查针对当前 Windows 环境，未声称实现是对抗并发文件替换的安全沙箱。`_publish` 的 0.75 秒是重试间等待的上限，不代表底层文件系统调用本身的耗时上限。

### 本轮实际命令与结果

- `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/test_workflow.py -q -p no:cacheprovider --basetemp=logs/review-two-phase-3/recheck-workflow-20261026`：**31 passed in 10.88s**。
- 同环境执行 `tests/test_markdown_projects.py tests/test_hil_guards.py tests/test_hil_candidate_identity.py`，basetemp=`logs/review-two-phase-3/recheck-guards-20261026`：**20 passed in 0.27s**。
- `.venv/Scripts/python.exe logs/review-two-phase-3/recheck-20261026.py`：独立故障注入 **8 项检查通过**。结果保存在 `logs/review-two-phase-3/independent-20261026/results.json`。
- 本轮最初曾误写不存在的 tests/test_projects.py/tests/test_hil.py，pytest 在收集前退出、未运行测试；随后依据实际文件名执行上述两次有效检查，不把该命令错误计入实现失败。
- cleanup：所有运行已结束；仅保留本复核所属 logs 子目录中的合成客户程序和故障证据，未打开串口、GUI、网络服务或创建后台进程；没有修改实现文件。

### 复查最终输入 SHA256

| 文件 | SHA256 |
| --- | --- |
| docs/PART-ONE.md | 5f63d0af6e3278a119e3dae3273d7c07f7dc767fa78935dc5e2cc43f40d1931e |
| docs/PART-TWO.md | 3894fb7dc12da0160db3c3dc5c8da5020ccb35cad48bec406c111009be6e9aa6 |
| src/plcweave/workflow.py | 42cf8cc7d27923cff2f6a5e4448267bde9b7eaec5cd5003be473156898c19f42 |
| src/plcweave/variants.py | 7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f |
| src/plcweave/projects.py | 89d343847868a331e4854bd0f5eaee7230512fe1905cf515c0c81639d8d38653 |
| src/plcweave/hil.py | a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125 |
| src/plcweave/fx.py | d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98 |
| src/plcweave/testing.py | 8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60 |
| src/plcweave/validation.py | 5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099 |
| src/plcweave/demo.py | cbfbcf2baa6a8ddf461864157e2f3b53af39335e68b631131e665ba0453ca843 |
| src/plcweave/markdown_suite.py | 48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e |
| tests/test_workflow.py | 08333aefcca4653cc922b9dea58ecf7f0a8010abe39a97eb23366c8abb3f9354 |
| tests/test_markdown_projects.py | 0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f |
| tests/test_hil_guards.py | cb4074152379f146acb23376a8d2d491becfdba498b6a3cac7f9d4346af58bba |
| tests/test_hil_candidate_identity.py | 8d7b7df4e6c98a0595b38bf2912927ae7e93df3159457892e5b53d0bb5dd6d1e |

复查结论绑定此表版本；之后若改变资源映射、清理、超时、发布或相关验证逻辑，应重新检查受影响项。

## 2026-10-26 最终增量复查

- task_id: `two-phase-20261026-review-3-final-increment`
- owner: `/root/review_resources`
- 时限：当日定向复查；已完成。
- 最终结论：**PASS（本复核范围）**。仅复查本轮相关改动，不将上一轮 51 项测试说成已在最终版本全量重跑。文档内容与技能同步不属于此次资源/清理复核结论。

### 检查与新发现关闭

1. `require_reviews` 使用 as_posix 记录路径：读取变更，重跑 ZIP 解压自包含构建复验，Windows 下产物/复核路径哈希绑定通过。
2. design-freeze 部分写失败：本轮新建文件有显式创建标志，异常清理不会删除调用前已有的文件；对应故障注入通过。
3. **R3-6 [P2, 本轮发现后修复] s1-freeze 部分写失败残留**：最初独立在 s1-freeze.md 的独占创建后写入 10 字符再抛 OSError，实际遗留损坏 S1 冻结但 baseline 已删除，重试被“freeze already exists”阻断。反例与原结果保留于 `logs/review-two-phase-3/final-increment-probe.py`、`increment-independent-20261026/results.json`。修复后阅读 freeze_markdown 的独占创建标志与 BaseException 回滚，重新执行同一独立故障：s1/design 冻结及 baseline 均不存在，随后直接重试成功。修复复验文件为 `final-increment-probe-fixed.py`，结果为 `increment-independent-fixed-20261026/results.json`。**CLOSED**。
4. revise 校验旧 baseline 三份 MD：确认验证在 revisions 创建前执行；复制 previous 后再次核验哈希，失败走仅本次目录回收。三种旧快照损坏均被定向用例拒绝，未生成新版本目录。
5. 无尾换行差异：diff 按行补规范换行，不修改旧 MD 原字节；定向测试确认删除行与新增行分别呈现。
6. demo 摘要：读取单一 `项目名-replay` 的生成和 PowerShell 单引号转义；离线段始终使用 --not-connected 且仅有 start/simulate/deliver V001，硬件段独立列出成功编译/RUN、confirm-bench 和 V002。生成命令回归实际执行离线三条 CLI，生成新项目交付且没有下载确认或硬件报告。该测试通过 Python 模块执行等价 CLI 参数，未运行串口、preflight 或硬件段，也不声称厂家编译通过。
7. projects.py 本轮仅文件末尾空白变化；对比上一轮逻辑无新增资源或发布语义。

### 最终版本实际执行

- 工作流定向 `-k 'partial_design_freeze or revision_rejects_corrupted or requirement_diff or stage_one_zip'`：**5 passed, 43 deselected**（加入 markdown_projects 文件但其名称未匹配过滤式；没有把被 deselect 的项计入通过）。
- 工作流定向 `-k partial_freeze`：**2 passed, 46 deselected**，分别故障注入 design-freeze.md/s1-freeze.md。
- `tests/test_markdown_projects.py`：**11 passed**。
- `tests/test_demo.py -k delivery_reproduction_commands_run_offline`：**1 passed, 26 deselected**。
- 合计最终版本相关测试 **19 项通过**，另有独立 S1 故障/清理/成功重试反例通过。临时路径全部在 `logs/review-two-phase-3/`。
- 所有命令使用 `.venv/Scripts/python.exe`、`PYTHONPATH=src`、`pytest -p no:cacheprovider`，basetemp 使用本复核的 final-increment/final-freeze/final-markdown 子目录。
- cleanup：执行已结束；本次仅保留所属日志中的合成文件和证据，没有后台进程、串口、连接、GUI 或锁，无实现文件改动。

### 最终输入 SHA256（取代前一轮版本表）

| 文件 | SHA256 |
| --- | --- |
| docs/PART-ONE.md | 310f797286af6d69a3c801b0e1bea58343c7777c1f12afe81bec80c2becd3585 |
| docs/PART-TWO.md | 0f896bea36cbfda20e0bae6dbc802d6b8d9e0af1af455ff164bb9044393c3d2a |
| src/plcweave/workflow.py | 43cc72d255193c3047ff6369ac55b434af334ea658aac678b1be91319ac4a020 |
| src/plcweave/variants.py | 7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f |
| src/plcweave/projects.py | 0ab14695cd9eb2c6ed4937bab3158bbd57a6d98e56158d03612f7be5fd634b0c |
| src/plcweave/hil.py | a2508d5deed58819b82bee6d8e97d5bd2399dc32579a9dfbc541767a2eb99125 |
| src/plcweave/fx.py | d92be0d668f219af6197eefddc7cce228638d327c209897845f7b10d70b06c98 |
| src/plcweave/testing.py | 8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60 |
| src/plcweave/validation.py | 5e4d4b2ad351bb69efb3e9d5d0a651d0399cb43303c0bce299e7d09d93524099 |
| src/plcweave/demo.py | eff8f13c870a08303090d0dd662ce8b16ad014cf40ea22c332cc9e6f77060b1e |
| src/plcweave/markdown_suite.py | ed5f50aee5fe10452d208dd7620aa28b8c11bda2c5a6da6114eff5baaa16d4de |
| tests/test_workflow.py | 7fdc38414f4f5385b4d1690ddaaba91876cc0360dcab8adbdd743ec920f8b763 |
| tests/test_markdown_projects.py | 0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f |
| tests/test_hil_guards.py | cb4074152379f146acb23376a8d2d491becfdba498b6a3cac7f9d4346af58bba |
| tests/test_hil_candidate_identity.py | 8d7b7df4e6c98a0595b38bf2912927ae7e93df3159457892e5b53d0bb5dd6d1e |
| tests/test_demo.py | b6268151a6a601c64ac737f48273fc5e5a7c53c7d2b5c8031ef56cce8a0b9c18 |
