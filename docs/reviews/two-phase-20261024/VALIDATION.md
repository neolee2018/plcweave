# 两阶段工具改造验证记录

日期：2026-10-26；task_id：PW-20261024-TWO-PHASE-IMPLEMENT；owner：Codex /root。本文件是主Agent执行与复核汇总，不代替四份独立结论。基于HEAD `be13030`及本次工作树修改；不回退此前的一条提示词演示改造。

## 实际实现

- `workflow init/freeze/build/deliver`承载第一阶段：AI维护MD需求、设计、独立测试和共用控制核心；构建HIL/正式版两份指令表及说明，分别执行本地回归，复核后打包完整目录与ZIP。
- `workflow confirm-download/test/status`承载第二阶段：保留用户厂家编译下载，绑定源/构建/套件/工具版本；脚本受控注入、证明输入已消费、记录实际返回数据、比较并输出修程序/重新下载或修测试基础设施/补观测的下一步。
- `workflow revise`保存旧需求、设计和用例原文及差异，新修订不继承不适用的冻结或PASS。冻结和构建均保留输入证据；旧快照被破坏时拒绝修订。
- 回归覆盖共用核心、两版I/O映像、旧确认失效、缺失/失败/未验证判定、取消与超时留证、写失败回收、文件锁有界重试、版本拒覆盖、清单相对路径和ZIP解包复测。
- 同步技能、执行参考、AGENTS、双语README和阶段规范；修复演示总结内的复现命令，保留根PROMPT固定场景入口。

使用步骤：[两阶段工作流](../../../skills/plc-program-development/references/two-phase-workflow.md)。

## 主Agent实际执行

在仓库根设置 `PYTHONPATH=src`、`PYTHONUTF8=1`，使用本仓 `.venv/Scripts/python.exe`：

```powershell
python -m pytest -q -p no:cacheprovider --basetemp=logs/two-phase-final-all-20261026
```

实际结果：**156 passed in 14.23s**，退出码0。这里的 `python`指上述本仓解释器，不是随意的系统解释器。

另完成：

- `workflow --help`、`workflow build --help`、`workflow test --help`实际调用成功。
- skill-creator的 `quick_validate.py skills/plc-program-development`实际返回 `Skill is valid!`。
- `git diff --check`通过（仅Git换行格式提示，不是空白错误）。
- 演示SUMMARY新生成的三条无硬件命令由回归实际执行：新建独立replay项目、仿真并交付；无下载确认、无硬件报告。

最初续跑出现两个不同fixture的目录发布 `PermissionError/WinError5`；修复为源文件归属不变、拒绝覆盖的有界重试，持续失败仍退出并回收本次临时成果。独立故障注入验证了尝试次数和0.75秒等待上限，最终完整回归通过；未放宽任何PLC预期。

## 独立复核

四名不同独立上下文Agent，主Agent不计入；先三名再补第四名，问题由原相关复核者复查。原始失败和每次输入SHA256保留在各自报告，不能把初查写成已经通过。

| 复核者 | 检查范围 | 独立记录 |
| --- | --- | --- |
| /root/review_requirements_tests | 需求/用例独立性、复位一致性、旧MD原文、修订与突变检出、冻结失败 | [REVIEW-1](REVIEW-1.md) |
| /root/review_execution | 双程序执行、合同身份、旧确认阻断、采样比较与判定 | [REVIEW-2](REVIEW-2.md) |
| /root/review_resources | 路径/资源/写入隔离、超时取消、部分文件失败和发布回收 | [REVIEW-3](REVIEW-3.md) |
| /root/review_delivery_docs | 客户隔离、双版交付、清单/ZIP/解包复测、技能和文档/演示一致性 | [REVIEW-4](REVIEW-4.md) |

各报告仅对列明版本和检查范围作结论；工具四条署名记录本身不能证明上下文独立。测试中的reviewer和Bench为明确标注的合成fixture，未用作客户独立验收或实际硬件证据。

## 验证边界和资源

当前适配器覆盖受支持FX指令子集、GX Works2列表方言输出和L01S已知映射下的稳态采样编排。台达WPLSoft/ISPSoft适配尚未实现；其他机型/协议、扫描精确时序、厂家编译以及正式版真实I/O、电气/带载均不能由本次工具测试推断通过。

本次没有连接PLC或串口、运行厂家软件、下载程序、改变RUN/STOP、开启GUI或监听服务。所有测试及独立反例在专属logs目录内同步退出；证据按日志保留规则留存，未清理其他任务或用户应用。最终回归的临时构建/打包目录另行核验；Hindsight/ZERO仍为公司内部可选入口，不成为公开运行依赖。
