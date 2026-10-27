# REVIEW-4：项目隔离、文档、交付与可复测性

- task_id：review-two-phase-4-20261026
- reviewer：`/root/review_delivery_docs`，第4名独立新上下文复核者；主Agent不计入本复核。
- owner：本复核者；资源及临时成果仅 `logs/review-two-phase-4/`，正式成果仅本报告。
- 开始：2026-10-26 11:27（Asia/Shanghai）；时限：2026-10-26 12:30。
- 结论：**PASS（本次工具/流程变更的本复核范围）**；当前无未关闭阻断问题。本结论不代表任何客户程序通过，不代表PLC、厂家软件、串口或电气/带载验证。

## 验收依据与独立性

依据原始要求检查第一阶段“需求→资源/独立用例→编程→语法/回归→四类成果、HIL和正式版双指令表”，及第二阶段“用户厂家编译下载→AI采集/比较→程序修复同步双版并重新下载→同版全部规定用例通过”。用户仅编辑需求，AI维护下游；客户隔离、旧证据和交付版本保留、完整ZIP可复测为必要条件。

本复核只接收任务、原始文件和验收边界，未读其他复核者报告；主Agent的修复通知仅作为重新检查线索，结论来自本次读文件及实际执行。团队记忆查询只作历史线索，未作为实现或验证证据。ZERO实时wake成功，返回数据包含STALE来源，不据其陈旧项目项推断当前完成状态。

## 实际检查

1. 对照PART-ONE/PART-TWO、双语README、AGENTS、项目说明、技能和两阶段参考逐项检查CLI及能力声明：当前受支持FX子集、L01S专属HIL映射、人工厂家编译下载、稳态采样、正式版物理I/O另行验证均有明确限制；未把自然语言设计、台达适配、自动下载或正式硬件验收写成已实现。
2. 读取projects/workflow/variants：独立MD草稿、S1原文快照和哈希、先冻结后程序、共用核心生成双版、正式版去除注入/身份/通信测试接口并接真实I/O、独立本地执行、不可覆盖build/delivery、变更使旧build失效、修复需新build/新下载确认、最终单批次全部用例和清理门禁、相对路径与选定文件打包均有落实。复核JSON为签名和版本元数据，工具不能证明真实上下文独立；文档已如实说明。
3. 实际隔离测试：初次68项通过。复核修复后最终运行以下命令：

   ```powershell
   $env:PYTHONUTF8='1'; $env:PYTHONPATH='src'; $env:PYTHONDONTWRITEBYTECODE='1'
   .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_workflow.py tests/test_demo.py tests/test_markdown_projects.py --basetemp=logs/review-two-phase-4/pytest-final
   ```

   **74 passed in 14.45s**，最终输出保存在 `logs/review-two-phase-4/pytest-final.txt`。测试包括合成Bench的采集/比较和清理异常门禁；这些都是工具自动测试，不是PLC硬件证据。另单独重跑当前workflow 36项、demo 27项均通过。
4. 自编独立探针 `logs/review-two-phase-4/independent_checks.py`：合成工程实际构建双版并交付stage1 ZIP；ZIP CRC和所有MANIFEST文件SHA256一致；解包后 `validate_build` 通过，CLI status正确停在BUILD_OR_DOWNLOAD_REQUIRED，解包run_hil.py --help可用；直接用解包HIL程序实际再仿真，得到SIM_PASS。没有运行任何硬件脚本/打开串口。测试合成的复核JSON仅用于工具门禁，不是客户或真人复核证明。
5. 同探针验证未选取文件、另一合成客户文件均不入包，直接选择另一客户文件拒绝；仓库根、project容器、src/docs内客户目录拒绝。默认每客户独立目录和显式外部目录在回归中验证。`.gitignore`默认忽略project客户内容，仅保留README。
6. 在隔离合成工作区实际运行根PROMPT模式A四条命令：demo start --not-connected → simulate → status → deliver。8/8用例、SIM_PASS、60.0%、S6未执行、无manual_download确认；交付ZIP生成，未冒充定制双程序交付。
7. `logs/review-two-phase-4/check_sync.py`在完全复制到本任务logs的合成仓库和旧技能上实际运行同步两次：原正文保留、备份保留原文、修订标记不重复、技能正文和两阶段参考链接目标存在。真实全局技能未修改；此测试没有把更新旧技能工具当新安装器。
8. 最终重新检查revise的三份旧baseline原文哈希、复制后校验、无尾换行diff：读取当前实现和新增用例，最终74项中全部通过；旧数据损坏在创建新修订前阻断。源/冻结/构建输入变化不能继承旧验证结果。

