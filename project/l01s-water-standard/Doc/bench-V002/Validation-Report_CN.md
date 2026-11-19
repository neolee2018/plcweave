# L01S 供水 PI V002 台架演示与验证报告

生成：2026-10-22T10:35:53.961599+00:00。机型：HBDTECH L01S-16M-4AD2DA（4AI/2AO）。

## 本次结论

已使用用户烧录的 V002，在空机隔离台架上由 PlatformIO 执行完整28项冻结补充程序：{'PASS': 24, 'UNVERIFIED': 4}。
PLC程序没有改版；没有已证明的程序失败。采样结果与原始事务经独立复算，ACCEPT_SCOPED_BENCH_EVIDENCE。
这是可复演的寄存器台架案例；原55项完整扫描用例的硬件结论仍为 UNVERIFIED，电气、带载水压闭环、掉电保持及单扫描瞬态也未验收。没有发布为 V1 或宣称完整 HARDWARE_PASS。

## 测试先于程序的证据

- S0先冻结需求；独立S1冻结55项MUST和10类关系断言。
- 私有Git快照 fa673fe / S1-STD-002-FROZEN 时间2026-10-22 13:51:28 +08，当时快照不含PLC源。
- 新PLC源首次创建2026-10-22 13:53:39 +08；独立S2依据冻结需求和用例编程。
- 独立S3完整解释执行176条指令、92,996个扫描，55/55用例、10类关系通过；7类语义故障变体被捕获。CLI及PlatformIO仿真入口通过。
- 本轮S6采样规则和无硬件测试也先冻结、先记录失败，再实现采样器。第一次实机run01为24PASS/4UNVERIFIED；独立复核发现积分截止采样只读两次，第二次已经30000但缺一次稳定确认。追加独立采集策略和失败测试后，改为截止时间内连续读取，仍严格要求最后两次完整到顶确认都不跨截止线。run02第一次到顶响应约50196.377ms，第二次50226.220ms跨过50200ms，因此截止断言仍UNVERIFIED，没有追逐PASS或扩大容差。run01原始报告、执行器和轨迹完整保留，最终run02重新执行全部28项。
- PLC源、原测试、预期值和所有时序容差始终未改。普通串口轮询不替代原每扫描关系验证。

## 实机范围与结果

COM5用于已授权真实STOP/RUN及身份核验；COM7为Modbus RTU，站号1，9600/8/N/1。每次写指定输入后回读确认；禁止写ADC、AO及未知映射。
已核对D196=2、D197=31、D200=28642、D201=27104、D202=2及变化心跳。该指纹用于版本关联，不能替代二进制回读。
范围覆盖初始化、保存设定值校验、压力标定、启停优先级、非法模式重启抑制、满频/积分限幅、输出使能路由、休眠/唤醒及抖动后的恢复。

| 补充程序 | 判定 |
| --- | --- |
| SUP-INIT-001 | PASS |
| SUP-INIT-002 | PASS |
| SUP-INIT-003 | PASS |
| SUP-INIT-004 | PASS |
| SUP-INIT-005 | PASS |
| SUP-INIT-006 | PASS |
| SUP-INIT-007 | PASS |
| SUP-INIT-008 | PASS |
| SUP-INIT-009 | PASS |
| SUP-INIT-010 | PASS |
| SUP-STEADY-STD-016 | PASS |
| SUP-STEADY-STD-024 | PASS |
| SUP-STEADY-STD-025 | PASS |
| SUP-STEADY-STD-048 | PASS |
| SUP-COMMAND-STD-011 | PASS |
| SUP-COMMAND-STD-012 | PASS |
| SUP-COMMAND-STD-013 | PASS |
| SUP-COMMAND-STD-014 | PASS |
| SUP-COMMAND-STD-015 | PASS |
| SUP-COMMAND-STD-019 | PASS |
| SUP-COMMAND-STD-020 | PASS |
| SUP-COMMAND-STD-021 | PASS |
| SUP-COMMAND-STD-022 | PASS |
| SUP-ZERO-SATURATION | UNVERIFIED |
| SUP-GATE-PLATEAU | PASS |
| SUP-TIMER-TWO-CYCLES | UNVERIFIED |
| SUP-TIMER-CANCEL | UNVERIFIED |
| SUP-JITTER-ACTUAL-SCHEDULE | UNVERIFIED |

