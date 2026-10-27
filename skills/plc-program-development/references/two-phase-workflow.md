# 两阶段开发、双程序与HIL执行

适用：客户定制工程。固定首次演示仍用仓库 `PROMPT.md` / `demo/START-HERE.md`，不要把单程序演示当作双程序正式工作流。

用户只需提供并修改 `requirements.md`。AI负责需求澄清、影响分析、资源分配、`design.md`、独立 `test_cases.md`、共用 `source.fxil`、测试脚本和交付。CLI是确定性执行工具，不会自行调用模型或从自然语言编造控制逻辑。以下命令由有终端能力的Agent执行；仓库根使用 `./tools/plcweave.ps1`，安装后可用 `plcweave`。

## 能力范围

- 当前构建适配器仅接受 `target=l01s` 或 `fx3u` 的受支持FX指令子集；厂家导入文件为GX Works2列表方言的 `MAIN.csv` / `COMMENT.csv`，UTF-16、引号制表符、CRLF。真实厂家导入、CPU适配和编译由用户验证，工具不执行下载。
- 新HIL执行器仅接受 `target=l01s`、`protocol=l01s-modbus-rtu`，基于已有L01S寄存器映射；用户仍须确认实际PLC型号/固件和接口依据。不能把此映射用于任意三菱PLC。台达WPLSoft/ISPSoft导出与运行映射尚未实现，遇到该目标明确阻断，不能拿FX文件代替。
- 测试版只注入声明的内部D输入并观测逻辑M/D；正式版接真实X/D8030–D8033输入、Y/D8050–D8051输出。两版共用控制核心，分别真实执行本地仿真。正式版每扫描还比较逻辑输出与物理输出映像的一致性；这是模型检查，不是电气/实机证明。
- HIL轮询只能对明确标为 `hardware_scope=steady_state` 且不含连续不变量的标量用例给出PASS。未知精度、连续不变量、扫描瞬态、首扫/重启/保持语义不由本执行器证明；用适用观测手段和独立后端补证，不能为了通过删减已有要求。

## 第一阶段

```powershell
./tools/plcweave.ps1 workflow init 客户项目名
# AI完善requirements.md、design.md、独立test_cases.md；四位独立Agent完成S1复核。
./tools/plcweave.ps1 workflow freeze project/客户项目名
# 冻结之后AI编写source.fxil中的共用控制核心。
./tools/plcweave.ps1 workflow build project/客户项目名 --version B001 --port COM7 --baud 9600 --parity N --station 1
./tools/plcweave.ps1 workflow status project/客户项目名 --build B001
# 四位独立Agent对实际构建、两版回归和交付一致性复核后：
./tools/plcweave.ps1 workflow deliver project/客户项目名 --build B001 --stage 1 --version V001-stage1
```

初始化只产生MD草稿，原始 `init` / `freeze` 命令保留兼容用途；新客户双程序流程使用 `workflow` 前缀。`freeze`建立需求/用例/设计的MD历史快照和哈希，不产生第二套可编辑作者源。`build`不覆盖既有版本：生成 `build/B001/hil/` 和 `production/`，各有 `source.fxil`、`MAIN.csv`、`COMMENT.csv`、`instruction_list.md`、本地报告/轨迹；另有 `BUILD.json`、`inputs/` 原始输入证据和项目 `run_hil.py`。

交付四类成果：需求文档、设计方案、测试用例、程序说明及两份可导入指令表。客户在 `delivery/<版本>/` 和对应ZIP中得到同一版本的完整结构、配套证据、复核记录、总结和路径明确的哈希清单。PDF是用户明确需要时的额外排版产物，不是本阶段默认作者源。

## design.md可执行接口

`workflow init`创建完整的空表。AI在设计正文说明功能、状态、时序、报警、依据、覆盖和资源占用，并填写下列精确表头；不另建JSON设计作者源。以下片段仅说明格式，完整合成示例见工具 `tests/test_workflow.py`，不是客户或硬件验证记录。

```markdown
## PLCWeave
| key | value |
| --- | --- |
| target | l01s |
| protocol | l01s-modbus-rtu |
| program_version | 1 |
| edition | 51 |
| suite_word | 1 |
| reset_ms | 100 |

## Inputs
| logical | physical | injection |
| --- | --- | --- |
| M100 | X0 | D1000 |
| M101 | X1 | D1001 |

## Outputs
| logical | physical |
| --- | --- |
| M0 | Y0 |

## HIL reset
| device | value |
| --- | --- |
| D1000 | 0 |
| D1001 | 1 |

## Reset expectations
| device | value |
| --- | --- |
| M0 | 0 |

## HIL cleanup
| device | value |
| --- | --- |
| D1000 | 0 |
| D1001 | 1 |

## Cleanup expectations
| device | value |
| --- | --- |
| M0 | 0 |
```

当前地址须为无前导零的规范名，X/Y后缀按八进制解释。逻辑输入/输出使用M0–M7679或D0–D7999，D196–D202留给身份和心跳，不得重叠；注入地址使用独占内部D，不得与控制核心或映像重叠。复位和清理必须给出全部注入输入及每个逻辑输出的预期。实际资源分配仍须确认型号/固件、保持区和地址能力，不能只以解析通过代替资料核验。