## 发现、复现与复查

**R4-01（已关闭）生成的旧演示SUMMARY复现段与CLI不一致。** 实际无硬件交付摘要给出 `demo start project/root-prompt-demo --not-connected`；本复核实际执行后退出1，错误为 `Use a single valid project/version name`。同段硬件续测缺少confirm-flash必需的编译/RUN参数和confirm-bench，且复用已存在V001交付版本。本复核通知主Agent修复，没有修改实现。

修复后本复核重新生成摘要，独立解析并实际执行其第8节三条无硬件复现命令，新的单名称 `*-replay` 工程成功建成、仿真、V001交付。续测文本完整包含编译/RUN、隔离/485确认和新交付V002；硬件段只读审查，未执行。新增仓库回归 `test_delivery_reproduction_commands_run_offline_in_a_new_project` 也在最终27项demo测试中通过。因此R4-01关闭。

探针开发时有两次本复核脚本断言错误，分别是CLI仿真stdout前含用例行不能整体当JSON、报告完成度实际格式为60.0%。修正探针解析后再次实际运行成功，未将探针自身错误归因实现。最初误写不存在的测试文件名导致pytest零测试的尝试未计入通过数量。

## 边界及cleanup

此次没有安装依赖、调用厂家软件、打开GUI、连接PLC/串口、创建监听端口或客户项目。CPython 3.13.2 / Windows AMD64；现有执行核原生二进制SHA256为 `21ebd9f071b3eafeff77f67bc22fcfe2829183047e45d2527b0f1f95816e9ff6`。解包可复测仅实证本机同版工具与该执行核；不据此声明跨系统安装、厂家导入编译或实际PLC通过。

所有本复核子进程均已返回，无服务/连接/GUI/串口/锁需回收。任务范围内未残留 `.build-*`、`.package-*`、`.delivery-*` 临时目录。隔离测试文件、合成ZIP及探针证据保留在本任务logs，供30天内审计；不删除用户或其他Agent资源。未改实现、其他报告、客户内容或全局技能。

## 最终实际读取文件SHA256

以下为复查完成时原始字节SHA256；结论仅适用于列出的版本，后续变动需按影响复查。

