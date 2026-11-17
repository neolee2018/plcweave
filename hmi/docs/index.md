# hmi/docs — 画面文档索引

## 画面清单

| 画面 ID | 名称 | 文档 | 截图 |
| --- | --- | --- | --- |
| S01 | 主界面（连接/四象限/操作栏/日志/客户寄存器） | [screens/main.md](screens/main.md) | [assets/screenshots/](assets/screenshots/) |
| S01-D | 调试记录 / 记录详情（对话框） | 见 screens/main.md 底部变体 | records.png |
| S01-S | 版本与接口设置（对话框） | 见 screens/main.md | （随主界面截图更新） |
| S01-T | Python 脚本运行 / 完成确认 / 手动继续 | 见 screens/main.md | main-script-running.png / script-complete.png / main-script-manual.png |

## 截图再生成命令

```bash
.venv/Scripts/python.exe hmi/prototype/scripts/screenshot.py
```

输出到 `assets/screenshots/`。场景包括未连接、已连接、仿真中、操作日志、硬件诊断、客户寄存器读回、调试记录、脚本执行、原生完成弹窗与确认后手动继续。脚本按应用自身的启动尺寸抓取演示窗口。[截图清单](screens/main.md#截图)

## backlog（后续迭代候选）

- 最小窗口 1024×768 的 DPI 复核。基线在 125% 与 150% 曾出现顶栏或底栏裁切，目前截图验收覆盖 1280×800。
- 实机联调后补充：过期/断线变体截图、结束未确认变体截图。
- 记录详情对话框独立截图（S01-D 拆分）。

## 配套工具页补充（2026-11-06）

- [DVP 转换提示词](screens/dvp-prompt.md)：[离线页面](../prototype/dvp-prompt.html)，从项目说明进入。
- 重新生成页面：仓库根目录执行 `python tools/build_dvp_prompt_page.py`。
- 页面变更后以本地文件方式核验复制成功、降级和手动复制提示，并更新页面说明中引用的截图。

