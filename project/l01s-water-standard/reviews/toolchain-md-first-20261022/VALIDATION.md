# MD-first / project隔离改动验收

- 新验收先RED：新增模块缺失；之后MD身份缺失的独立反例先RED再修。
- 最终本仓回归：97 passed in 0.60s，0 skipped。
- 命令：PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q tests --basetemp=local/pytest-md-all --tb=short。
- 仓库技能、本机已安装技能：quick_validate均PASS（Python -X utf8）。
- 4名不同、独立上下文复核：review_md_contract、review_projects、review_toolchain、review_skill_workflow均最终PASS；首次额度失败不计作复核。
- 初版项目仅requirements.md/test_cases.md/README.md；冻结仅s1-freeze.md；不生成需求/测试JSON。
- 迁移时830原有文件逐个字节哈希一致。后续活动run_hil02.py历史路径兼容及正常pycache改变已声明；独立复核518项冻结/历史关键材料全匹配，0缺失。
- 迁移后的历史load_inputs只读检查通过（28补充程序/55原用例）。没有重跑PLC或宣称新硬件通过。
- 正式交付文件夹：project/l01s-water-standard/delivery/V002-final；4件套+MANIFEST.md。
- ZIP：l01s-water-standard-V002-final.zip；SHA256：fe629cab4a3a83ee0efed3062b0f8cdb7cd019662ba49427120b49f771807e5c。目录/ZIP/原交付4文件哈希一致，CRC通过。
- 全局旧技能备份：local/skill-backup/20261022。旧SOP明示新规范优先，历史JSON仅兼容。
- 真实串口、PLC动作、GUI：本轮均无。

4份同目录报告包含实际检查、原问题、修复复核和输入哈希。未把根代理自身测试代替4名复核者。
