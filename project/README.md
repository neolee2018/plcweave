# 客户项目容器

本目录存放客户项目，默认每个客户案例新建独立子目录。使用 `tools/plcweave.ps1 init <项目名>`；用户指定外部目录则使用 `--directory`。
双程序客户定制使用 `tools/plcweave.ps1 workflow init <项目名>`，另建design.md草稿；完整两阶段步骤见[工作流参考](../skills/plc-program-development/references/two-phase-workflow.md)。冻结MD历史原文在baseline/s1，构建输入快照和双程序在build/<版本>，需求修订在revisions/<版本>，均留在本客户项目内。
仓库首次演示用 `tools/plcweave.ps1 demo start <项目名>` 创建（流程见 `demo/START-HERE.md`），不要手工把 `demo/scenario` 复制进已有客户项目。

客户需求、测试、PLC程序、资料、证据、复核和交付全部留在相应项目内。公共Git仅跟踪本说明，其他客户内容默认忽略；可在项目中使用独立私有版本库。

```text
project/
  客户项目/
    requirements.md
    test_cases.md
    s1-freeze.md             # 用例完成后冻结
    source.fxil             # 冻结之后再编程
    Doc/
    reviews/节点/
    evidence/
    delivery/版本/          # 最终交付文件夹
    delivery/项目-版本.zip
```
