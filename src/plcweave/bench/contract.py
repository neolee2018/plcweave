"""输入接口档案：注入/会话寄存器白名单的加载与校验。

PRD §8.2 边界：仿真输入/会话/结束请求只允许写“已核实接口档案”中的专用 D
白名单；输出与版本只读地址与本档案物理隔离；档案不同方向使用独立寄存器。

默认档案 DEFAULT_DEMO_PROFILE 的地址属于虚拟演示设备。实机需要用户区地址、
已确认的目标构建和配套程序。回环演示后端使用进程内传输。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

# L01S 用户程序 D 区上限（params.md：版本地址 D0–D8511）。
D_MAX = 8511
USER_D_MAX = 7999

# 硬件只读观察点表（PRD §7/§8.2，零基协议地址）。
Y_COIL_BASE = 0x3300        # FC01, Y0–Y7（八进制编号，连续 8 点）
X_INPUT_BASE = 0x3400       # FC02, X0–X7 硬件原值
AD_HW_BASE = 8030           # FC03, D8030–D8033 硬件模拟输入
DA_HW_BASE = 8050           # FC03, D8050/D8051 第1/2路模拟输出

# 已知不可占用的现有工具寄存器（hil.py 白名单等）；仅作重叠提示，不构成完整占用表。
RESERVED_KNOWN = {102, 154, 190, 191, 192, 193, 194, 196, 197, 198, 200, 201, 202, 261, 1056,
                  8030, 8031, 8032, 8033, 8050, 8051, 8052, 8058}


@dataclass(frozen=True)
class CustomerRegister:
    address: int
    minimum: int
    maximum: int
    signed: bool = False

    def __post_init__(self) -> None:
        if type(self.address) is not int or not 0 <= self.address <= USER_D_MAX:
            raise ValueError("客户可写地址须在 D0–D7999")
        if type(self.signed) is not bool:
            raise ValueError("signed 必须为布尔值")
        low, high = (-32768, 32767) if self.signed else (0, 65535)
        if (type(self.minimum) is not int or type(self.maximum) is not int
                or not low <= self.minimum <= self.maximum <= high):
            raise ValueError(f"D{self.address} 写入范围无效")

    def decode(self, raw: int) -> int:
        return raw - 65536 if self.signed and raw >= 32768 else raw


@dataclass(frozen=True)
class InterfaceProfile:
    """输入注入/会话接口档案。所有地址为零基 D 寄存器编号。"""

    name: str
    status: str                       # proposal | confirmed
    confirmed: bool                   # 用户已核对目标程序后置 True
    note: str = ""
    x_command: tuple[int, ...] = ()   # 8 个 X 暂存（PC→PLC）
    ad_command: tuple[int, ...] = ()  # 4 个 AD 暂存 raw（PC→PLC）
    x_effective: tuple[int, ...] = ()   # 8 个 X 生效镜像（PLC→PC）
    ad_effective: tuple[int, ...] = ()  # 4 个 AD 生效镜像 raw（PLC→PC）
    session_request: int | None = None    # PC→PLC 会话申请（写非零递增值）
    session_confirm: int | None = None    # PLC→PC 会话确认（回显申请值）
    session_state: int | None = None      # PLC→PC 会话状态 0空闲/1活动/2结束中
    host_heartbeat: int | None = None     # PC→PLC 心跳计数
    plc_liveness: int | None = None       # PLC→PC 存活计数
    request_seq: int | None = None        # PC→PLC 组提交序号
    content_checksum: int | None = None   # PC→PLC 内容校验和
    ack_seq: int | None = None            # PLC→PC 已消费序号
    end_request: int | None = None        # PC→PLC 结束请求
    end_confirm: int | None = None        # PLC→PC 结束确认
    build_identity: tuple[tuple[int, int], ...] = ()
    customer_registers: tuple[CustomerRegister, ...] = ()

    # ---- 派生集合 ------------------------------------------------------
    def write_regs(self) -> tuple[int, ...]:
        """PC 可写地址全集（白名单）。"""
        return (*self.x_command, *self.ad_command,
                self.session_request, self.host_heartbeat,
                self.request_seq, self.content_checksum, self.end_request)

    def read_regs(self) -> tuple[int, ...]:
        """PLC→PC 档案读取地址全集。"""
        return (*self.x_effective, *self.ad_effective,
                self.session_confirm, self.session_state, self.plc_liveness,
                self.ack_seq, self.end_confirm)

    def is_complete(self) -> bool:
        """接口要素是否齐全（PRD §8.2 最低集合）。"""
        return all((
            len(self.x_command) == 8, len(self.ad_command) == 4,
            len(self.x_effective) == 8, len(self.ad_effective) == 4,
            None not in (self.session_request, self.session_confirm,
                         self.session_state, self.host_heartbeat,
                         self.plc_liveness, self.request_seq,
                         self.content_checksum, self.ack_seq,
                         self.end_request, self.end_confirm),
        ))

    def validate(self) -> list[str]:
        """返回错误列表；空列表表示档案可用于校验流程。"""
        errors: list[str] = []
        if self.status not in ("proposal", "confirmed"):
            errors.append(f"档案状态非法: {self.status!r}")
        if type(self.confirmed) is not bool or self.confirmed != (self.status == "confirmed"):
            errors.append("confirmed 须为布尔值且与 status 一致")
        try:
            _check_address_range(self)
        except ValueError as exc:
            return [*errors, str(exc)]
        for label, regs, size in (("X暂存", self.x_command, 8),
                                  ("AD暂存", self.ad_command, 4),
                                  ("X生效镜像", self.x_effective, 8),
                                  ("AD生效镜像", self.ad_effective, 4)):
            if len(regs) != size:
                errors.append(f"{label}需要 {size} 个地址，实际 {len(regs)}")
        for label, regs in (("X暂存", self.x_command), ("AD暂存", self.ad_command),
                            ("X生效镜像", self.x_effective), ("AD生效镜像", self.ad_effective)):
            if regs and list(regs) != list(range(regs[0], regs[0] + len(regs))):
                errors.append(f"{label}地址必须连续（便于整组读写）")
        for label, value in (("会话申请", self.session_request),
                             ("会话确认", self.session_confirm),
                             ("会话状态", self.session_state),
                             ("主机心跳", self.host_heartbeat),
                             ("PLC存活", self.plc_liveness),
                             ("提交序号", self.request_seq),
                             ("内容校验", self.content_checksum),
                             ("消费序号", self.ack_seq),
                             ("结束请求", self.end_request),
                             ("结束确认", self.end_confirm)):
            if value is None:
                errors.append(f"{label}地址未分配")
        errors.extend(self._overlap_errors())
        used = set((*self.read_regs(), *self.write_regs()))
        identity = set()
        for address, expected in self.build_identity:
            if (type(address) is not int or not 0 <= address <= USER_D_MAX
                    or type(expected) is not int or not 0 <= expected <= 65535
                    or address in used or address in identity):
                errors.append(f"构建标识 D{address} 地址或预期值无效")
            identity.add(address)
        customers = set()
        for register in self.customer_registers:
            if register.address in used | identity | customers:
                errors.append(f"客户寄存器 D{register.address} 与档案字段重叠")
            customers.add(register.address)
        return errors

    def _overlap_errors(self) -> list[str]:
        seen: dict[int, str] = {}
        errors: list[str] = []
        for label, regs in (("X暂存", self.x_command), ("AD暂存", self.ad_command),
                            ("X生效镜像", self.x_effective), ("AD生效镜像", self.ad_effective)):
            for address in regs:
                _register_owner(seen, errors, address, label)
        for label, value in (("会话申请", self.session_request),
                             ("会话确认", self.session_confirm),
                             ("会话状态", self.session_state),
                             ("主机心跳", self.host_heartbeat),
                             ("PLC存活", self.plc_liveness),
                             ("提交序号", self.request_seq),
                             ("内容校验", self.content_checksum),
                             ("消费序号", self.ack_seq),
                             ("结束请求", self.end_request),
                             ("结束确认", self.end_confirm)):
            if value is not None:
                _register_owner(seen, errors, value, label)
        return errors

    def check_write_allowed(self, address: int) -> None:
        """写白名单闸门：越权即拒绝（PRD：手改配置也不能越权写）。"""
        if address not in self.write_regs():
            raise PermissionError(f"地址 D{address} 不在接口档案写白名单内，拒绝写入")

    def digest(self) -> str:
        """档案内容哈希，用于会话摘要绑定（PRD §9.2）。"""
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ---- 序列化 --------------------------------------------------------
    def to_dict(self) -> dict:
        data = {
            "name": self.name, "status": self.status, "confirmed": self.confirmed,
            "note": self.note,
            "x_command": list(self.x_command), "ad_command": list(self.ad_command),
            "x_effective": list(self.x_effective), "ad_effective": list(self.ad_effective),
            "session_request": self.session_request, "session_confirm": self.session_confirm,
            "session_state": self.session_state, "host_heartbeat": self.host_heartbeat,
            "plc_liveness": self.plc_liveness, "request_seq": self.request_seq,
            "content_checksum": self.content_checksum, "ack_seq": self.ack_seq,
            "end_request": self.end_request, "end_confirm": self.end_confirm,
        }
        if self.build_identity:
            data["build_identity"] = {str(address): value for address, value in self.build_identity}
        if self.customer_registers:
            data["customer_registers"] = [vars(register).copy() for register in self.customer_registers]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "InterfaceProfile":
        if not isinstance(data, dict):
            raise ValueError("接口档案必须是 JSON 对象")
        known = {"name", "status", "confirmed", "note", "x_command", "ad_command",
                 "x_effective", "ad_effective", "session_request", "session_confirm",
                 "session_state", "host_heartbeat", "plc_liveness", "request_seq",
                 "content_checksum", "ack_seq", "end_request", "end_confirm",
                 "build_identity", "customer_registers"}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"接口档案存在未知字段: {sorted(unknown)}")
        for field_name in ("name", "status"):
            if not isinstance(data.get(field_name), str) or not data[field_name]:
                raise ValueError(f"档案字段 {field_name} 必须为非空字符串")
        ints = {}
        for key in ("x_command", "ad_command", "x_effective", "ad_effective"):
            value = data.get(key, [])
            if not isinstance(value, list) or any(type(v) is not int for v in value):
                raise ValueError(f"档案字段 {key} 必须为整数列表")
            ints[key] = tuple(value)
        scalars = {}
        for key in ("session_request", "session_confirm", "session_state",
                    "host_heartbeat", "plc_liveness", "request_seq",
                    "content_checksum", "ack_seq", "end_request", "end_confirm"):
            value = data.get(key)
            if value is not None and type(value) is not int:
                raise ValueError(f"档案字段 {key} 必须为整数或 null")
            scalars[key] = value
        identity = data.get("build_identity", {})
        if not isinstance(identity, dict) or any(
                not isinstance(key, str) or not key.isascii() or not key.isdecimal()
                for key in identity):
            raise ValueError("build_identity 须为零基 D 编号和预期整数值的对象")
        registers = data.get("customer_registers", [])
        if not isinstance(registers, list):
            raise ValueError("customer_registers 须为列表")
        try:
            customers = tuple(CustomerRegister(**register) for register in registers)
        except TypeError as exc:
            raise ValueError("客户寄存器须填写 address、minimum、maximum，可选 signed") from exc
        confirmed = data.get("confirmed", False)
        if type(confirmed) is not bool:
            raise ValueError("confirmed 必须为布尔值")
        profile = cls(
            name=data["name"], status=data["status"],
            confirmed=confirmed,
            note=str(data.get("note", "")),
            build_identity=tuple(sorted((int(key), value) for key, value in identity.items())),
            customer_registers=customers,
            **ints, **scalars,
        )
        _check_address_range(profile)
        return profile


def _register_owner(seen: dict[int, str], errors: list[str], address: int, label: str) -> None:
    if address in seen:
        errors.append(f"地址 D{address} 重复分配: {seen[address]} 与 {label}")
    else:
        seen[address] = label


def _check_address_range(profile: InterfaceProfile) -> None:
    all_regs = [value for value in (*profile.write_regs(), *profile.read_regs())
                if value is not None]
    for address in all_regs:
        if type(address) is not int or not 0 <= address <= D_MAX:
            raise ValueError(f"档案地址 D{address} 超出 D0–D{D_MAX} 范围")


def group_checksum(words) -> int:
    """8X+4AD 组提交内容的 16 位累加校验和（PC 与 PLC 共用定义）。"""
    total = 0
    for value in words:
        total += int(value) & 0xFFFF
    return total & 0xFFFF


def load_profile(path: str | Path) -> InterfaceProfile:
    """从 JSON 文件加载并校验档案；文件不存在或内容非法时抛 ValueError。"""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"无法读取接口档案 {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"接口档案不是有效 JSON: {exc}") from exc
    profile = InterfaceProfile.from_dict(data)
    errors = profile.validate()
    if errors:
        raise ValueError("接口档案校验失败: " + "; ".join(errors))
    return profile


# 默认演示档案用于虚拟设备和自动化测试。实机需另行分配用户区地址。
DEFAULT_DEMO_PROFILE = InterfaceProfile(
    name="demo-virtual-l01s",
    status="proposal",
    confirmed=False,
    note="内置虚拟 PLC 演示档案（D8100–D8143，建议分配）；实机禁止使用，须另存并核对",
    x_command=tuple(range(8110, 8118)),      # D8110–D8117 X0–X7 暂存
    ad_command=tuple(range(8118, 8122)),     # D8118–D8121 AD0–AD3 暂存 raw
    x_effective=tuple(range(8130, 8138)),    # D8130–D8137 X0–X7 生效镜像
    ad_effective=tuple(range(8140, 8144)),   # D8140–D8143 AD0–AD3 生效镜像
    session_request=8100,
    session_confirm=8101,
    session_state=8102,
    host_heartbeat=8103,
    plc_liveness=8104,
    request_seq=8105,
    content_checksum=8106,
    ack_seq=8107,
    end_request=8108,
    end_confirm=8109,
)


def validate_version_address(address: int | None) -> int | None:
    """版本寄存器地址校验：None 表示未设置；合法范围 D0–D8511。

    RESERVED_KNOWN 中的地址不在此硬性禁止——版本地址属于用户程序文档的
    只读业务寄存器（PRD §3.2），但调用方应把命中的地址作为警告展示，
    提醒用户核对程序文档后再连接。
    """
    if address is None:
        return None
    if type(address) is not int or not 0 <= address <= D_MAX:
        raise ValueError("版本寄存器必须是 D0–D8511 内的整数编号")
    return address
