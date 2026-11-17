"""调试记录存储：会话落盘、30 次轮转、异常恢复与 ZIP 导出。

PRD §9 规则：
- 会话边界 = 点击“开始仿真”→ 结束清理完成；启动失败也形成一条记录；
- 进行中的记录持续落盘（先写意图再发送，由 engine 的 record 钩子保证顺序）；
- 默认保留最近 30 次已结束记录 + 当前进行中记录；第 31 次归档后删除最旧；
- 异常退出后下次启动把未关闭记录标为“异常中断”，保留已落盘事件；
- 导出 ZIP 含会话摘要 JSON + UTF-8 CSV 明细；不覆盖同名文件。

默认目录：%LOCALAPPDATA%/PLCWeave/hil-bench/sessions（可用 set_root 覆盖，
调试记录页展示并允许打开）。
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RETENTION_ENDED = 30

STATUS_RUNNING = "进行中"
STATUS_ENDED = "正常结束"
STATUS_FAILED = "异常中断"
STATUS_START_FAILED = "启动失败"


def default_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "PLCWeave" / "hil-bench" / "sessions"


class SessionStore:
    """会话记录管理。所有写入先写 JSONL 事件流，再更新摘要，崩溃可恢复。"""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_id: str | None = None
        self._current_dir: Path | None = None
        self._events_file = None
        self.write_error: str | None = None

    # ---- 路径 -------------------------------------------------------------
    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    @staticmethod
    def _now_id() -> str:
        # 同一秒内多次开会话也必须唯一：时间戳 + 进程号 + 随机后缀。
        return (datetime.now().strftime("%Y%m%d-%H%M%S-")
                + f"{os.getpid() % 1000:03d}-" + uuid.uuid4().hex[:6])

    # ---- 会话生命周期 -------------------------------------------------------
    def session_start(self, snapshot: dict) -> str:
        """开始新会话。若存在未关闭的旧会话，先按异常中断归档。"""
        self.finalize_stale()
        session_id = self._now_id()
        directory = self._session_dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        summary = {
            "session_id": session_id,
            "status": STATUS_RUNNING,
            "started_wall": snapshot.get("started_wall")
            or datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
            "ended_wall": None,
            "end_reason": None,
            **{key: value for key, value in snapshot.items() if key != "started_wall"},
        }
        (directory / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        self.current_id = session_id
        self._current_dir = directory
        self._events_file = (directory / "events.jsonl").open("a", encoding="utf-8")
        self.write_error = None
        return session_id

    def session_event(self, event: dict) -> None:
        """追加一条操作/通讯/采样事件（持续落盘）。写失败时置 write_error。"""
        if self._events_file is None:
            return
        try:
            self._events_file.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._events_file.flush()
            self.write_error = None
        except OSError as exc:
            self.write_error = f"日志写入失败: {exc}"

    def session_sample(self, sample: dict) -> None:
        self.session_event({"type": "sample", **sample})

    def session_update(self, patch: dict) -> None:
        """把后补信息（如自动连接读到的版本）合并进当前会话摘要。"""
        if self.current_id is None or self._current_dir is None:
            return
        summary_path = self._current_dir / "summary.json"
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary = {"session_id": self.current_id}
        summary.update(patch)
        try:
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        except OSError as exc:
            self.write_error = f"会话摘要更新失败: {exc}"

    def record(self, kind: str, payload: dict) -> str | dict | None:
        """engine record 钩子的统一入口。"""
        dispatch = {
            "start": self.session_start,
            "event": self.session_event,
            "sample": self.session_sample,
            "update": self.session_update,
            "end": self.session_end,
        }
        handler = dispatch.get(kind)
        if handler is None:
            raise ValueError(f"未知记录类型: {kind}")
        return handler(payload)

    def session_end(self, summary_patch: dict) -> dict | None:
        """结束当前会话：合并摘要、关闭事件流、执行 30 次轮转。"""
        if self.current_id is None or self._current_dir is None:
            return None
        directory = self._current_dir
        summary_path = directory / "summary.json"
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary = {"session_id": self.current_id}
        summary.update({
            "status": summary_patch.get("status", STATUS_ENDED),
            "end_reason": summary_patch.get("end_reason", "用户结束"),
            "ended_wall": datetime.now(timezone.utc).astimezone().isoformat(
                timespec="milliseconds"),
        })
        for key in ("error", "readback_error", "final_outputs", "script_cleanup_error"):
            if summary_patch.get(key):
                summary[key] = summary_patch[key]
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        ended_id = self.current_id
        self.release_current()
        self.rotate()
        summary["session_id"] = ended_id
        return summary

    def _close_events_file(self) -> None:
        if self._events_file is not None:
            try:
                self._events_file.close()
            except OSError:
                pass
            self._events_file = None

    def release_current(self) -> None:
        self._close_events_file()
        self.current_id = None
        self._current_dir = None
        self.write_error = None

    # ---- 恢复与轮转 ----------------------------------------------------------
    def finalize_stale(self) -> list[str]:
        """把遗留的“进行中”记录标为异常中断（程序崩溃/断电恢复）。"""
        recovered: list[str] = []
        for directory in self._ended_first():
            if directory.name == self.current_id:
                continue
            summary_path = directory / "summary.json"
            if not summary_path.is_file():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if summary.get("status") == STATUS_RUNNING:
                summary["status"] = STATUS_FAILED
                summary["end_reason"] = "异常中断（程序未正常关闭该会话）"
                summary["ended_wall"] = datetime.now(timezone.utc).astimezone().isoformat(
                    timespec="milliseconds")
                summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
                recovered.append(directory.name)
        return recovered

    def _ended_first(self) -> list[Path]:
        """按修改时间列出全部会话目录（旧的在前）。"""
        if not self.root.exists():
            return []
        return sorted((p for p in self.root.iterdir() if p.is_dir()),
                      key=lambda p: p.stat().st_mtime)

    def rotate(self, keep: int = RETENTION_ENDED) -> list[str]:
        """仅保留最近 keep 次已结束记录 + 当前会话；返回被删除的目录名。"""
        ended = []
        for directory in self._ended_first():
            if directory.name == self.current_id:
                continue
            summary_path = directory / "summary.json"
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                summary = {}
            if summary.get("status") in (STATUS_ENDED, STATUS_FAILED, STATUS_START_FAILED):
                ended.append((summary.get("ended_wall") or "", directory))
        ended.sort(key=lambda item: (item[0], item[1].name))
        removed = []
        for _, directory in ended[:-keep] if keep > 0 else ended:
            shutil.rmtree(directory, ignore_errors=True)
            removed.append(directory.name)
        return removed

    # ---- 列表与读取 ----------------------------------------------------------
    def list_sessions(self) -> list[dict]:
        """全部会话摘要（含进行中），按开始时间倒序。"""
        items: list[dict] = []
        for directory in reversed(self._ended_first()):
            summary_path = directory / "summary.json"
            if not summary_path.is_file():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            summary["dir"] = str(directory)
            items.append(summary)
        return items

    def read_events(self, session_id: str) -> list[dict]:
        path = self._session_dir(session_id) / "events.jsonl"
        if not path.is_file():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # 恢复场景允许尾部截断行：保留可解析部分，不伪造缺失事件。
                events.append({"type": "corrupt_line", "raw": line[:200]})
        return events

    def storage_path(self) -> str:
        return str(self.root)

    def attachment_path(self, name: str) -> Path:
        if self._current_dir is None or Path(name).name != name:
            raise ValueError("会话附件需要有效记录和单一文件名")
        return self._current_dir / name

    # ---- 导出 ---------------------------------------------------------------
    def export_session(self, session_id: str, output_path: str | Path) -> Path:
        """导出 ZIP：summary.json + operations.csv + samples.csv。不覆盖同名文件。"""
        directory = self._session_dir(session_id)
        summary_path = directory / "summary.json"
        if not summary_path.is_file():
            raise FileNotFoundError(f"会话 {session_id} 不存在")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        events = self.read_events(session_id)
        summary["exported_through_seq"] = max((event.get("seq", 0) for event in events), default=0)
        # The host and GUI have separate sequence spaces. Capture complete audit
        # lines once and declare both cutoffs, rather than implying a common instant.
        transactions = directory / "script-transactions.jsonl"
        audit = b""
        if transactions.is_file():
            with transactions.open("rb") as source:
                audit = source.read(os.fstat(source.fileno()).st_size)
            audit = audit[:audit.rfind(b"\n") + 1]
            summary["script_audit_through_sequence"] = max(
                (json.loads(line).get("sequence", 0) for line in audit.splitlines()), default=0)
            summary["export_snapshot_note"] = "主日志与脚本原始日志分别截取；两个序号独立，运行中导出可能包含尚未显示的脚本事务。"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path = _unique_path(output_path)
        operations = [event for event in events if event.get("type", "op") == "op"]
        samples = [event for event in events if event.get("type") == "sample"]
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            if transactions.is_file():
                bundle.writestr("script-transactions.jsonl", audit)
            bundle.writestr("summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
            bundle.writestr("operations.csv", _operations_csv(operations))
            bundle.writestr("samples.csv", _samples_csv(samples))
            bundle.writestr("README.txt",
                            "PLCWeave 手动HIL仿真台 导出记录\n"
                            f"会话: {session_id}\n"
                            f"状态: {summary.get('status')}\n"
                            "operations.csv=操作与通讯明细（UTF-8，Excel 请用数据导入向导）\n"
                            "samples.csv=输出采样明细\n"
                            "本导出副本由用户保存，不参与本机 30 次轮转。\n")
        return output_path


def _unique_path(path: Path) -> Path:
    """同名文件不覆盖：追加 -v2、-v3……"""
    stem, suffix = path.stem, path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-v{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"无法为 {path} 生成不重复文件名")


def _operations_csv(operations: list[dict]) -> str:
    headers = ["序号", "时间", "单调耗时ms", "来源", "操作对象", "动作",
               "目标值", "生效值", "单位", "量程", "步长%", "结果", "原因", "明细"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for event in operations:
        writer.writerow([
            event.get("seq"), event.get("wall"), event.get("mono_ms"),
            event.get("actor"), event.get("object"), event.get("action"),
            _cell(event.get("target")), _cell(event.get("effective")),
            event.get("unit"), event.get("range_kind"), event.get("step_pct"),
            event.get("result"), event.get("reason"), _cell(event.get("detail")),
        ])
    return buffer.getvalue()


def _samples_csv(samples: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["时间", "状态", "Y0–Y7", "DA1 raw", "DA2 raw",
                     "生效X0–X7", "生效AD raw0–3", "客户寄存器"])
    for sample in samples:
        writer.writerow([
            sample.get("wall"), sample.get("state"),
            _cell(sample.get("y")),
            *(sample.get("da_raw") or [None, None]),
            _cell(sample.get("effective_x")), _cell(sample.get("effective_ad_raw")),
            _cell(sample.get("customer_registers")),
        ])
    return buffer.getvalue()


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
