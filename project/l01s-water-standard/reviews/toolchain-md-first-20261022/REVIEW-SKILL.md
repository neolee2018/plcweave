# 独立复核 R4：技能、入口和用例规范

- task_id: PW-20261022-MD-PROJECTS-R4
- owner: review_skill_workflow
- deadline: 15分钟
- 独立性：新上下文，仅接收需求、文件范围和资源边界；未读取主会话历史；未借用其他复核者结论。
- 范围：仓库技能、MD用例规范、最终AGENTS/README/全局技能入口与实际CLI的一致性。只读源码和文档，不评定客户程序及硬件结果。
- 开始：接收R4任务后立即审阅仓库技能和真实CLI源；最终核对完成：2026-10-22T15:20:48.433510+00:00
- 资源归属：仅本次前台只读命令及内存解析；唯一持久写入为本报告。

## 结论：PASS（限本复核范围）

四项要求均有明确、相互一致的规则入口，未发现阻断问题。

| 要求 | 实际证据与判断 |
| --- | --- |
| 第一版需求和测试仅MD | skill Markdown优先节明确requirements.md/test_cases.md为唯一作者源；不提前另存JSON/YAML/CSV/HTML/PDF；S1记录MD字节哈希，复杂套件仍只放在同一MD。reference与parse_markdown/freeze_markdown一致。CLI创建器只创建3份MD，没有PLC源或测试JSON。运行证据例外明确，未成为并行作者源。 |
| 4名独立Agent | skill单列4个不同独立上下文；主Agent不计数，不传完整主历史或预设结论；额度不足分批且不能一人换角色凑数；失败不判PASS。AGENTS与README同义，无需将流程复核误称CLI已自动执行。 |
| 每客户独立目录、最终目录和ZIP | 默认project/<项目名>/、指定外部目录、仓库内仅project/、拒绝覆盖旧项目/交付版本均明确；CLI参数和create_project/package_delivery一致。最终delivery/<版本>/及项目内ZIP、清单、显式成果选择规则齐全。 |
| 工具仓库与客户材料分离 | skill/AGENTS/README都将客户需求、程序、资料、测试、证据、交付归客户目录；src/tests/docs/skills/private禁止作为新客户目录；.gitignore忽略project内容并保留project/README.md。未将历史兼容JSON要求转嫁给新项目。 |

## 真实执行与限制

1. 读取src/plcweave/__main__.py、projects.py、markdown_suite.py，核对命令和格式实现。CLI实际--help列出init/freeze/package/simulate/preflight/hil，及--directory/--version/--file，与技能命令一致。
2. 将reference的完整markdown示例抽出，使用真实parse_markdown在内存中解析：DOC_SAMPLE_PARSE_PASS。核对scan_ms=10、M0预期=0、需求引用R01/R02。
3. 对同一样例构造4种独立无效变体：未知表列、错误priority、非扫描整数倍时长、未watch的断言设备；真实解析器全部ValueError拒绝：NEGATIVE_VARIANTS_REJECTED=4。
4. 新tools/plcweave.ps1实际--help成功，入口自动选本仓.venv并设置src和UTF8；环境恢复代码在finally。早先文档未注明源码环境的可执行性问题已由最终入口修正。
5. 全局优先修订链接存在；其PLC-MD-First-Workflow.md与仓库skill去除frontmatter后的内容完全相同，GLOBAL_WORKFLOW_MATCH=True；其相对链接references/markdown-cases.md存在，且与仓库reference字节完全一致，GLOBAL_REFERENCE_MATCH=True。后文旧JSON及旧目录被顶层新修订明确标为历史兼容。
6. 本人尝试test_markdown_projects.py时，默认系统Python无pytest；本仓.venv需PYTHONPATH=src；设定后11项在pytest默认临时目录setup即被sandbox拒绝，未执行用例主体。未把这次环境错误称作程序FAIL或回归PASS，也未额外建临时目录。上列文档解析与CLI检查为本人实际完成。未借用主Agent所报全仓测试数量作为独立执行证据。
7. Hindsight检索成功，仅作历史背景。ZERO实时入口因sandbox拒绝读取其私有凭据文件而离线；没有查看凭据、启动服务或用旧记忆冒充实时状态。

