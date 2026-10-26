# 两阶段工具修改独立复核 3

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