| 文件 | SHA256 |
| --- | --- |
| `AGENTS.md` | `91d2e139e6a154d3c0edbd58b394af02980bbfd1ceb94bcdaca61cd55d375eb7` |
| `docs/PART-ONE.md` | `310f797286af6d69a3c801b0e1bea58343c7777c1f12afe81bec80c2becd3585` |
| `docs/PART-TWO.md` | `0f896bea36cbfda20e0bae6dbc802d6b8d9e0af1af455ff164bb9044393c3d2a` |
| `skills/plc-program-development/SKILL.md` | `f8c94cc427782b5a35a616c08ec99f25f5fc5dc0bee7039b418b8c8ca2ebc965` |
| `skills/plc-program-development/references/two-phase-workflow.md` | `7d0300cd87891b5c5a17343aae1f25962c1a494b6aac425b60d7383c6ff390bf` |
| `skills/plc-program-development/references/markdown-cases.md` | `b67494703545703d3aa36823ab019063f2138312b7aa19ea90fa1d10ee6f0b2c` |
| `README.md` | `c3e20f0c3498185ecfa8f9b4bea7293df57dba699006c70ed6e7c5a8dad2ac76` |
| `README.zh-CN.md` | `eebb81dcbebdd8b41fcde3977dfc30bd0d0da461ac30196674d82ad7c8126166` |
| `PROMPT.md` | `44d0af3dcf6f123e7dacb3eac0753fc85b3c487c30d0e37310d9ff5649ebe4e4` |
| `demo/START-HERE.md` | `a344b0dddb02cc555f53ef729209f022d8ac3a08c1cdad3836a423eef4468ac6` |
| `.gitignore` | `d01b9145cb5012e61f0616ba0b770f3b7666f34b1d58adf28e5d4a43f7bd0559` |
| `project/README.md` | `2ac1611b289d7d5800fcc66e96bd75d44c9ad8035b2c80c49a0c859fe212795d` |
| `tools/sync_plc_skill.py` | `2be9d2f52cde6a5a0fa6c1af5fed55d7ba9cde1915218475557b8b5170908677` |
| `tools/plcweave.ps1` | `46199f744bfae2ec9733ab926e11181c1764e51171af63bd6834c686228c0c4e` |
| `src/plcweave/workflow.py` | `43cc72d255193c3047ff6369ac55b434af334ea658aac678b1be91319ac4a020` |
| `src/plcweave/variants.py` | `7d6b7a712f9205db04b5c2ee35d78a5cbcc3e65443eed10ddfcf6be2edf39b9f` |
| `src/plcweave/projects.py` | `0ab14695cd9eb2c6ed4937bab3158bbd57a6d98e56158d03612f7be5fd634b0c` |
| `src/plcweave/__main__.py` | `719df617402704aee3aeeb72d690c42689c565a47ecc9854085da53875fe6c22` |
| `src/plcweave/demo.py` | `eff8f13c870a08303090d0dd662ce8b16ad014cf40ea22c332cc9e6f77060b1e` |
| `src/plcweave/markdown_suite.py` | `48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e` |
| `src/plcweave/testing.py` | `8323dde4b0867daa0ee2024347edd20aa8972518abeb6563b22ee8e112956a60` |
| `tests/test_workflow.py` | `cbd5eeab9d67714b18fc3eb55191412a6c0a52451e85d8ada3e3f9f729f8d090` |
| `tests/test_demo.py` | `b6268151a6a601c64ac737f48273fc5e5a7c53c7d2b5c8031ef56cce8a0b9c18` |
| `tests/test_markdown_projects.py` | `0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f` |

记录完成（UTC）：2026-10-26T03:34:15.038266+00:00。

## 最后增量复查：S1部分写失败清理

2026-10-26按增量通知重新实际阅读 `src/plcweave/markdown_suite.py` 的 `freeze_markdown` 及 `tests/test_workflow.py` 对应参数化测试，并对照本复核24文件哈希快照。仅以下两份文件变化，其余22份输入哈希相同。

新增 `created` 标志在独占创建成功进入写入后设定，捕获写入/退出关闭过程的 `BaseException`，仅删除本次创建的 `s1-freeze.md` 再抛出异常；先前已有文件在独占打开失败时不由此路径删除。成功路径的冻结文本、原文哈希、先冻结后程序与返回值未变。对应故障测试现在分别覆盖 `design-freeze.md`、`s1-freeze.md` 部分写失败，并检查本次冻结与baseline回滚、原需求和复核记录保留。

据此，本复核此前关于成功交付结构、ZIP清单、项目隔离、解包布局与运行入口、文档一致性和根PROMPT无硬件流程的结论仍适用；未发现本增量引入这些范围的新阻断。此次按变化范围作代码和测试内容复查，未重跑74项，也未把主Agent另报156项结果计为本复核亲自运行。故障注入的实际独立执行由其他复核者负责，不在此代签其结果。

`BUILD.json`绑定工具哈希，故旧构建/旧ZIP在更新后的工具上会按设计要求重新构建；本增量说明不声称先前已生成的旧包可绕过该版本门禁。此前解包再执行的真实记录适用于当时匹配的工具哈希，新交付仍须使用当前工具新建build和新版本包。

| 最后变更文件 | 本次实际读取SHA256 |
| --- | --- |
| `src/plcweave/markdown_suite.py` | `ed5f50aee5fe10452d208dd7620aa28b8c11bda2c5a6da6114eff5baaa16d4de` |
| `tests/test_workflow.py` | `7fdc38414f4f5385b4d1690ddaaba91876cc0360dcab8adbdd743ec920f8b763` |

增量cleanup：仅追加本报告，无新进程、设备连接或临时工程，无资源待回收。本复核范围结论维持PASS；无客户或硬件通过声明。
