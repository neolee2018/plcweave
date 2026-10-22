# PLCWeave · 控程工坊

**测试驱动的开源 PLC 开发工具链，连接 AI 编程、本地仿真、厂家验证与硬件在环测试。**

An open-source, test-driven PLC engineering toolkit connecting AI-assisted
programming, simulation, vendor validation, and hardware-in-the-loop testing.

状态：项目骨架与方案已建立。执行引擎、厂家适配器及HIL正在规划整合；本仓目前没有可运行的PLC编译或仿真命令，也不宣称已通过厂家或硬件验证。

## 工作流程

S0 需求/硬件/接口冻结 → S1 独立冻结测试 → S2 程序生成/静态检查/指令仿真 →
S3 全轨迹验证 → S4 候选包 → S5 厂家编译及适用仿真 → S6 台架/Modbus HIL → S7 归因、验收与经验沉淀。

- 程序失败：返回S2，保持测试预期独立；测试基础设施错误先修工具。
- 验证状态分开记录：STATIC_PASS、SIM_PASS、GX_CHECK_PASS、HARDWARE_PASS。
- 本地核心优先FX3U/L01S明确支持的子集；品牌适配逐步扩展。

完整方案：[流程与工具链蓝图](docs/BLUEPRINT.md)。实施顺序：[ROADMAP](docs/ROADMAP.md)。

## 技术路线与范围

- Python：规格、测试、轨迹比较、CLI编排、报告和设备适配。
- Rust/gxwlib：计划复用已有FX3U扫描执行核扩展，保留上游许可与来源。
- JSON/YAML与Schema：统一需求、机型、用例、轨迹和验证报告。
- pytest/Rust测试：指令语义、故障反例与集成回归。
- GX Works2/GX Simulator2：用户自行安装授权的外部厂家验证环境。
- Modbus：计划先只读采集，再在隔离测试台开放指定测试输入。

当前没有监听服务或端口；没有Web界面。未来引入服务时先登记端口。
不分发厂商软件、SDK、授权文件或手册；私有客户程序与运行配置不进入公共仓库。

## 当前目录

```text
src/plcweave/      包命名空间；当前仅版本元数据
docs/BLUEPRINT.md  S0–S7、工具链、架构及验证边界
docs/ROADMAP.md    分阶段整合计划
docs/REUSE.md      上游组件与复用边界
logs/             任务资源日志（本机保留，Git忽略）
```

## 许可

本仓原创部分采用 [Apache-2.0](LICENSE)，归属见 [NOTICE](NOTICE)。
第三方组件遵循各自许可，清单见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
本次初始化只引入自有方案及包骨架，尚未拷入上游代码或事实数据。
本项目与三菱电机无隶属或认证关系。