测试用例只向 `injection` 地址施加输入，观察公共逻辑映像。`Initial`是每例设计复位之后的输入覆盖；`Steps`的 `duration_ms`表示保持该输入至少这么长后比较稳态。两版仿真与HIL均先施加设计复位。HIL收尾读回逻辑输入以证明PLC消费注入；该证据不代替物理端子或电气验证。

共用程序按现有FXIL格式写 `#meta` / `#instructions` / `#comments`，保留一个终止END，只访问内部控制映像及受支持的时钟/首次扫描继电器。不得直接访问X/Y、专用D、注入寄存器或写逻辑输入；受支持的指令/地址以执行器实际检查为准，间接、块操作和未覆盖指令应阻断。测试版通信、身份、输入映射由构建器生成；正式版不包含这些测试接口。产品确实需要的通信/诊断若超出本适配器范围，应补实现和验证，不能悄悄删除需求。

## 独立复核记录

每个节点需四名不同独立上下文Agent，主Agent不计入。记录各自实际检查、问题及结论，不要求通过，不伪造记录。工具读取项目内 `reviews/<节点>/*.json` 作为执行元数据；复核正文可另存MD。节点和必须绑定的原文件如下：

| 节点 | input_sha256所需原始文件 |
| --- | --- |
| S1 | requirements.md、test_cases.md、design.md |
| stage1-B001 | 上述三份、source.fxil、s1-freeze.md、design-freeze.md、baseline/s1/三份MD、build/B001/BUILD.json |
| stage2-B001 | stage1全部输入，另加同一最终批次evidence/hil/B001/T001/report.json与trace.jsonl |

每位复核者在自己的记录中填写 `reviewer_id`（唯一，不能是main或/root）、`independent: true`、`verdict: "PASS"`、非空 `checks` 字符串数组、`blocking_findings: []`、`input_sha256` 对象（相对路径→原始字节SHA256）。存在阻断问题则如实写其他结论和问题，此时工具拒绝冻结或交付。JSON记录只证明记录结构、署名区别和输入版本匹配，不能机械证明上下文真的独立；主Agent必须真实组织四位复核。

## 第二阶段

用户在GX Works2中导入 **hil/MAIN.csv及同目录COMMENT.csv**、选择正确CPU、编译并下载HIL版。只有用户明确确认本版成功编译、下载并RUN之后，AI才记录：

```powershell
./tools/plcweave.ps1 workflow confirm-download project/客户项目名 --build B001 --operator 操作者 --software "GX Works2 现场版本" --compiled --running
```

连接参数已知时复用。HIL构建时写入PLC的波特率/校验/数据位/停止位/站号来自同一设置；改变这些参数需要新build和重新下载，端口号可以在测试时更换。先安装可选HIL依赖，再在用户明确确认连接、RUN、隔离空机及测试范围后执行：

```powershell
./tools/plcweave.ps1 workflow test project/客户项目名 --build B001 --batch T001 --port COM7 --connected --running --isolated-bench
# 同一入口也由build/B001/run_hil.py调用，可用同版已安装环境运行该脚本并传同样确认参数。
./tools/plcweave.ps1 workflow status project/客户项目名 --build B001
```

先只读校验PLC身份/合同指纹/套件字和心跳，不符则不注入；指纹绑定冻结需求、设计、用例和程序，完整主机哈希与人工下载记录仍保留。脚本记录输入、实际寄存器数据、时间戳、采样跨度、预期差异及清理结果到 `evidence/hil/B001/T001/`。超时和取消也保留报告与轨迹，清理连接后取消继续向上抛出；不能把通信缺失填0或把未采样部分算通过。缺少同版确认、条件、能力或映射时不访问设备。

若 PROGRAM_FAIL，AI定位并修复 **同一冻结基线的共用核心**，用新build（B002）生成两版、执行本地回归、更新程序说明；由用户重新导入编译下载并确认B002，AI才再次测试。不得放宽预期或把通信/脚本错误当作PLC程序缺陷。TEST_INFRA_ERROR先修基础设施；UNVERIFIED补观测能力。目标全部规定测试通过；等待用户下载或连续无改善时保存断点和具体下一步，不无限盲试。

全部规定用例必须在最终同版单一批次有PASS和确认清理；经四位独立Agent复核后才可：

```powershell
./tools/plcweave.ps1 workflow deliver project/客户项目名 --build B001 --stage 2 --batch T001 --version V001-stage2
```

测试版HIL通过不会把正式版硬件等级升级；正式版的真实I/O、传感器、电气及带载仍按项目验收范围另行验证。

## 需求变更

用户只编辑requirements.md后，AI运行：

```powershell
./tools/plcweave.ps1 workflow revise project/客户项目名 --version V002 --reason "需求新增传感器、按钮或LED"
```

工具在项目 `revisions/V002/` 创建未冻结的新修订，带当前需求、待审设计/用例、旧MD历史原文和需求差异。AI读取差异并实际更新资源分配、设计及独立测试；重新组织S1复核、冻结，再编写共用程序、生成双版、回归并交付。工具不会自动替AI完成自然语言影响分析和程序设计。旧快照、构建、下载/测试证据及交付均保留，不继承不适用的旧PASS。