## 最终文档澄清复查

- 时间：2026-10-22T15:22:40.329020+00:00
- AGENTS的CLI列表现完整列出init/freeze/package/simulate/preflight/hil，与此前实际help及__main__.py一致。
- skill明确MANIFEST.md是随包哈希清单，不是客户编辑源；MD/HTML编辑源留项目文档目录，二者职责清晰，与package_delivery生成MANIFEST.md的实际行为一致。
- 全局SOP与仓库skill正文再次比较一致；下表哈希已更新。CLI及相关工具代码哈希无变化，沿用前次实际检查，不重复执行已测项目。
- 结论仍为PASS；无新增阻断问题。本次仅更新本报告，未触及实现、客户材料、硬件或冻结内容。

## 输入版本 SHA256

| 文件 | SHA256 |
| --- | --- |
| F:\000-HBDTECH-Neo\103-plcweave\skills\plc-program-development\SKILL.md | 7901084fa4996b9d1a8597bf2783b4d096c873e115bf3d7a49f691e8bfe4df3c |
| F:\000-HBDTECH-Neo\103-plcweave\skills\plc-program-development\references\markdown-cases.md | b67494703545703d3aa36823ab019063f2138312b7aa19ea90fa1d10ee6f0b2c |
| F:\000-HBDTECH-Neo\103-plcweave\AGENTS.md | 8e173bdc7187cc79164f76e23c2eb601f621697ca21aebc9829c06f894aa6a62 |
| F:\000-HBDTECH-Neo\103-plcweave\README.md | 498e53329ca1715a5b3387aad5d830809e7013980c1bf8f4255761a936b12df6 |
| F:\000-HBDTECH-Neo\103-plcweave\tools\plcweave.ps1 | 46199f744bfae2ec9733ab926e11181c1764e51171af63bd6834c686228c0c4e |
| F:\000-HBDTECH-Neo\103-plcweave\src\plcweave\__main__.py | 3e78ab526dc4169204c0b4b25f3a7c738afd46708500a218413769b4a2fa5409 |
| F:\000-HBDTECH-Neo\103-plcweave\src\plcweave\markdown_suite.py | 48d8fef550af86b5f2dd1330dd651c963ebd07c781b5b3c479797649419faa7e |
| F:\000-HBDTECH-Neo\103-plcweave\src\plcweave\projects.py | a10133a1a9a3c47db4415717fe4d8cb27f04506dd3f10066f74ecea3f3e9c863 |
| C:\Users\MasterNeo\.agents\skills\plc-program-development\SKILL.md | 1888bd34d44a4bf27fb046b526103c3bd0131c55a5133237e68befffd3632413 |
| C:\Users\MasterNeo\.agents\skills\plc-program-development\resources\sop\PLC-MD-First-Workflow.md | c979e375cca607125a91613fad95d6b522e06e603f20dc664a1fc0bd727ce39d |
| C:\Users\MasterNeo\.agents\skills\plc-program-development\resources\sop\references\markdown-cases.md | b67494703545703d3aa36823ab019063f2138312b7aa19ea90fa1d10ee6f0b2c |

## 结束与cleanup

完成技能/入口一致性复核，未修改实现、客户文件或冻结预期。没有打开串口、GUI、网络监听、设备连接或后台进程；所有前台命令已退出。解析样例与变体只驻内存，临时PYTHONPATH在finally恢复；pytest缓存关闭、Python字节码写入关闭。未创建需要删除的测试目录，没有全局清理用户资源。报告存入logs/并按仓库30天日志规则保留。
