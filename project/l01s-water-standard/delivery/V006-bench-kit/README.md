# V006 台架套件（L01S Water Standard）

本包对应 **程序版本字 D300=6 / 版次 31 / 套件字 6**，源哈希
`7eee2d2878b4508fee1169297a9a8f8df0d5b98e091a4e18cb1d1d33fc96aa09`。

> ⚠️ **作废旧包**：`delivery/V006-n1c-bench-kit/`（同日早先的 N1C 草稿，命令块仍 16 字、
> 不含唤醒/超压改动）**已作废，请勿烧录**。以本包为准。

## 本次改动一览

| 项 | V005 | V006 |
|---|---|---|
| 唤醒压力首扫（D326） | floor(保存SV×85%) = 51（5.1 bar） | **固定 40（4.0 bar）** |
| 最大压力保护 | 无 | **D336 设定（默认 80 = 8.0 bar），D100 超限即封锁输出并置 D307 bit7；回落到上限−0.5 bar 自动恢复** |
| 状态块 D316 | 保留恒 0 | 最大压力生效值镜像（0.1 bar） |
| 状态位图 D307 | bit0–bit5 | +bit6 PV 卡满量程诊断（N1C）+**bit7 超压封锁** |
| 命令块 | D320–D335（16 字） | **D320–D336（17 字）** |
| 程序/套件字 | D300=5、D304=5 | **D300=6、D304=6** |

## 烧录步骤

1. GX Works 打开工程，导入 `Program/COMMENT.csv` 与 `Program/MAIN.csv`
   （或按 `Program/Instruction-List-Paste.txt` 粘贴 310 条指令）。
2. **确认工程无编译错误后**下载到 PLC，PLC 置 RUN。
3. 只读核对身份：D300=6、D301=31、D304=6、D302/D303 = -7313/-11960；
   D305 心跳应持续变化。
4. 把烧录时间/操作者/软件版本记入项目 `manual_download.json`（V006 尚未登记，需你确认后补）。

## 烧录后的台架验证（手动，不用脚本）

> 台架界面：`python -m plcweave.bench`，右上 Language 选 English/中文，客户寄存器表里添加以下监控：
> D326、D336（可写）、D307、D308、D316（只读）。

1. **上电默认值**：D326=40（4.0 bar）、D336=80（8.0 bar）、D316=80；D307 无 bit7。
2. **超压封锁**：
   - 写 D322=1（测试注入）、D323=1（物理路由使能）、D320=1（启动）；
   - 写 D330 把 D308 推到 **8.1 bar 以上**（D330≈2025）；
   - 期望：D311=0、D312=0、Y0 灭、D307 bit7 置位（值 ≥128）。
3. **自动恢复**：
   - 把 D330 回落到 **7.4 bar 以下**（D330≈1860）；
   - 期望：D307 bit7 清除，频率从 2000（20 Hz）地板重新爬升。
4. **钳位**：写 D336=0 → D316 变 10（1.0 bar）；写 D336=200 → D316 变 160（16.0 bar）。
5. **回归**：启动/停止、休眠/唤醒、PI 调压与 V005 行为一致（唤醒门槛改为 4.0 bar）。

## 兼容性提醒

- **命令块必须写满 17 字**。若 HMI/SCADA 仍按 16 字写，D336 会保持 0 → 被钳位成 1.0 bar，
  压力一超过 1 bar 就会封锁输出。上位机请同步 `Doc/registers.md`。
- 超压判定用实际压力 D100（0.1 bar），**严格大于**上限才触发；恢复阈值为上限 −0.5 bar。
- 报警只有状态位（D307 bit7）+ 界面提示，不占用 Y1 等物理输出点。

## 本包内容

```
Program/MAIN.csv, COMMENT.csv, Instruction-List-Paste.txt   烧录件（310 条）
Runner/run_hil_v3.py            台架 HIL 运行器（37 字读 / 17 字写）
Runner/verify_v006_behavior.py  本地逐扫描行为验证脚本
Doc/registers.md                批量接口表（V006）
Doc/simulation-behavior.json    逐扫描行为证据（22 项 PASS）
source.fxil / build_identity.json / requirements-V006.md / s1-revision-V006.md
MANIFEST.md                     文件哈希清单
```

## 验证状态

- 本地指令级仿真：22 项行为检查 PASS（`Doc/simulation-behavior.json`）。
- 静态检查：编译 0 error；7 条多次写警告（含 V005 既有 6 条）、3 条系统继电器 info。
- **未验证**：GX Works 导入/编译、FX3U 实机运行、HMI 联调；V005 的冻结用例（STD-005）
  只对 V005 有效，**请勿对 V006 运行**，第二阶段将按 STD-006 重写。
