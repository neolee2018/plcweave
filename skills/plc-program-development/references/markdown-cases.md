# Markdown 用例格式

需求全文写 `requirements.md`，用例全文写 `test_cases.md`。初版可先写普通文字和未完成表格；未完成用例不能冻结或执行。程序先不要创建。

普通可执行格式如下：表头和字段为固定英文标识，标题、说明和note可用中文。不使用额外JSON/YAML作者文件。

```markdown
# 测试用例

## Suite
| key | value |
| --- | --- |
| suite_version | V001 |
| scan_ms | 10 |
| watch | M0,D0 |

## Invariants
| device | expected |
| --- | --- |
| M0 | 0..1 |

## TC-001: 停止状态
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R01,R02 |
| hardware_scope | bench |

### Initial
| device | value |
| --- | --- |
| D0 | 0 |

### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | D0=0 | M0=0..1 | M0=0 | 保持两个扫描 |
```

- 每例以 `## 唯一ID: 标题` 开始，可有Metadata、Initial、Steps。
- watch为逗号分隔设备；多项赋值以分号隔开，如 `D0=1;M1=0`。空单元格用 `-`。
- 值为整数；预期可用闭区间 `0..100`。输入值和初始值不能写范围。所断言的设备必须在watch中。
- 每步duration_ms是正整数且为scan_ms的整数倍。MUST/SHOULD之外的优先级拒绝。未知栏目、重复ID、无步骤或无断言拒绝，不能默认为通过。
- Metadata支持priority、requirements、hardware_scope、injection_mode、expected_behavior_note；不支持的规则应扩展执行器并独立测试后再使用，不能写在备注里假装执行。
- 冻结命令只生成 `s1-freeze.md`，记录requirements.md和test_cases.md的原始字节哈希；不能覆盖旧冻结。执行前后再次核验。

## 复杂关系与历史导入

对于当前独立关系比较器使用的复杂结构，可在同一 `test_cases.md` 内放一个 `plcweave-suite` fenced结构块，块内沿用受支持的机器模型。它是该MD文件的一部分，执行时直接读内存，仍不生成同名JSON/YAML文件。此格式用于复杂套件/无损历史导入，不要求初版需求或用例先写成JSON。

结构块和表格不能同时定义两套可执行用例；未知schema、关系或参数必须拒绝。历史JSON文件若仍存在，则按历史模式单独读取；同一项目同时放test_cases.md和test_cases.json会因权威源歧义而阻断。历史证据冻结内容保持原样，不为“统一格式”改写。
