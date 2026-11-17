"""接口档案（contract）测试：白名单、重叠校验、确认门。"""
import json

import pytest

from plcweave.bench.contract import (
    DEFAULT_DEMO_PROFILE,
    InterfaceProfile,
    group_checksum,
    load_profile,
    validate_version_address,
)


class TestDefaultProfile:
    def test_valid_and_complete(self):
        assert DEFAULT_DEMO_PROFILE.validate() == []
        assert DEFAULT_DEMO_PROFILE.is_complete()

    def test_write_whitelist_exact(self):
        assert DEFAULT_DEMO_PROFILE.write_regs() == (
            8110, 8111, 8112, 8113, 8114, 8115, 8116, 8117,   # X 暂存
            8118, 8119, 8120, 8121,                            # AD 暂存
            8100,                                              # 会话申请
            8103,                                              # 主机心跳
            8105,                                              # 提交序号
            8106,                                              # 内容校验
            8108,                                              # 结束请求
        )

    def test_output_and_hw_addresses_outside_whitelist(self):
        # Y/X硬件/AD硬件/DA/版本案例地址都不得进入写白名单（PRD §8.2）。
        forbidden = (0x3300, 0x3400, 8030, 8050, 8051, 196, 8058)
        for address in forbidden:
            with pytest.raises(PermissionError):
                DEFAULT_DEMO_PROFILE.check_write_allowed(address)

    def test_roundtrip_dict(self):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        clone = InterfaceProfile.from_dict(data)
        assert clone == DEFAULT_DEMO_PROFILE
        assert clone.digest() == DEFAULT_DEMO_PROFILE.digest()

    def test_digest_changes_with_content(self):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        data["note"] = "changed"
        clone = InterfaceProfile.from_dict(data)
        assert clone.digest() != DEFAULT_DEMO_PROFILE.digest()


class TestProfileValidation:
    def base(self, **overrides):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        data.update(overrides)
        return InterfaceProfile.from_dict(data)

    def test_missing_register_rejected(self):
        profile = self.base(session_request=None)
        errors = profile.validate()
        assert any("会话申请" in message for message in errors)
        assert not profile.is_complete()

    def test_overlapping_addresses_rejected(self):
        profile = self.base(x_effective=list(range(8110, 8118)))  # 与 X 暂存重叠
        errors = profile.validate()
        assert any("重复分配" in message for message in errors)

    def test_non_contiguous_block_rejected(self):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        data["ad_command"] = [8118, 8119, 8121, 8122]
        profile = InterfaceProfile.from_dict(data)
        assert any("连续" in message for message in profile.validate())

    def test_address_range_enforced(self):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        data["session_request"] = 9000   # 超出 D8511
        with pytest.raises(ValueError):
            InterfaceProfile.from_dict(data)

    def test_unknown_field_rejected(self):
        data = DEFAULT_DEMO_PROFILE.to_dict()
        data["d196_secret"] = 1
        with pytest.raises(ValueError):
            InterfaceProfile.from_dict(data)

    def test_confirmed_flag_gate(self):
        profile = self.base(confirmed=False, status="proposal")
        assert not profile.confirmed

    def test_load_profile_file(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text(json.dumps(DEFAULT_DEMO_PROFILE.to_dict(), ensure_ascii=False),
                        encoding="utf-8")
        assert load_profile(path).name == DEFAULT_DEMO_PROFILE.name

    def test_load_profile_broken_json(self, tmp_path):
        path = tmp_path / "profile.json"
        path.write_text("{broken", encoding="utf-8")
        with pytest.raises(ValueError):
            load_profile(path)

    def test_load_profile_missing_file(self, tmp_path):
        with pytest.raises(ValueError):
            load_profile(tmp_path / "nope.json")


class TestGroupChecksum:
    def test_definition(self):
        # 12 字组（X0–X7 + AD0–3）累加和 16 位截断，PC 与 PLC 共用。
        assert group_checksum([1, 0, 0, 0, 0, 0, 0, 1, 4000, 0, 2000, 100]) == 6102
        assert group_checksum([65535, 1]) == 0
        assert group_checksum([65535, 2]) == 1

    def test_empty(self):
        assert group_checksum([]) == 0


class TestVersionAddress:
    def test_none_allowed(self):
        assert validate_version_address(None) is None

    def test_range(self):
        assert validate_version_address(196) == 196
        with pytest.raises(ValueError):
            validate_version_address(8512)
        with pytest.raises(ValueError):
            validate_version_address(-1)
        with pytest.raises(ValueError):
            validate_version_address("D196")
