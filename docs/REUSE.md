# 复用计划与边界

总项目统一工作流、数据规范、安装入口和证据；不平行重写已有执行核。

| 来源 | 计划复用 | 本次导入 |
|---|---|---|
| 本地102-plc-s2-engine | gxwlib的FX3U扩展、黄金用例和构建经验 | 无代码导入 |
| 本地101-gxworks-agent | 厂家GUI通路探索与错误诊断 | 无代码导入 |
| 本地88-iec61131-plc/PLC技能 | FX生成、交付格式和S0–S7工作流 | 仅确认过的蓝图文档 |
| 本地89-l01s-daq-station/20-modbus-hc | 协议profile和采样设计经验 | 无代码导入 |
| monozukuri-ai/gxwlib | Rust执行基础（MIT，另有内部第三方声明） | 未引入 |
| Arienax/gxworks-agent | 贡献者自有指令事实与适配参考（Apache-2.0范围内） | 未引入 |

每次导入固定commit、文件哈希、许可及修改范围。禁止仅凭仓库顶层许可证覆盖嵌套许可。