计时使用保守区间，整个区间落入原容差才通过；与边界重叠保留UNVERIFIED，不扩大容差，也不据此指认程序早动作。

| 事件 | 实测区间ms | 容差ms | 判定 |
| --- | --- | --- | --- |
| SUP-ZERO-SATURATION / first-full-frequency | [40012.803, 40158.055] | min=39800, max=40200 | PASS |
| SUP-TIMER-TWO-CYCLES / sleep-1 | [4816.677, 4992.276] | min=4900, max=5100 | UNVERIFIED |
| SUP-TIMER-TWO-CYCLES / wake-1 | [2788.407, 2961.631] | min=2900, max=3100 | UNVERIFIED |
| SUP-TIMER-TWO-CYCLES / sleep-2 | [4817.035, 4991.102] | min=4900, max=5100 | UNVERIFIED |
| SUP-TIMER-TWO-CYCLES / wake-2 | [2775.309, 2948.248] | min=2900, max=3100 | UNVERIFIED |
| SUP-TIMER-CANCEL / sleep-after-cancel | [4838.573, 5010.375] | min=4900, max=5100 | UNVERIFIED |
| SUP-TIMER-CANCEL / wake-after-cancel | [2799.985, 2973.492] | min=2900, max=3100 | UNVERIFIED |

AO0的4000及AO1的0是寄存器回读，没有测量端子电压或电流。PLC没有连接传感器或执行设备，未验证真实水压。

## 复演方法

当前硬件已烧录V002，运行本仓现有工具环境，不需要再次下载或打开GX Works2。此任务未发现经过验证的L01S自动应用下载器，PlatformIO负责仿真和测试编排；upload仍明确阻断。

在案例目录的platformio.ini中，将custom_hil_output设为未存在的新编号（如run03），然后执行PlatformIO的bench目标。证据目录不可覆盖；默认目标仍是simulate。只允许在本次已确认无传感器/执行器的测试台复演。PlatformIO显示SUCCESS表示任务完成，完整硬件结论仍以报告中的UNVERIFIED和逐项状态为准。

手动寄存器演示可按顺序操作：

1. D192=1、D191=0、D193=0，确认停止和输出0。
2. D190=1、D102=60、D1056=1250（5.0bar），再D192=0、D191=1；观察M0=1。
3. D1056=1450（5.8bar）持续保持，观察M10预休眠、随后M11休眠。
4. D1056=1275（5.1bar）持续保持，观察重新唤醒。人工观察不用于精确时序验收。
5. 若演示满频，将D1056=0保持约51秒；观察D154=5000（50Hz）、D120=30000。仅在空机测试台将D193=1时，Y0=1且D8050=4000；D193改0则路由关闭。
6. 结束写D192=1、D191=0、D193=0，回读M0/M10/M11/D120/D154/Y0/D8050/D8051全部0。

四件套文件夹含MAIN.csv、COMMENT.csv和两份英文PDF；测试PDF包含完整寄存器表、原55用例和28项补充程序操作表。Doc保留可编辑HTML/Markdown，evidence保留两轮原始记录、独立复核、失败测试及冻结哈希。
压缩包是案例与证据包；自动复演依赖本仓已安装的PLCWeave环境，并非独立Windows安装器。

## 清理、限制与版本绑定

最终状态：RUN retained, original control flags restored, application stopped/output disabled/zero readback。CPU RUN，M8035/M8036/M8037恢复原值；应用停止，D193=0，输出寄存器与Y0为0。串口关闭：True；任务锁移除：True。
S5按用户不使用GX Works2的要求未执行。未声称厂家编译或导入实测通过；CSV格式检查通过和用户手工烧录是独立事实。历史上游扩大测试仍有5项旧预期差异，原记录保留，不称上游全绿。

源SHA256：`238e10886e2d8ed4e8d2d66e758a18afe4e403f6c613f306d7859796b8ec3a88`

原测试SHA256：`b8702dc680b52990c180bbdfa320a477cbc5562ef71c9bf625012d9679475106`

S6冻结计划SHA256：`d09a6298935138492fcd485831c069a29f9561f10cea1a69008916e3dbb96313`

原始run02报告SHA256：`b0282613593b85b39e9ac436c4ae898249ed9878d7f617255ddca64dee41f45c`

原始run02轨迹SHA256：`a5fefe0202757bccf8cef6702056fa8427e55664ee38bf39b20eb9093784ad1d`
