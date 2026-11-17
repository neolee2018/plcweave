"""PLCWeave 手动硬件在环仿真台（bench）。

模块边界：
- rtu      : 最小 Modbus RTU 编解码 + 串口/回环传输层
- contract : 输入接口档案（注入/会话寄存器白名单）加载与校验
- virtual  : 内置虚拟 PLC（演示/测试后端，完整实现接口契约）
- engine   : 会话状态机、工程换算、操作日志引擎（与 GUI 无关）
- store    : 调试记录存储、30 次轮转、ZIP 导出
- app      : tkinter 桌面界面

设计依据：hmi/PRD.md 与 hmi/params.md。
"""

from .rtu import (
    CrcMismatch,
    LoopbackTransport,
    ModbusError,
    RtuClient,
    SerialTransport,
    crc16,
)
from .contract import (
    DEFAULT_DEMO_PROFILE,
    InterfaceProfile,
    load_profile,
)

__all__ = [
    "CrcMismatch",
    "LoopbackTransport",
    "ModbusError",
    "RtuClient",
    "SerialTransport",
    "crc16",
    "DEFAULT_DEMO_PROFILE",
    "InterfaceProfile",
    "load_profile",
]
