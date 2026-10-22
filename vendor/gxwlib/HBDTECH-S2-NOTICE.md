# 第三方成果清单与许可告知（THIRD_PARTY NOTICES）

本文是根仓 [`NOTICE`](NOTICE) 的完整清单版。许可要求：分发时保留各部分许可文本与归属，
修改处标明（Apache-2.0 §4），未修改内容不得伪称本仓原创。

## 1. 本仓原创部分（Apache-2.0，Copyright 2026 HBDTECH）

根仓 `LICENSE`。范围：`golden/`、`tests/`、`tools/`、`docs/`（除第三方文件）、
`assets/instruction-facts/SOURCES.md`、README/构建文档。
黄金用例中的指令行为断言（双线圈、定时器基准等）是技术事实的独立实现与描述，
非手册文字转录；用例 notes 标注了对应手册参考。

## 2. gxwlib vendored 源码树（`vendor/gxwlib/`，MIT）

| 项 | 值 |
| --- | --- |
| 上游 | https://github.com/monozukuri-ai/gxwlib ，commit `1e9a8d7542665e5015041d361e4bb86d7650714f` |
| 许可 | MIT，Copyright (c) 2026 neka-nat —— 见 `vendor/gxwlib/LICENSE`（原样保留） |
| 本地修改（HBDTECH，fx3u profile 扩展） | `crates/gxw-core/src/ir.rs`、`simulation/{compile,memory,scan,trace}.rs`、`ladder/mod.rs`、`crates/gxw-core/tests/{analysis,instructions,simulation}.rs`、`crates/gxw-python/src/simulation.rs`（扩展提交，原 vendor 内 commit `b5f86cd` 的内容已随源码并入本仓；修改均带 `HBDTECH S2 extension` 注释标记） |
| 未修改保留 | 上游 `LICENSE`、`LICENSES/`（含 50 项依赖声明与 `inventory.json`）、`tests/fixtures/`（含第三方样例）、`docs/`、`scripts/` 原样提交 |

## 3. gxwlib 内部源自 gxworks-agent 的改编代码

`vendor/gxwlib/crates/gxw-core/src/structured/*` 声明改编自 gxworks-agent，
Apache-2.0。义务文件：`vendor/gxwlib/LICENSES/gxworks-agent.txt`（上游随附，原样保留）。
本仓未修改这些文件。

## 4. 指令事实 JSON（`assets/instruction-facts/*.json`，Apache-2.0）

来源、逐文件 SHA-256、许可依据与边界：见
[`assets/instruction-facts/SOURCES.md`](assets/instruction-facts/SOURCES.md)。
来源基准 commit `0212ff03ae9655d5caf72b6eef687cac3ca9890d`，文件未修改；
上游许可三件套副本在 `assets/instruction-facts/upstream-license/`。

## 5. 第三方测试样例（`vendor/gxwlib/tests/fixtures/third_party/`）

ladder_converter 的 GXW/CSV 样例：来源记录（provenance）与 ITO SOFT DESIGN Inc. 的
MIT 许可随上游 `tests/fixtures/README.md` 与相关目录原样保留，分发时一并到达用户。

## 6. Rust / Python 依赖

- 构建/运行时：gxwlib 的 Rust 依赖清单与许可见 `vendor/gxwlib/LICENSES/inventory.json`
  （含 MIT、Apache-2.0 双许可、Unicode-3.0、LLVM 例外等 50 项）；Python 侧 gxwlib
  无运行时依赖（见其 pyproject）。
- 开发/测试（本仓 `requirements-dev.txt`）：pytest（MIT）、PyYAML（MIT 项目许可）。
  完整依赖树许可随 `pip install` 元数据到达；本清单覆盖直接依赖，未来若发布二进制
  包（wheel/冻结发行）需按当期依赖树重新审计。

## 7. 明确不随本仓分发的外部软件

MELSOFT / GX Works2 / GX Simulator2（三菱电机商业软件）、厂家手册与 SDK、
gxworks-agent 的 130MB 知识数据库（仅存在于其发布包，非源码仓内容）。
发布源码不包含 exe/dll/pyd 等可执行库、厂家手册 PDF 或 SQLite 知识库；
保留4份已说明来源的 `.gxw` 测试fixture（自生成与带MIT来源的样例），见第5节及fixture说明。
