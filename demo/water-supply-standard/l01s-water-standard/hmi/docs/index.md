# 画面清单 — l01s-water-standard HMI（V005 批量接口）

| 画面 | 截图 | 原型页 | screens 文档 |
|---|---|---|---|
| S1 主画面 · 运行态 | [overview.png](assets/screenshots/overview.png) | [overview.html](../prototype/pages/overview.html) | [screens/overview.md](screens/overview.md) |
| S1 主画面 · 休眠态 | [overview-sleep.png](assets/screenshots/overview-sleep.png) | [overview-sleep.html](../prototype/pages/overview-sleep.html) | 同上 |
| S2 参数设置（工程师） | [params.png](assets/screenshots/params.png) | [params.html](../prototype/pages/params.html) | [screens/params.md](screens/params.md) |
| S3 诊断与身份 | [diagnostics.png](assets/screenshots/diagnostics.png) | [diagnostics.html](../prototype/pages/diagnostics.html) | [screens/diagnostics.md](screens/diagnostics.md) |
| 合成预览 | [HMI-PREVIEW-V005.png](assets/screenshots/HMI-PREVIEW-V005.png) | [contact-sheet.html](../prototype/pages/contact-sheet.html) | — |

## 再生成命令

```bash
bash hmi/prototype/scripts/screenshot.sh   # 在项目根执行；Edge 无头 → docs/assets/screenshots/*.png
```

## 状态与 backlog

- 原型为静态 mock（800×480，TK8070S 级）；目标硬件与组态工具待客户确认。
- 已出图场景：运行态、休眠态。待出图：重启抑制（M12）、身份不一致黄条（PRD §3/§4 已定义）。
- 数据源红线：绑定地址全部来自 V005 `source.fxil` #comments + `build_identity.json`（见 `../params.md` 表头）。
- `../registers.md` 的 V002 历史表不含 V005 批量接口段（D300–D335），HMI 绑定以 `../params.md` 为准；权威表 `../../Doc/HMI-register-map.md` 的 V005 段待下次程序资料更新时补齐。
