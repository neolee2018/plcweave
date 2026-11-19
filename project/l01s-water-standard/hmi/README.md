# l01s-water-standard · HMI 资源夹

> 103-plcweave 约定（2026-11-03）：每个客户项目的 HMI 资源统一放此处，随 PLC 程序同步演进。
> 本项目为恒压供水标准版（当前程序 V005 修复版，批量接口 D300–D335）。

## 三件套状态（2026-11-11 更新）

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `PRD.md` | 前端 PRD（页面清单/旅程/交互口径/验收） | ✅ 原型级 |
| `params.md` | HMI 可视参数表（V005 批量接口子集） | ✅ 数据源=source.fxil V005 #comments |
| `registers.md` | 程序寄存器表：**V005 批量接口段**（新增）+ V002 历史表 | ✅ V005 段已登记；权威 Doc 表待同步 |
| `DESIGN_RULES.md` | 色板/组件/场景态 | ✅ |
| `prototype/pages/*.html` | 页面原型（800×480，5 页） | ✅ |
| `docs/assets/screenshots/*.png` | 交互截图（5 张，2026-11-11 渲染） | ✅ 与原型同步 |
| `docs/screens/*.md` | 逐画面绑定与交互说明 | ✅ |

## 画面

S1 主画面（运行态/休眠态）· S2 参数设置（工程师）· S3 诊断与身份。清单与 backlog 见 `docs/index.md`。

## 再生成

```bash
bash hmi/prototype/scripts/screenshot.sh   # 项目根执行
```

## 参考

- 表头范式模板：`../../../reusable/registers/TEMPLATE-HMI寄存器地址表.md`
- 工作区 HMI 全局约定：skill=`hmi-frontend`；参照实现 `82-hpc6-water-supply/hmi/`
