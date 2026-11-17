"""会话存储测试：落盘、轮转、异常恢复、导出、写失败可见。"""
import json
import zipfile

import pytest

from plcweave.bench.store import (
    STATUS_ENDED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_START_FAILED,
    SessionStore,
)


def start(store, **extra):
    snapshot = {"tool": "plcweave-bench", "tool_version": "0.3.0",
                "port": "COM7", "baud": 9600, "format": "8N1", "station": 1,
                "demo": False, **extra}
    session_id = store.record("start", snapshot)
    return session_id


class TestLifecycle:
    def test_start_event_end_roundtrip(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        session_id = start(store, version_address="D196")
        store.record("update", {"version_value": 101, "version_address": "D196"})
        store.record("event", {"seq": 1, "wall": "2026-11-03T21:00:00+08:00",
                               "mono_ms": 10.0, "actor": "user", "object": "X0",
                               "action": "提交输入", "target": 1, "result": "已生效"})
        store.record("sample", {"wall": "2026-11-03T21:00:01+08:00", "y": [1, 0]})
        summary = store.record("end", {"status": STATUS_ENDED, "end_reason": "正常结束"})
        assert summary["status"] == STATUS_ENDED
        assert summary["session_id"] == session_id
        assert store.current_id is None
        files = sorted(p.name for p in (tmp_path / "sessions" / session_id).iterdir())
        assert files == ["events.jsonl", "summary.json"]
        loaded = json.loads((tmp_path / "sessions" / session_id / "summary.json")
                            .read_text(encoding="utf-8"))
        assert loaded["version_value"] == 101        # update 补录成功
        assert loaded["ended_wall"] is not None

    def test_running_record_kept(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        session_id = start(store)
        assert store.list_sessions()[0]["status"] == STATUS_RUNNING
        assert store.current_id == session_id

    def test_no_session_end_noop(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        assert store.record("end", {"status": STATUS_ENDED}) is None


class TestRotation:
    def _make_ended(self, store, index):
        session_id = start(store, note=f"session-{index}")
        store.record("event", {"seq": 1, "object": f"op-{index}"})
        store.record("end", {"status": STATUS_ENDED, "end_reason": "正常结束"})
        return session_id

    def test_keep_30_ended_plus_current(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        for index in range(31):
            self._make_ended(store, index)
        start(store)   # 当前进行中会话
        sessions = store.list_sessions()
        ended = [item for item in sessions if item["status"] == STATUS_ENDED]
        running = [item for item in sessions if item["status"] == STATUS_RUNNING]
        assert len(ended) == 30       # 第 31 次归档后删除最旧
        assert len(running) == 1      # 当前会话不受轮转影响
        remaining_notes = [item.get("note") for item in ended]
        assert "session-0" not in remaining_notes      # 最旧被删
        assert "session-30" in remaining_notes         # 最新保留

    def test_failed_sessions_count_toward_rotation(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        for index in range(30):
            session_id = start(store, note=f"fail-{index}")
            store.record("end", {"status": STATUS_START_FAILED, "end_reason": "启动失败"})
        session_id = start(store, note="fail-30")
        store.record("end", {"status": STATUS_FAILED, "end_reason": "异常中断"})
        ended = [item for item in store.list_sessions() if item["status"] != STATUS_RUNNING]
        assert len(ended) == 30
        assert not list((tmp_path / "sessions").glob("*fail-0*"))   # 失败记录同样参与轮转

    def test_exported_copies_untouched(self, tmp_path):
        # 导出副本在会话目录之外，轮转只处理本工具历史目录（PRD §9.3）。
        store = SessionStore(tmp_path / "sessions")
        session_id = self._make_ended(store, 0)
        exported = store.export_session(session_id, tmp_path / "exports" / "a.zip")
        for index in range(1, 31):
            self._make_ended(store, index)
        assert exported.exists()   # 导出文件不被轮转删除


class TestRecovery:
    def test_stale_running_marked_as_interrupted(self, tmp_path):
        root = tmp_path / "sessions"
        # 模拟上次崩溃留下的“进行中”记录
        stale = root / "20261101-120000-0001"
        stale.mkdir(parents=True)
        (stale / "summary.json").write_text(json.dumps(
            {"session_id": stale.name, "status": STATUS_RUNNING}, ensure_ascii=False),
            encoding="utf-8")
        (stale / "events.jsonl").write_text('{"seq": 1, "object": "X0"}\n', encoding="utf-8")
        store = SessionStore(root)
        recovered = store.finalize_stale()
        assert recovered == [stale.name]
        summary = json.loads((stale / "summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == STATUS_FAILED
        assert "异常中断" in summary["end_reason"]
        assert "异常中断（程序未正常关闭该会话）" in summary["end_reason"]

    def test_recovery_keeps_recorded_events(self, tmp_path):
        root = tmp_path / "sessions"
        stale = root / "20261101-120000-0001"
        stale.mkdir(parents=True)
        (stale / "summary.json").write_text(
            json.dumps({"status": STATUS_RUNNING}), encoding="utf-8")
        (stale / "events.jsonl").write_text('{"seq": 1, "object": "X0"}\n',
                                            encoding="utf-8")
        store = SessionStore(root)
        store.finalize_stale()
        events = store.read_events(stale.name)
        assert events and events[0]["object"] == "X0"   # 已落盘事件不丢失

    def test_new_start_finalizes_stale_first(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        first = start(store)
        # 模拟崩溃重启：新进程新建 store 实例指向同一目录
        store2 = SessionStore(tmp_path / "sessions")
        start(store2)
        summary = json.loads((tmp_path / "sessions" / first / "summary.json")
                             .read_text(encoding="utf-8"))
        assert summary["status"] == STATUS_FAILED


class TestExport:
    def _full_session(self, store):
        session_id = start(store, port="COM7")
        store.record("update", {"version_value": 101})
        for seq in range(1, 4):
            store.record("event", {"seq": seq, "wall": "2026-11-03T21:00:00+08:00",
                                   "actor": "user", "object": f"X{seq}",
                                   "action": "提交输入", "target": 1,
                                   "result": "已生效", "unit": None})
        store.record("sample", {"wall": "2026-11-03T21:00:05+08:00", "state": "仿真中",
                                "y": [1, 0, 0, 0, 0, 0, 0, 0], "da_raw": [3000, 0],
                                "effective_x": [1, 0], "effective_ad_raw": [2000]})
        store.record("end", {"status": STATUS_ENDED, "end_reason": "正常结束"})
        return session_id

    def test_zip_contents(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        session_id = self._full_session(store)
        output = store.export_session(session_id, tmp_path / "out.zip")
        with zipfile.ZipFile(output) as bundle:
            names = set(bundle.namelist())
            assert {"summary.json", "operations.csv", "samples.csv", "README.txt"} <= names
            summary = json.loads(bundle.read("summary.json").decode("utf-8"))
            assert summary["session_id"] == session_id
            operations = bundle.read("operations.csv").decode("utf-8")
            assert "操作对象" in operations and "X1" in operations    # UTF-8 中文可读
            samples = bundle.read("samples.csv").decode("utf-8")
            assert "3000" in samples

    def test_no_overwrite_same_name(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        session_id = self._full_session(store)
        first = store.export_session(session_id, tmp_path / "out.zip")
        second = store.export_session(session_id, tmp_path / "out.zip")
        assert first.name == "out.zip"
        assert second.name == "out-v2.zip"
        assert first.exists() and second.exists()

    def test_export_missing_session(self, tmp_path):
        store = SessionStore(tmp_path / "sessions")
        with pytest.raises(FileNotFoundError):
            store.export_session("nope", tmp_path / "x.zip")

    def test_export_during_running(self, tmp_path):
        # 仿真进行中导出当前快照：会话不因此结束（PRD §9.4）。
        store = SessionStore(tmp_path / "sessions")
        session_id = start(store)
        store.record("event", {"seq": 1, "object": "X0", "action": "提交输入"})
        output = store.export_session(session_id, tmp_path / "mid.zip")
        assert output.exists()
        assert store.current_id == session_id
        assert store.list_sessions()[0]["status"] == STATUS_RUNNING


class TestWriteFailure:
    def test_write_error_surfaces(self, tmp_path, monkeypatch):
        store = SessionStore(tmp_path / "sessions")
        session_id = start(store)
        # 模拟磁盘故障：flush 抛 OSError
        original_flush = store._events_file.flush
        monkeypatch.setattr(store._events_file, "flush",
                            lambda: (_ for _ in ()).throw(OSError("disk full")))
        store.record("event", {"seq": 1, "object": "X0"})
        assert store.write_error and "日志写入失败" in store.write_error
        monkeypatch.setattr(store._events_file, "flush", original_flush)
        store.record("event", {"seq": 2, "object": "X0"})
        assert store.write_error is None   # 恢复后清除故障标记
