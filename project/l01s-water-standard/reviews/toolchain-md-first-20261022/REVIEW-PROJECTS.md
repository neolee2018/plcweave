# R2 独立复核：客户项目隔离、历史迁移与交付打包

- task_id: PW-20261022-MD-PROJECTS-R2
- owner: review_projects；时限：15分钟；复核日期：2026-10-22
- 结论：**PASS**。先前发现的3个具体反例均已修复并独立复验；本范围未发现待修复问题。
- 范围：src/plcweave/projects.py、src/plcweave/__main__.py、tests/test_markdown_projects.py；迁移清单及新V002-final交付只读校验。
- 未使用串口、GUI、PLC；未改实现、客户文件、历史冻结内容或交付包。
- ZERO入口因凭据文件PermissionError不可用，明确离线；未读取或打印凭据。已检索团队经验，未用记忆替代实时状态。

## 实际运行与路径问题关闭

最终独立运行tests/test_markdown_projects.py：**11 passed in 0.22s**。使用本仓.venv Python、sys.path插入src及本任务专用logs basetemp，避免系统TEMP目录权限问题。

另在本任务TemporaryDirectory内通过实际Windows junction与故障注入完成验证：

| 项目 | 实际检查与结果 |
| --- | --- |
| 默认project根junction外逃 | CreateJunction将repo/project指向外部，未传directory时拒绝，外部目录无新文件，PASS |
| 默认project/name悬空junction外逃 | 将repo/project/indirect指向外部空目录，再删除该空目标形成悬空junction；未传directory时拒绝，外部目标未创建，PASS |
| 初始化中途写失败 | 第二次write_text(test_cases.md)注入OSError，本次新建目录回收；同名重试成功，PASS |
| 显式外部授权 | directory显式指向临时外部目录时创建成功，PASS |
| 客户隔离 | 仓库src/customer路径拒绝；项目外文件及项目内指向外部的junction输入拒绝，PASS |
| Windows名称 | ../escape、CON、NUL.txt、LPT1、尾点、前空格、斜杠、反斜杠、冒号拒绝，PASS |
| 交付文件选择 | ZIP只含显式选择文件及MANIFEST.md，未选文件不进入ZIP，PASS |
| 哈希及原文件 | 目录清单、ZIP清单、ZIP实际内容SHA256一致；打包前全部原文件SHA256保持一致，PASS |
| 不覆盖 | 同版本拒绝且既有ZIP SHA256不变，PASS |
| 文件名冲突 | basename按大小写折叠冲突及manifest.md保留名拒绝，PASS |
| 异常清理 | copy2故障无发布目录；ZIP最终rename故障回滚版本目录；均无.package-*残留，PASS |
| 交付目录重定向 | delivery指向外部junction时阻断，PASS |

首次复核曾确认默认project根junction外逃与初始化半成品问题，第二轮补充确认悬空子junction变体；最终完整默认目标的resolve检查及初始化失败清理已逐项复验通过。不是仅凭阅读修改后的源码判定关闭。

CLI只读复核：init的--directory进入create_project；package重复--file明确选择交付文件；版本参数进入package_delivery，未发现CLI层额外问题。

## 历史迁移只读复核

读取project/l01s-water-standard/migration/20261022-paths.md的**830条**记录，逐个重新计算新路径文件SHA256：**828匹配、0缺失**。两项当前差异仅为已单独声明的活动run_hil02.py路径兼容修复及其__pycache__/run_hil02.cpython-313.pyc，符合修复范围。

另把evidence、冻结、requirements、test_cases、candidate、versions、历史delivery及ZIP列为关键证据，共**518项，全部匹配迁移清单**。未发现冻结输入、两轮执行器证据快照、历史报告或ZIP被改写。这里直接确认的是“当前文件与迁移记录哈希匹配”；迁移发生当刻的前后哈希采集由迁移执行方记录。

private/已不存在，project/当前有l01s-water与l01s-water-standard两个客户目录及公共README.md。git check-ignore实际确认两个客户requirements.md均被忽略；git ls-files project无客户已跟踪文件。全局Git ignore配置读取存在权限警告，不影响本仓检查结果。

## 最新正式交付独立核验

目录：project/l01s-water-standard/delivery/V002-final/

ZIP：project/l01s-water-standard/delivery/l01s-water-standard-V002-final.zip

实际内容恰为4件原始交付文件与MANIFEST.md：MAIN.csv、COMMENT.csv、Blackbox-Test-Cases_EN.pdf、L01S-Water-PI-il-annotated_EN.pdf。

逐项核验新目录文件、ZIP内容、MANIFEST SHA256与原交付文档/V002-bench-demo文件SHA256全部一致；ZIP内MANIFEST与目录MANIFEST字节一致；ZipFile.testzip()返回None。未重新生成PDF。

ZIP大小：466603字节。

ZIP SHA256：fe629cab4a3a83ee0efed3062b0f8cdb7cd019662ba49427120b49f771807e5c

## 结束与cleanup

所有额外反例均位于本任务logs/review-projects-* TemporaryDirectory，退出后断言不存在；pytest专属目录先核验绝对路径属于本仓logs及本任务精确名称后清理。没有长期进程、连接、串口、GUI、锁或临时文件残留。最终产出仅本报告；未新增测试源码或修改实现。

本结论限于文件项目组织、打包、迁移完整性及实际软件检查，不声称重新执行硬件验证，也不把其他Agent报告的全仓97通过计作本Agent独立运行证据。

## 最终受检输入版本

- src/plcweave/projects.py: a10133a1a9a3c47db4415717fe4d8cb27f04506dd3f10066f74ecea3f3e9c863
- src/plcweave/__main__.py: 3e78ab526dc4169204c0b4b25f3a7c738afd46708500a218413769b4a2fa5409
- tests/test_markdown_projects.py: 0cdaf60bde2a5363cd1199f35ea0c5d859e327b619841bde8ff3fa786f1bab0f
- project/l01s-water-standard/migration/20261022-paths.md: 6559a7e16696c6b8be5e48c32a5da4fc0aac4ed74ac24b612b7ca86974ff090b
