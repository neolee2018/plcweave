# 测试用例 — L01S 启停/延时输出演示

## Suite
| key | value |
| --- | --- |
| suite_version | DEMO-V001 |
| scan_ms | 10 |
| watch | M0,Y0,M8125,M8196,D100,D101,D154,D195,D196,D197,D202,D8050,D8051,D8120,D8121,D8129 |

## Invariants
| device | expected |
| --- | --- |
| M0 | 0..1 |
| Y0 | 0..1 |

## TC-001: 首扫描身份与串口镜像
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R01,R08 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0;Y0=0;D196=1;D197=41;D202=1;D8120={{D8120_SIGNED}};D8121={{STATION}};D8129=20;M8125=1;M8196=1;D8050=0;D8051=0 | 两个扫描后核对身份、串口与输出禁止 |

## TC-002: 启动自锁与停止优先
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R02,R05,R08 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D191=1 | - | M0=1;Y0=0 | 启动请求，输出仍禁止 |
| 20 | D191=0 | - | M0=1 | 请求撤销后自锁保持 |
| 20 | D192=1 | - | M0=0;Y0=0;D154=0 | 停止优先 |
| 20 | D192=0 | - | M0=0 | 停止后不自动重启 |

## TC-003: 输出使能与三秒延时
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R03,R04 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D191=1 | - | M0=1 | 启动 |
| 20 | D191=0;D193=1 | - | Y0=0 | 使能输出但延时未到 |
| 2000 | - | - | Y0=0 | 延时窗口内保持断开 |
| 2000 | - | - | Y0=1;D154=1000 | 3 s 后接通（留出 9600 轮询余量） |

## TC-004: 运行中停止立即断开输出
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R02,R05 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D191=1 | - | M0=1 | 启动 |
| 20 | D191=0;D193=1 | - | Y0=0 | 使能输出 |
| 3500 | - | - | Y0=1;D154=1000 | 延时完成（含轮询余量） |
| 20 | D192=1 | - | M0=0;Y0=0;D154=0 | 停止立即清输出 |
| 20 | D192=0 | - | M0=0 | 保持停止 |

## TC-005: 写入回声
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R06 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D194=1234 | - | D195=1234 | 一个扫描内回声 |
| 20 | D194=0 | - | D195=0 | 回声跟随清零 |

## TC-006: 运行计时与启动计数
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R07 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D194=-1234 | - | D195=-1234 | 计数器复位命令 |
| 20 | D194=0 | - | D195=0 | 释放复位 |
| 20 | D191=1 | - | M0=1 | 启动 |
| 20 | D191=0 | - | M0=1 | 自锁 |
| 2200 | - | - | D100=1..4;D101=1 | 约 2 s 运行（留出轮询余量） |
| 20 | D192=1 | - | M0=0 | 停止 |

## TC-007: 运行中撤销输出使能
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R03,R05 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D191=1 | - | M0=1 | 启动 |
| 20 | D191=0;D193=1 | - | Y0=0 | 使能输出 |
| 3500 | - | - | Y0=1;D154=1000 | 延时完成（含轮询余量） |
| 20 | D193=0 | - | M0=1;Y0=0;D154=0 | 撤销使能只关输出，不停机 |
| 20 | D192=1 | - | M0=0 | 停机 |

## TC-008: 停止后重新启动重新计时
### Metadata
| key | value |
| --- | --- |
| priority | MUST |
| requirements | R04,R05 |
| hardware_scope | bench |
### Steps
| duration_ms | write | invariant | expect | note |
| --- | --- | --- | --- | --- |
| 20 | - | - | M0=0 | 首扫描完成 |
| 20 | D191=1 | - | M0=1 | 第一次启动 |
| 20 | D191=0;D193=1 | - | Y0=0 | 使能输出 |
| 3500 | - | - | Y0=1 | 延时完成（含轮询余量） |
| 20 | D192=1 | - | M0=0;Y0=0 | 停止 |
| 20 | D192=0 | - | M0=0 | 释放停止 |
| 20 | D191=1 | - | M0=1 | 第二次启动 |
| 20 | D191=0 | - | M0=1 | 自锁 |
| 1500 | - | - | Y0=0 | 新计时未到（留出轮询余量） |
| 2500 | - | - | Y0=1 | 重新计满 3 s |
