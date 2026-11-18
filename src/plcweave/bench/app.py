"""PLCWeave 手动硬件在环仿真台 — tkinter 桌面界面。

布局与交互遵循 hmi/PRD.md 与 hmi/prototype/main.md：
- 左上数字输入 X0–X7 横向单排 + 每点下方独立状态小灯（PLC 确认的生效值）
- 右上模拟输入 AD0–AD3 四列，竖直只读滑条居中、−/＋ 在左右、数值在下方
- 左下数字输出 Y0–Y7 只读点位牌 + 小灯（FC01 直接读 Y）
- 右下模拟输出 DA1–DA2 两列只读（FC03 直接读 D8050/D8051）
- 上方连接与版本信息，下方仿真操作与本次日志

线程模型：worker 线程序列化所有串口事务；UI 线程只通过事件队列更新，
tkinter 控件永不跨线程直接访问。无监听端口、无 Web 服务。
"""
from __future__ import annotations

import json
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .contract import DEFAULT_DEMO_PROFILE, InterfaceProfile, load_profile
from .engine import (
    BAUD_RATES,
    FORMAT_CHOICES,
    FULL_RAW,
    RANGE_LABELS,
    UNIT_LABELS,
    BenchEngine,
    RecordingError,
    State,
)
from .rtu import LoopbackTransport
from .store import SessionStore, default_root
from .virtual import VirtualPLC
from .script_bridge import ScriptController
from .i18n import (DEFAULT_LANGUAGE, LANGUAGES, get_language, msg, set_language, t,
                   tr, ui_family, untr)

TOOL_VERSION = "0.6.3"

# 视觉规范（DESIGN_RULES：浅灰底 + 白卡片 + 蓝主色 + 绿/红状态色）
BG = "#EEF1F6"
CARD = "#FFFFFF"
BORDER = "#DDE3EC"
INK = "#0F172A"
SUB = "#64748B"
ACCENT = "#2563EB"
ACCENT_DARK = "#1D4ED8"
GREEN = "#16A34A"
RED = "#DC2626"
ORANGE = "#D97706"
LED_OFF = "#CBD5E1"
BAR_TRACK = "#E2E8F0"
BAR_FILL = "#2563EB"

# 界面统一使用 Tk 命名字体（bench7–bench12b）：切语言时改 family 即全界面生效。
# family 由 i18n.ui_family() 决定：阿拉伯语 → Segoe UI（雅黑无阿拉伯字形），其余 → 微软雅黑。
_FONT_SIZES = (7, 8, 9, 10, 11, 12)


def _bench_font_name(size: int, bold: bool = False) -> str:
    return f"bench{size}{'b' if bold else ''}"


REFRESH_CHOICES = {"250ms": 250, "500ms": 500, "1000ms": 1000}

# 文字随语言变化的按钮按语言微调宽度（Tk width 为字符单位，各语言字符宽不同）
BTN_WIDTHS = {
    "start": {"zh": 12, "en": 18, "fr": 24, "pt": 19, "es": 20, "ar": 14},
    "script_start": {"zh": 12, "en": 19, "fr": 23, "pt": 25, "es": 26, "ar": 14},
}

UI_CONFIG_PATH = Path(default_root()).parent / "ui_config.json"


def list_com_ports() -> list[str]:
    try:
        from serial.tools import list_ports

        return [item.device for item in sorted(list_ports.comports())]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# worker：串口事务线程
# ---------------------------------------------------------------------------
class BenchWorker(threading.Thread):
    """单线程执行 engine 调用；定时轮询与心跳；事件转发给 UI。"""

    def __init__(self, engine: BenchEngine, store: SessionStore) -> None:
        super().__init__(daemon=True, name="bench-worker")
        self.engine = engine
        self.store = store
        self.commands: queue.Queue = queue.Queue()
        self.ui_events: queue.Queue = queue.Queue()
        self._alive = threading.Event()
        self._alive.set()
        self.refresh_ms = 250
        self._last_poll = 0.0
        self._last_heartbeat = 0.0
        self._last_sample = 0.0
        engine.sink = self._on_engine_event
        engine.record = self._on_engine_record
        self.scripts = ScriptController(engine, store)

    # ---- 引擎钩子（worker 线程上下文） --------------------------------------
    def _on_engine_event(self, payload: dict) -> None:
        self.ui_events.put(payload)

    def _on_engine_record(self, kind: str, payload: dict):
        try:
            if kind in ("event", "sample") and self.engine._recording and self.store.current_id is None:
                raise OSError(t("store.log_not_open"))
            result = self.store.record(kind, payload)
            if self.store.write_error:
                raise OSError(self.store.write_error)
            return result
        except OSError as exc:
            raise RecordingError(str(exc)) from exc

    def _recording_failed(self, exc: RecordingError) -> None:
        try:
            self.scripts.close()
        except (OSError, RuntimeError):
            pass
        self.engine.abort_recording(f"日志故障: {exc}")
        try:
            self.store.session_end({"status": "异常中断", "end_reason": "日志故障", "error": str(exc)})
        except OSError:
            self.store.release_current()
        self.ui_events.put({"type": "store_error", "message": str(exc)})

    # ---- UI 提交命令 --------------------------------------------------------
    def submit(self, function, *args, **kwargs) -> None:
        self.commands.put((function, args, kwargs))

    # ---- 线程主循环 ----------------------------------------------------------
    def run(self) -> None:
        while self._alive.is_set():
            now = time.monotonic()
            try:
                self.scripts.poll()
                if self.engine.state == State.SIMULATING and now - self._last_heartbeat >= 0.5:
                    self._last_heartbeat = now
                    self.engine.heartbeat()
                try:
                    function, args, kwargs = self.commands.get(timeout=0.02)
                except queue.Empty:
                    pass
                else:
                    function(*args, **kwargs)
                if not self._alive.is_set():
                    break
                now = time.monotonic()
                if (self.engine.state in (State.CONNECTED, State.SIMULATING, State.MANUAL)
                        and (now - self._last_poll) * 1000 >= self.refresh_ms):
                    self._last_poll = now
                    self.engine.poll()
                    if self.engine.state in (State.SIMULATING, State.MANUAL) and now - self._last_sample > 1.0:
                        self._last_sample = now
                        self._on_engine_record("sample", self.engine.sample_snapshot())
            except RecordingError as exc:
                self._recording_failed(exc)
            except Exception as exc:
                self.ui_events.put({"type": "command_error", "message": str(exc)})

    def stop(self) -> None:
        self._alive.clear()


# ---------------------------------------------------------------------------
# 小控件
# ---------------------------------------------------------------------------
def make_led(parent, size=14) -> tk.Canvas:
    canvas = tk.Canvas(parent, width=size + 4, height=size + 4, bg=CARD,
                       highlightthickness=0)
    canvas._led_size = size
    canvas._led = canvas.create_oval(2, 2, size + 2, size + 2, fill=LED_OFF,
                                     outline="#94A3B8")
    return canvas


def set_led(canvas, color: str) -> None:
    canvas.itemconfigure(canvas._led, fill=color)


def make_bar(parent, width=30, height=40) -> tk.Canvas:
    """竖直只读滑条：上满量程、下 0，确认生效值自下向上增长。

    不绑定任何鼠标/滚轮/键盘事件，也不可聚焦（PRD A07：只读滑条）。
    """
    canvas = tk.Canvas(parent, width=width, height=height, bg=CARD,
                       highlightthickness=0, takefocus=0)
    canvas._bar = (width, height)
    canvas._track = canvas.create_rectangle(10, 2, width - 10, height - 2,
                                            fill=BAR_TRACK, outline="#B6C0CF")
    canvas._fill = canvas.create_rectangle(10, height - 2, width - 10, height - 2,
                                           fill=BAR_FILL, outline="")
    canvas._top_tick = canvas.create_text(width // 2, 10, text="", font="bench7",
                                          fill=SUB, state="hidden")
    canvas._value_text = canvas.create_text(width // 2, height // 2, text="",
                                            font="bench8b", fill=SUB)
    return canvas


def set_bar(canvas, fraction: float | None, text: str, stale: bool = False) -> None:
    width, height = canvas._bar
    canvas.delete(canvas._fill)
    color = "#94A3B8" if stale else BAR_FILL
    if fraction is None:
        canvas._fill = canvas.create_rectangle(10, height - 2, width - 10, height - 2,
                                               fill=BAR_TRACK, outline="")
    else:
        fraction = max(0.0, min(1.0, fraction))
        top = (height - 2) - (height - 4) * fraction
        canvas._fill = canvas.create_rectangle(10, top, width - 10, height - 2,
                                               fill=color, outline="")
    canvas.tag_lower(canvas._track)      # 层叠：轨道 < 填充
    _ = text


class LedColumn(tk.Frame):
    """一个点位牌下方的状态小灯 + 文字（小灯与操作按钮分开）。"""

    def __init__(self, parent) -> None:
        super().__init__(parent, bg=CARD)
        self.led = make_led(self)
        self.led.pack()
        self.text = tk.Label(self, text=t("led.unknown"), font="bench8", fg=SUB, bg=CARD)
        self.text.pack()

    def update_state(self, state: str, stale: bool = False) -> None:
        # state: on / off / unknown / pending
        if stale:
            set_led(self.led, ORANGE)
            self.text.configure(text=t("led.stale"), fg=ORANGE)
            return
        color_map = {"on": GREEN, "off": LED_OFF, "unknown": LED_OFF, "pending": ORANGE}
        set_led(self.led, color_map.get(state, LED_OFF))
        text_map = {"on": "led.on", "off": "led.off", "unknown": "led.unknown",
                    "pending": "led.pending"}
        fg_map = {"on": GREEN, "off": SUB, "unknown": SUB, "pending": ORANGE}
        self.text.configure(text=t(text_map.get(state, "led.unknown")),
                            fg=fg_map.get(state, SUB))


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class BenchApp:
    def __init__(self, root: tk.Tk, *, demo: bool = False,
                 profile: InterfaceProfile | None = None,
                 store: SessionStore | None = None,
                 worker: BenchWorker | None = None,
                 engine: BenchEngine | None = None) -> None:
        self.root = root
        self.demo = demo
        self.profile = profile or DEFAULT_DEMO_PROFILE
        self.store = store or SessionStore()
        self._stale = False
        self._last_error_message: str | None = None
        # ("msg", 引擎原文) 或 ("key", i18n key)：切语言时按当前语言重算
        self._error_raw: tuple[str, str] | None = None
        self._last_state = State.DISCONNECTED
        self._pending_ad_errors: dict[int, tk.Label] = {}
        self._customer_rows: list[dict] = []
        self._customer_pending = False
        self._closing = False
        self._lang_binds = []      # i18n：静态文案绑定，语言切换时统一重建
        self._build_engine(worker, engine)
        self._load_ui_config()
        set_language(self.ui_config.get("language") or DEFAULT_LANGUAGE)
        if not demo and profile is None and engine is None and self.ui_config.get("profile_path"):
            try:
                self.profile = load_profile(self.ui_config["profile_path"])
                self.engine.profile = self.profile
            except ValueError as exc:
                self._set_error(str(exc))
        self._ensure_fonts()
        self._build_styles()
        self._build_ui()
        self._apply_config_to_widgets()
        self._restore_customer_watches()
        self.refresh_permissions()
        self.refresh_values(initial=True)
        self._event_job = self.root.after(50, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- 引擎/worker 构造 ---------------------------------------------------
    def _build_engine(self, worker, engine) -> None:
        if engine is None:
            engine = BenchEngine(profile=self.profile)
            engine.apply_settings(demo=self.demo)
        self.engine = engine
        if worker is None:
            worker = BenchWorker(engine, self.store)
        self.worker = worker
        if self.demo and engine.transport is None:
            worker.submit(self._inject_loopback)

    def _inject_loopback(self) -> None:
        device = VirtualPLC(self.engine.profile)
        self.engine.transport = LoopbackTransport(device)
        self.engine.owns_transport = False
        self._virtual_device = device

    # ---- 配置持久化 ----------------------------------------------------------
    def _load_ui_config(self) -> None:
        self.ui_config = {"port": "", "baud": 9600, "format": "8N1", "station": 1,
                          "version_address": "", "refresh_ms": 250,
                          "profile_path": "", "x_mode": "保持开关",
                          "language": DEFAULT_LANGUAGE,
                          "test_script": "", "script_args": {}}
        try:
            data = json.loads(UI_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.ui_config.update(data)
        except (OSError, json.JSONDecodeError):
            pass
        if self.demo:
            self.ui_config["port"] = ""
        if not self.ui_config.get("profile_path"):
            self.ui_config["profile_path"] = ""
        if not isinstance(self.ui_config.get("script_args"), dict):
            self.ui_config["script_args"] = {}
        # 旧版全局 test_script_args 迁移为按脚本记忆，切换项目互不覆盖。
        legacy = self.ui_config.pop("test_script_args", None)
        if legacy and self.ui_config.get("test_script"):
            self.ui_config["script_args"].setdefault(self.ui_config["test_script"], legacy)

    def _save_ui_config(self) -> None:
        try:
            UI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            UI_CONFIG_PATH.write_text(json.dumps(self.ui_config, ensure_ascii=False,
                                                 indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---- 样式 ----------------------------------------------------------------
    def _ensure_fonts(self) -> None:
        """在当前 Tk 解释器注册命名字体（每个 root 独立注册，多窗口测试互不影响）。

        必须持有 Font 对象：tkinter 在 Font 被回收时会删除同名 Tcl 命名字体，
        引用一丢，控件里的 font="bench9" 就退化为 Tk 默认字体（宋体 12），
        表现为全屏文字偏大、卡片内文案被裁切。
        """
        family = ui_family()
        self._fonts: dict[str, tkfont.Font] = {}
        for size in _FONT_SIZES:
            for bold in (False, True):
                name = _bench_font_name(size, bold)
                try:
                    self._fonts[name] = tkfont.Font(name=name, exists=True, root=self.root)
                except tk.TclError:
                    self._fonts[name] = tkfont.Font(
                        name=name, family=family, size=size,
                        weight="bold" if bold else "normal", root=self.root)

    def _apply_font_family(self) -> None:
        """切换命名字体 family：所有引用该字体的控件（含 ttk 样式）即时更新。"""
        family = ui_family()
        for font in getattr(self, "_fonts", {}).values():
            try:
                font.configure(family=family)
            except tk.TclError:
                continue

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=INK, font="bench9")
        style.configure("Card.TFrame", background=CARD)
        style.configure("Card.TLabel", background=CARD, foreground=INK)
        style.configure("Sub.TLabel", background=CARD, foreground=SUB,
                        font="bench8")
        style.configure("TCombobox", fieldbackground="white", background="#F1F5F9",
                        arrowcolor=INK)
        style.configure("Treeview", background="white", fieldbackground="white",
                        font="bench9", rowheight=24)
        style.configure("Treeview.Heading", font="bench9b", background="#F1F5F9")
        style.configure("TButton", font="bench9")
        # 与 9pt 输入框等高（clam 输入框上下约 4px 内边距，按钮取同值）
        style.configure("Customer.TButton", font="bench9", padding=(10, 0))

    def _card(self, parent) -> tk.Frame:
        frame = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
        return frame

    def _button(self, parent, text, command, *, primary=False, width=None,
                state=tk.NORMAL, padx=10) -> tk.Button:
        bg = ACCENT if primary else "white"
        fg = "white" if primary else INK
        active = ACCENT_DARK if primary else "#F1F5F9"
        # 禁用态必须显式给字色：Tk 默认 SystemDisabledText（灰）压在蓝底上，
        # 实测对比度约 1:1，"Start simulation" 之类主按钮禁用后完全认不出字。
        disabled_fg = "#F1F5F9" if primary else "#64748B"
        return tk.Button(parent, text=text, command=command, font="bench9",
                         bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                         disabledforeground=disabled_fg,
                         relief="flat", bd=1, highlightthickness=1,
                         highlightbackground=BORDER, cursor="hand2",
                         state=state, width=width, padx=padx, pady=3)

    # ---- i18n 文案绑定 ----------------------------------------------------------
    def _bind_text(self, widget, key: str) -> None:
        """注册静态文案：切换语言时按 key 重建文字。"""
        self._lang_binds.append(lambda w=widget, k=key: w.configure(text=t(k)))

    def _bind_button(self, widget, key: str, widths: dict[str, int]) -> None:
        """注册按钮文案：切换语言时重建文字与按语言调好的宽度。"""
        self._lang_binds.append(
            lambda w=widget, k=key, ws=widths: w.configure(
                text=t(k), width=ws.get(get_language(), 12)))

    def _bind_combo_values(self, combo, canonicals) -> None:
        """注册下拉框候选值：候选存引擎原值，显示经 tr() 翻译。"""
        self._lang_binds.append(
            lambda c=combo, cs=tuple(canonicals): c.configure(values=[tr(v) for v in cs]))

    def _bind_heading(self, tree, column: str, key: str) -> None:
        self._lang_binds.append(lambda w=tree, c=column, k=key: w.heading(c, text=t(k)))

    def _apply_language(self) -> None:
        """按当前语言重建全部文案：字体 family + 静态绑定 + 各动态刷新函数。"""
        self._apply_font_family()
        self.root.title(t("app.title", version=TOOL_VERSION))
        for bind in self._lang_binds:
            bind()
        self.refresh_permissions()
        self.refresh_values()
        self._update_version_label()
        self._update_status_line()
        self._render_customer_values()
        self._refresh_script_label()
        self._refresh_error_text()
        self._refresh_io_labels()
        self._rebuild_log()

    def _on_language(self, _event=None) -> None:
        display = self.lang_var.get()
        code = next((c for c, name in LANGUAGES.items() if name == display), None)
        if code is None or code == get_language():
            self.lang_var.set(LANGUAGES[get_language()])
            return
        # 先在旧语言下把显示值还原为引擎原值，切换后再按新语言重映射
        x_mode = untr(self.x_mode_var.get())
        access = untr(self.watch_access.get())
        set_language(code)
        self.ui_config["language"] = code
        self._save_ui_config()
        self._apply_language()
        self.x_mode_var.set(tr(x_mode))
        self.watch_access.set(tr(access))

    # ---- 界面骨架 --------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root.title(t("app.title", version=TOOL_VERSION))
        self.root.configure(bg=BG)
        self.root.geometry("1600x860")
        # AD 列"目标/生效"改为两行显示（中文/英文都放得下），内容比旧版高约 14px，
        # 最小高度从 740 提到 760，低于此高度卡片会被压扁导致输入框溢出。
        self.root.minsize(1530, 760)

        self._build_topbar()
        self._build_log_area()
        self._build_bottom_bar()
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(4, 2))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=1)
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_digital_input_card(left)
        self._build_analog_input_card(left)
        self._build_digital_output_card(left)
        self._build_analog_output_card(left)
        self._build_customer_card(right)
        # 启动语言可能非默认：创建完成后先跑一遍绑定，把宽度/候选值校正到当前语言
        for bind in self._lang_binds:
            bind()

    def _build_topbar(self) -> None:
        bar = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER,
                       highlightthickness=1)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        inner = tk.Frame(bar, bg=CARD)
        inner.pack(fill="x", padx=10, pady=6)

        def field(key):
            label = tk.Label(inner, text=t(key), font="bench9", bg=CARD, fg=SUB)
            label.pack(side="left", padx=(10, 2))
            self._bind_text(label, key)
            return inner

        field("COM")   # COM 为协议词，不入字典
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(inner, textvariable=self.port_var, width=8,
                                       state="readonly", values=list_com_ports())
        self.port_combo.pack(side="left")
        self._button(inner, "↻", self._refresh_ports, width=2).pack(side="left", padx=(2, 8))

        field("field.baud")
        self.baud_var = tk.StringVar(value="9600")
        self.baud_combo = ttk.Combobox(inner, textvariable=self.baud_var, width=8,
                                       state="readonly",
                                       values=[str(b) for b in BAUD_RATES])
        self.baud_combo.pack(side="left", padx=(0, 8))

        field("field.format")
        self.format_var = tk.StringVar(value="8N1")
        self.format_combo = ttk.Combobox(inner, textvariable=self.format_var, width=6,
                                         state="readonly", values=list(FORMAT_CHOICES))
        self.format_combo.pack(side="left", padx=(0, 8))

        field("field.station")
        self.station_var = tk.StringVar(value="1")
        self.station_entry = tk.Entry(inner, textvariable=self.station_var, width=5,
                                      font="bench9", relief="solid", bd=1)
        self.station_entry.pack(side="left", padx=(0, 8))

        field("field.version")
        self.version_var = tk.StringVar()
        self.version_entry = tk.Entry(inner, textvariable=self.version_var, width=7,
                                      font="bench9", relief="solid", bd=1)
        self.version_entry.pack(side="left", padx=(0, 8))
        self.version_entry.insert(0, "D")

        self.connect_btn = self._button(inner, t("btn.connect"), self._on_connect, width=6)
        self._bind_button(self.connect_btn, "btn.connect",
                          {"zh": 6, "en": 8, "fr": 9, "pt": 8, "es": 8, "ar": 6})
        self.connect_btn.pack(side="left", padx=(0, 10))
        self.disconnect_btn = self._button(inner, t("btn.disconnect"), self._on_disconnect, width=6)
        self._bind_button(self.disconnect_btn, "btn.disconnect",
                          {"zh": 6, "en": 11, "fr": 11, "pt": 11, "es": 11, "ar": 9})
        self.disconnect_btn.pack(side="left", padx=(0, 10))

        self.version_label = tk.Label(inner, text=t("version.none"), font="bench10b",
                                      bg=CARD, fg=INK)
        self.version_label.pack(side="left", padx=(6, 0))

        self.status_label = tk.Label(inner, text=self._status_text(), font="bench10b",
                                     bg=CARD, fg=SUB)
        self.status_label.pack(side="right")

        # 语言切换（i18n）：切换即时生效并写入 ui_config.json
        self.lang_var = tk.StringVar(value=LANGUAGES[get_language()])
        self.lang_combo = ttk.Combobox(inner, textvariable=self.lang_var, width=10,
                                       state="readonly", values=list(LANGUAGES.values()))
        self.lang_combo.pack(side="right", padx=(0, 2))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        lang_label = tk.Label(inner, text=t("lang.label"), font="bench8", bg=CARD, fg=SUB)
        lang_label.pack(side="right", padx=(10, 4))
        self._bind_text(lang_label, "lang.label")

    def _status_text(self) -> str:
        base = self.engine.state if hasattr(self, "engine") else State.DISCONNECTED
        suffix = t("status.demo_suffix") if self.demo else ""
        return f"{tr(base)}{suffix}"

    def _refresh_ports(self) -> None:
        self.port_combo.configure(values=list_com_ports())

    # ---- 左上：数字输入 --------------------------------------------------------
    def _build_digital_input_card(self, parent) -> None:
        card = self._card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=2)
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=12, pady=(8, 0))
        # 标题独占表头：交互下拉移到卡片底部工具行。
        # 表头塞"标题+交互+下拉"在法/西/葡/阿下必然挤爆（标题就 165~178px，
        # 卡片只有约 287px），压扁下拉框比截标题更糟，索性腾到下方整行。
        di_title = tk.Label(head, text=t("di.title"), font="bench12b",
                            bg=CARD, fg=INK, anchor="w")
        di_title.pack(side="left")
        self._bind_text(di_title, "di.title")
        hint1 = tk.Label(card, text=t("di.hint_layout"), font="bench8", bg=CARD, fg=SUB,
                          anchor="w")
        hint1.pack(anchor="w", padx=12)
        self._bind_text(hint1, "di.hint_layout")

        tiles = tk.Frame(card, bg=CARD)
        tiles.pack(fill="x", padx=12, pady=(6, 0))
        self.x_buttons: list[tk.Button] = []
        self.x_leds: list[LedColumn] = []
        self.x_captions: list[tk.Label] = []
        for index in range(8):
            column = tk.Frame(tiles, bg=CARD)
            column.grid(row=0, column=index, padx=3, sticky="n")
            tiles.columnconfigure(index, weight=1)
            button = tk.Button(column, text=f"X{index}", font="bench10b",
                               width=4, relief="flat", bd=1, cursor="hand2",
                               bg="#EFF6FF", fg=ACCENT_DARK, activebackground="#DBEAFE",
                               highlightthickness=1, highlightbackground=BORDER,
                               command=lambda i=index: self._on_x_click(i))
            button.pack()
            button.bind("<ButtonPress-1>", lambda e, i=index: self._on_x_press(i))
            button.bind("<ButtonRelease-1>", lambda e, i=index: self._on_x_release(i))
            button.bind("<Leave>", lambda e, i=index: self._on_x_leave(i))
            self.x_buttons.append(button)
            led_column = LedColumn(column)
            led_column.pack(pady=(4, 0))
            self.x_leds.append(led_column)
            caption = tk.Label(column, text="", font="bench7", bg=CARD, fg=ACCENT_DARK)
            caption.pack()
            self.x_captions.append(caption)

        note_row = tk.Frame(card, bg=CARD)
        note_row.pack(fill="x", padx=12, pady=(6, 0))
        hint2 = tk.Label(note_row, text=t("di.hint_align"), font="bench8", bg=CARD, fg=SUB,
                          anchor="w", wraplength=250, justify="left")
        hint2.pack(side="left")
        self._bind_text(hint2, "di.hint_align")
        # 底部工具行：交互模式 + 硬件原值（诊断）折叠按钮
        tools_row = tk.Frame(card, bg=CARD)
        tools_row.pack(fill="x", padx=12, pady=(4, 0))
        self.x_mode_var = tk.StringVar(value=tr(self.engine.x_mode))
        self.x_mode_combo = ttk.Combobox(tools_row, textvariable=self.x_mode_var, width=8,
                                         state="readonly",
                                         values=[tr("保持开关"), tr("按住有效")])
        self._bind_combo_values(self.x_mode_combo, ("保持开关", "按住有效"))
        self._lang_binds.append(
            lambda c=self.x_mode_combo: c.configure(
                width={"zh": 8, "en": 7, "fr": 8, "pt": 8, "es": 8, "ar": 7}.get(
                    get_language(), 8)))
        interact_label = tk.Label(tools_row, text=t("di.interaction"), font="bench8",
                                  bg=CARD, fg=SUB)
        interact_label.pack(side="left", padx=(0, 4))
        self._bind_text(interact_label, "di.interaction")
        self.x_mode_combo.pack(side="left")
        self.x_mode_combo.bind("<<ComboboxSelected>>", self._on_x_mode)
        self.di_legend = tk.Label(card, text="", font="bench7", bg=CARD, fg=ACCENT_DARK,
                                  anchor="w", wraplength=250, justify="left")
        self.di_legend.pack(anchor="w", padx=12)

        # 辅助诊断折叠区：硬件 X 原值（按钮同样放在工具行右侧，避免被提示文字挤成 0 宽）
        self.hw_x_visible = False
        self.hw_x_btn = self._button(tools_row, t("di.hw_expand"), self._toggle_hw_x, width=13)
        # 双态按钮：切换语言时按折叠状态取词，并按语言微调宽度
        self._lang_binds.append(
            lambda: self.hw_x_btn.configure(
                text=t("di.hw_collapse" if self.hw_x_visible else "di.hw_expand"),
                width={"zh": 13, "en": 10, "fr": 18, "pt": 18, "es": 20, "ar": 12}.get(get_language(), 13)))
        self.hw_x_btn.pack(side="right")
        self.hw_x_frame = tk.Frame(card, bg=CARD)
        self.hw_x_labels = [tk.Label(self.hw_x_frame, text=f"X{i}: —",
                                     font="bench8", bg=CARD, fg=SUB)
                            for i in range(8)]
        for i, label in enumerate(self.hw_x_labels):
            label.grid(row=0, column=i, padx=6)
        if self.hw_x_visible:
            self.hw_x_frame.pack(anchor="w", padx=20)
            self.hw_x_btn.configure(text=t("di.hw_collapse"))

    def _toggle_hw_x(self) -> None:
        self.hw_x_visible = not self.hw_x_visible
        if self.hw_x_visible:
            self.hw_x_frame.pack(anchor="w", padx=20, pady=(0, 6))
            self.hw_x_btn.configure(text=t("di.hw_collapse"))
        else:
            self.hw_x_frame.pack_forget()
            self.hw_x_btn.configure(text=t("di.hw_expand"))

    # ---- 右上：模拟输入 --------------------------------------------------------
    def _build_analog_input_card(self, parent) -> None:
        card = self._card(parent)
        card.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=2)
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=12, pady=(4, 0))
        ai_title = tk.Label(head, text=t("ai.title"), font="bench12b",
                            bg=CARD, fg=INK, anchor="w")
        ai_title.pack(side="left")
        self._bind_text(ai_title, "ai.title")
        ai_hint = tk.Label(card, text=t("ai.hint"), font="bench8", bg=CARD, fg=SUB,
                           anchor="w")
        ai_hint.pack(anchor="w", padx=12)
        self._bind_text(ai_hint, "ai.hint")

        columns = tk.Frame(card, bg=CARD)
        columns.pack(fill="both", expand=True, padx=8, pady=(2, 3))
        self.ad_range_vars: list[tk.StringVar] = []
        self._ad_range_combos: list[ttk.Combobox] = []
        self.ad_bars: list[tk.Canvas] = []
        self.ad_value_labels: list[tk.Label] = []
        self.ad_target_labels: list[tk.Label] = []
        self.ad_entries: list[tk.Entry] = []
        self.ad_apply_buttons: list[tk.Button] = []
        self.ad_minus_buttons: list[tk.Button] = []
        self.ad_plus_buttons: list[tk.Button] = []
        for index in range(4):
            column = tk.Frame(columns, bg=CARD)
            column.grid(row=0, column=index, sticky="n", padx=6)
            columns.columnconfigure(index, weight=1)
            tk.Label(column, text=f"AD{index}", font="bench11b",
                     bg=CARD, fg=INK).pack(pady=(0, 2))
            range_var = tk.StringVar(value="0–10V")
            combo = ttk.Combobox(column, textvariable=range_var, width=7,
                                 state="readonly",
                                 values=[RANGE_LABELS["V10"], RANGE_LABELS["MA20"]])
            combo.pack()
            combo.bind("<<ComboboxSelected>>",
                       lambda e, i=index, v=range_var: self._on_ad_range(i, v))
            self.ad_range_vars.append(range_var)
            self._ad_range_combos.append(combo)

            bar_row = tk.Frame(column, bg=CARD)
            bar_row.pack(pady=(2, 0))
            minus = self._button(bar_row, t("btn.minus"),
                                 lambda i=index: self._on_ad_nudge(i, -1), padx=1)
            self._bind_text(minus, "btn.minus")
            minus.pack(side="left")
            bar = make_bar(bar_row)
            bar.pack(side="left", padx=2)
            plus = self._button(bar_row, t("btn.plus"),
                                lambda i=index: self._on_ad_nudge(i, +1), padx=1)
            self._bind_text(plus, "btn.plus")
            plus.pack(side="left")
            self.ad_bars.append(bar)
            self.ad_minus_buttons.append(minus)
            self.ad_plus_buttons.append(plus)

            value_label = tk.Label(column, text="—", font="bench11b",
                                   bg=CARD, fg=INK)
            value_label.pack(pady=(3, 0))
            self.ad_value_labels.append(value_label)
            target_label = tk.Label(column, text=t("ai.target_effective_none"),
                                    font="bench8", bg=CARD, fg=SUB,
                                    # 列宽约 77px：允许折行，否则中文"目标 0.00 / 生效 0.00"
                                    # 会被居中裁掉首字（屏幕上只剩"标 0.00 …"）
                                    wraplength=72, justify="center")
            target_label.pack()
            self.ad_target_labels.append(target_label)

            entry_row = tk.Frame(column, bg=CARD)
            entry_row.pack(pady=(2, 0), fill="x")
            # 按钮先占位（side=right），输入框再吃掉剩余宽度：
            # 反过来打包时列宽不足会把按钮压到只剩半个字（法/葡/西最明显）
            apply_button = self._button(entry_row, t("btn.apply"),
                                        lambda i=index: self._on_ad_entry(i), width=4,
                                        padx=4)
            self._bind_button(apply_button, "btn.apply",
                                 {"zh": 4, "en": 2, "fr": 2, "pt": 2, "es": 2, "ar": 2})
            apply_button.pack(side="right")
            entry = tk.Entry(entry_row, width=6, font="bench9", relief="solid",
                             bd=1, justify="center")
            entry.pack(side="left", fill="x", expand=True, padx=(0, 3))
            entry.bind("<Return>", lambda e, i=index: self._on_ad_entry(i))
            self.ad_entries.append(entry)
            self.ad_apply_buttons.append(apply_button)
            error_label = tk.Label(column, text="", font="bench7", bg=CARD, fg=RED,
                                   wraplength=110, justify="center")
            self._pending_ad_errors[index] = error_label
        self.ad_legend = tk.Label(card, text="", font="bench7", bg=CARD, fg=ACCENT_DARK,
                                  anchor="w", wraplength=340, justify="left")
        self.ad_legend.pack(anchor="w", padx=12)

    # ---- 左下：数字输出 --------------------------------------------------------
    def _build_digital_output_card(self, parent) -> None:
        card = self._card(parent)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(4, 2))
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=12, pady=(8, 0))
        do_title = tk.Label(head, text=t("do.title"), font="bench12b",
                            bg=CARD, fg=INK, anchor="w")
        do_title.pack(side="left")
        self._bind_text(do_title, "do.title")
        do_hint = tk.Label(card, text=t("do.hint"), font="bench8", bg=CARD, fg=SUB,
                           anchor="w", wraplength=250, justify="left")
        do_hint.pack(anchor="w", padx=12)
        self._bind_text(do_hint, "do.hint")
        tiles = tk.Frame(card, bg=CARD)
        tiles.pack(fill="x", padx=12, pady=(6, 0))
        self.y_tiles: list[tk.Label] = []
        self.y_leds: list[LedColumn] = []
        self.y_captions: list[tk.Label] = []
        for index in range(8):
            column = tk.Frame(tiles, bg=CARD)
            column.grid(row=0, column=index, padx=3, sticky="n")
            tiles.columnconfigure(index, weight=1)
            tile = tk.Label(column, text=f"Y{index}", font="bench10b",
                            width=4, relief="flat", bg="#F1F5F9", fg=SUB,
                            borderwidth=1, highlightthickness=1,
                            highlightbackground=BORDER, anchor="center", pady=4)
            tile.pack()
            self.y_tiles.append(tile)
            led_column = LedColumn(column)
            led_column.pack(pady=(4, 0))
            self.y_leds.append(led_column)
            caption = tk.Label(column, text="", font="bench7", bg=CARD, fg=ACCENT_DARK)
            caption.pack()
            self.y_captions.append(caption)
        self.do_legend = tk.Label(card, text="", font="bench7", bg=CARD, fg=ACCENT_DARK,
                                  anchor="w", wraplength=250, justify="left")
        self.do_legend.pack(anchor="w", padx=12, pady=(4, 0))
        do_note = tk.Label(card, text=t("do.note"), font="bench8", bg=CARD, fg=SUB,
                           anchor="w", wraplength=250, justify="left")
        do_note.pack(anchor="w", padx=12, pady=(2, 8))
        self._bind_text(do_note, "do.note")

    # ---- 右下：模拟输出 --------------------------------------------------------
    def _build_analog_output_card(self, parent) -> None:
        card = self._card(parent)
        card.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(4, 2))
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=12, pady=(4, 0))
        ao_title = tk.Label(head, text=t("ao.title"), font="bench12b",
                            bg=CARD, fg=INK, anchor="w")
        ao_title.pack(side="left")
        self._bind_text(ao_title, "ao.title")
        ao_hint = tk.Label(card, text=t("ao.hint"), font="bench8", bg=CARD, fg=SUB,
                           anchor="w", wraplength=250, justify="left")
        ao_hint.pack(anchor="w", padx=12)
        self._bind_text(ao_hint, "ao.hint")
        columns = tk.Frame(card, bg=CARD)
        columns.pack(fill="both", expand=True, padx=8, pady=(2, 3))
        self.da_range_vars: list[tk.StringVar] = []
        self._da_range_combos: list[ttk.Combobox] = []
        self.da_bars: list[tk.Canvas] = []
        self.da_value_labels: list[tk.Label] = []
        self.da_raw_labels: list[tk.Label] = []
        for index in range(2):
            column = tk.Frame(columns, bg=CARD)
            column.grid(row=0, column=index, sticky="n", padx=10)
            columns.columnconfigure(index, weight=1)
            tk.Label(column, text=f"DA{index + 1}", font="bench11b",
                     bg=CARD, fg=INK).pack(pady=(0, 2))
            range_var = tk.StringVar(value="0–10V")
            combo = ttk.Combobox(column, textvariable=range_var, width=7,
                                 state="readonly",
                                 values=[RANGE_LABELS["V10"], RANGE_LABELS["MA20"]])
            combo.pack()
            combo.bind("<<ComboboxSelected>>",
                       lambda e, i=index, v=range_var: self._on_da_range(i, v))
            self.da_range_vars.append(range_var)
            self._da_range_combos.append(combo)
            bar = make_bar(column)
            bar.pack(pady=(4, 0))
            self.da_bars.append(bar)
            value_label = tk.Label(column, text="—", font="bench11b",
                                   bg=CARD, fg=INK)
            value_label.pack(pady=(3, 0))
            self.da_value_labels.append(value_label)
            raw_label = tk.Label(column, text=f"{t('da.raw_none')} · {t(f'ao.alias{index}')}",
                                 font="bench7", bg=CARD, fg=SUB)
            raw_label.pack(pady=(1, 0))
            self.da_raw_labels.append(raw_label)
        self.da_legend = tk.Label(card, text="", font="bench7", bg=CARD, fg=ACCENT_DARK,
                                  anchor="w", wraplength=250, justify="left")
        self.da_legend.pack(anchor="w", padx=12)

    # ---- 底部操作栏 --------------------------------------------------------------
    def _build_bottom_bar(self) -> None:
        bar = self._card(self.root)
        bar.pack(side="bottom", fill="x", padx=10, pady=(4, 0))
        inner = tk.Frame(bar, bg=CARD)
        inner.pack(fill="x", padx=10, pady=6)
        self.start_btn = self._button(inner, t("btn.start"), self._on_start_stop,
                                      primary=True, width=12)
        self.start_btn.pack(side="left")
        self.apply_all_btn = self._button(inner, t("btn.apply_all"), self._on_apply_all, width=8)
        self._bind_button(self.apply_all_btn, "btn.apply_all",
                              {"zh": 8, "en": 10, "fr": 14, "pt": 12, "es": 12, "ar": 10})
        self.apply_all_btn.pack(side="left", padx=(10, 0))
        self.reset_btn = self._button(inner, t("btn.reset"), self._on_reset, width=12)
        self._bind_button(self.reset_btn, "btn.reset",
                          {"zh": 12, "en": 12, "fr": 13, "pt": 14, "es": 18, "ar": 12})
        self.reset_btn.pack(side="left", padx=(10, 0))
        self.export_btn = self._button(inner, t("btn.export_log"), self._on_export, width=12)
        self._bind_button(self.export_btn, "btn.export_log",
                           {"zh": 12, "en": 18, "fr": 19, "pt": 17, "es": 17, "ar": 12})
        self.export_btn.pack(side="left", padx=(10, 0))
        self.records_btn = self._button(inner, t("btn.records"), self._on_records,
                                        width=16)
        self._bind_button(self.records_btn, "btn.records",
                           {"zh": 16, "en": 16, "fr": 21, "pt": 20, "es": 20, "ar": 12})
        self.records_btn.pack(side="left", padx=(10, 0))
        self.settings_btn = self._button(inner, t("btn.settings"), self._on_settings,
                                         width=14)
        self._bind_button(self.settings_btn, "btn.settings",
                            {"zh": 14, "en": 28, "fr": 30, "pt": 26, "es": 26, "ar": 18})
        self.settings_btn.pack(side="left", padx=(10, 0))
        step_label = tk.Label(inner, text=t("label.step"), font="bench9", bg=CARD, fg=SUB)
        step_label.pack(side="right")
        self._bind_text(step_label, "label.step")
        self.step_var = tk.StringVar(value="5%")
        self.step_combo = ttk.Combobox(inner, textvariable=self.step_var, width=4,
                                       state="readonly",
                                       values=[f"{i}%" for i in range(1, 11)])
        self.step_combo.pack(side="right", padx=(0, 2))
        self.step_combo.bind("<<ComboboxSelected>>", self._on_step)
        step_hint = tk.Label(inner, text=t("label.step_hint"), font="bench8", bg=CARD,
                             fg=SUB)
        step_hint.pack(side="right")
        self._bind_text(step_hint, "label.step_hint")

    # ---- 日志区 ------------------------------------------------------------------
    def _build_log_area(self) -> None:
        area = self._card(self.root)
        area.pack(side="bottom", fill="x", padx=10, pady=(3, 6))
        head = tk.Frame(area, bg=CARD)
        head.pack(fill="x", padx=10, pady=(4, 0))
        self.bottom_title = tk.Label(head, text=t("log.title"), font="bench10b",
                                     bg=CARD, fg=INK)
        self.bottom_title.pack(side="left")
        self._bind_text(self.bottom_title, "log.title")
        self.script_name_var = tk.StringVar()
        self.script_label = tk.Label(head, textvariable=self.script_name_var,
                                     font="bench8", bg=CARD, fg=ACCENT_DARK, cursor="hand2")
        self.script_label.pack(side="left", padx=(10, 0))
        self.script_label.bind("<Button-1>", lambda event: ScriptDialog(self))
        self.script_load_btn = self._button(head, t("btn.load_script"), self._on_load_script,
                                            width=8)
        self._bind_button(self.script_load_btn, "btn.load_script",
                            {"zh": 8, "en": 13, "fr": 16, "pt": 17, "es": 15, "ar": 12})
        self.script_load_btn.pack(side="left", padx=(6, 0))
        self.script_start_btn = self._button(head, t("btn.script_start"), self._on_script,
                                             width=12)
        self.script_start_btn.pack(side="left", padx=(6, 0))
        self.data_age_label = tk.Label(head, text=t("status.data_age", age="—", refresh="—",
                                                    state="—"),
                                       font="bench8", bg=CARD, fg=SUB)
        self.data_age_label.pack(side="right")
        columns = ("time", "object", "value", "result")
        self.log_tree = ttk.Treeview(area, columns=columns, show="headings", height=3)
        for key, key_i18n, width in (("time", "log.col.time", 130),
                                     ("object", "log.col.object", 140),
                                     ("value", "log.col.value", 320),
                                     ("result", "log.col.result", 220)):
            self.log_tree.heading(key, text=t(key_i18n))
            self.log_tree.column(key, width=width, anchor="w")
            self._bind_heading(self.log_tree, key, key_i18n)
        self.log_tree.pack(fill="both", expand=True, padx=10, pady=(3, 6))

    def _build_customer_card(self, parent) -> None:
        """右侧客户寄存器面板：单位/量程注释列 + 归一化读数（PRD 布局 V0.6）。"""
        area = self._card(parent)
        area.pack(fill="both", expand=True)
        head = tk.Frame(area, bg=CARD)
        head.pack(fill="x", padx=10, pady=(6, 0))
        cust_title = tk.Label(head, text=t("cust.title"), font="bench10b",
                              bg=CARD, fg=INK)
        cust_title.pack(side="left")
        self._bind_text(cust_title, "cust.title")
        table = tk.Frame(area, bg=CARD)
        table.pack(fill="both", expand=True, padx=6, pady=(4, 0))
        columns = ("address", "name", "value", "unit", "access", "sample")
        self.customer_tree = ttk.Treeview(table, columns=columns, show="headings", height=12)
        col_keys = ("cust.col.address", "cust.col.name", "cust.col.value",
                    "cust.col.unit", "cust.col.access", "cust.col.sample")
        # 基准宽度只决定"申请宽度"（会影响左侧卡片分到的宽度），实际宽度靠 stretch
        # 在 1600 窗口里均分（约 1.4 倍）：基准给小，展示反而更宽，卡片也不再被挤。
        for key, key_i18n, width in zip(columns, col_keys,
                                        (56, 140, 80, 170, 80, 90)):
            self.customer_tree.heading(key, text=t(key_i18n))
            self.customer_tree.column(key, width=width, minwidth=width, anchor="w",
                                      stretch=True)
            self._bind_heading(self.customer_tree, key, key_i18n)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.customer_tree.yview)
        scroll.pack(side="right", fill="y")
        self.customer_tree.configure(yscrollcommand=scroll.set)
        self.customer_tree.pack(side="left", fill="both", expand=True)
        self.customer_tree.bind("<<TreeviewSelect>>", self._select_customer_row)

        self.watch_address = tk.StringVar()
        self.watch_name = tk.StringVar()
        self.watch_access = tk.StringVar(value=tr("读写"))
        self.send_address = tk.StringVar()
        self.send_value = tk.StringVar()
        add = tk.Frame(area, bg=CARD)
        add.pack(fill="x", pady=(2, 0))
        for key_i18n, variable, width in (("cust.label.watch_addr", self.watch_address, 7),
                                          ("cust.label.name", self.watch_name, 12)):
            label = tk.Label(add, text=t(key_i18n), bg=CARD)
            label.pack(side="left", padx=(0, 4))
            self._bind_text(label, key_i18n)
            ttk.Entry(add, textvariable=variable, width=width).pack(side="left", padx=(0, 8))
        access_label = tk.Label(add, text=t("cust.label.access"), bg=CARD)
        access_label.pack(side="left", padx=(0, 4))
        self._bind_text(access_label, "cust.label.access")
        self.watch_access_combo = ttk.Combobox(add, textvariable=self.watch_access,
                                               state="readonly", width=9,
                                               values=(tr("只读"), tr("只写"), tr("读写")))
        self._bind_combo_values(self.watch_access_combo, ("只读", "只写", "读写"))
        self.watch_access_combo.pack(side="left", padx=(0, 8))
        # Customer.TButton：内边距与输入框等高（截图验证对齐，勿改回默认）
        self.customer_buttons = []
        for key_i18n, command, padx in (("btn.add_watch", self._add_customer_watch, 0),
                                        ("btn.remove_watch", self._remove_customer_watch, 6),
                                        ("btn.import_csv", self._import_customer_csv, 0),
                                        ("btn.export_csv", self._export_customer_csv, 6)):
            button = ttk.Button(add, text=t(key_i18n), command=command,
                                style="Customer.TButton")
            self._bind_text(button, key_i18n)
            button.pack(side="left", padx=(padx, 0))
            self.customer_buttons.append(button)

        send = tk.Frame(area, bg=CARD)
        send.pack(fill="x", pady=(2, 0))
        send_addr_label = tk.Label(send, text=t("cust.label.send_addr"), bg=CARD)
        send_addr_label.pack(side="left", padx=(0, 4))
        self._bind_text(send_addr_label, "cust.label.send_addr")
        self.customer_send_combo = ttk.Combobox(send, textvariable=self.send_address,
                                                state="readonly", width=7)
        self.customer_send_combo.pack(side="left", padx=(0, 8))
        send_value_label = tk.Label(send, text=t("cust.label.send_value"), bg=CARD)
        send_value_label.pack(side="left", padx=(0, 4))
        self._bind_text(send_value_label, "cust.label.send_value")
        self.customer_value_entry = ttk.Entry(send, textvariable=self.send_value, width=10)
        self.customer_value_entry.pack(side="left", padx=(0, 8))
        self.customer_send_btn = ttk.Button(send, text=t("btn.send"), command=self._send_customer)
        self._bind_text(self.customer_send_btn, "btn.send")
        self.customer_send_btn.pack(side="left")
        self.customer_status = tk.Label(send, text=t("cust.status.hint"),
                                        bg=CARD, fg=SUB, anchor="w")
        self.customer_status.pack(side="left", fill="x", expand=True, padx=8)
        self._bind_text(self.customer_status, "cust.status.hint")

    def _restore_customer_watches(self) -> None:
        self._watch_config_key = "demo_watches" if self.demo else "customer_watches"
        default = [[260, "设定压力（演示）", "读写"]] if self.demo else []
        watches = self.ui_config.get(self._watch_config_key, default)
        if isinstance(watches, list):
            for entry in watches[:32]:
                if (isinstance(entry, list) and 2 <= len(entry) <= 3
                        and isinstance(entry[1], str)):
                    access = entry[2] if len(entry) == 3 and entry[2] in (
                        "只读", "只写", "读写") else "读写"
                    self.worker.submit(self.engine.set_customer_watch,
                                       entry[0], entry[1], access,
                                       # 演示档案的默认点位带英文显示名（数据不进记录）
                                       name_en="Setpoint (demo)"
                                       if self.demo and entry[1] == "设定压力（演示）" else None)

    def _add_customer_watch(self) -> None:
        address = self.watch_address.get().strip().upper().removeprefix("D")
        if not address.isascii() or not address.isdecimal() or len(address) > 4 or int(address) > 8511:
            self.customer_status.configure(text=t("cust.err.addr_range"), fg=RED)
            return
        name = self.watch_name.get().strip()
        if len(name) > 40:
            self.customer_status.configure(text=t("cust.err.name_len"), fg=RED)
            return
        self.worker.submit(self.engine.set_customer_watch, int(address), name,
                           untr(self.watch_access.get()))

    def _import_customer_csv(self) -> None:
        target = filedialog.askopenfilename(
            title=t("watch.import_title"),
            filetypes=[(t("filetype.csv_text"), "*.csv;*.txt"), (t("filetype.all"), "*.*")],
            parent=self.root)
        if not target:
            return   # 取消不影响现有列表
        try:
            text = Path(target).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            self.customer_status.configure(text=t("cust.err.read", error=exc), fg=RED)
            return
        self.worker.submit(self.engine.import_customer_watches_csv, text)

    def _export_customer_csv(self) -> None:
        if not self.engine.customer_watches:
            self.customer_status.configure(text=t("cust.err.empty"), fg=ORANGE)
            return
        target = filedialog.asksaveasfilename(
            title=t("watch.export_title"), defaultextension=".csv",
            initialfile=time.strftime("plcweave-watches-%Y%m%d-%H%M%S.csv"),
            filetypes=[(t("filetype.csv"), "*.csv")], parent=self.root)
        if not target:
            return   # 取消不影响现有列表
        self.worker.submit(self._export_customer_csv_task, target)

    def _export_customer_csv_task(self, target: str) -> None:
        """worker 线程：生成 CSV 文本并写文件；结果作为操作入日志。"""
        text, count = self.engine.export_customer_watches_csv()
        try:
            Path(target).write_text(text, encoding="utf-8-sig")
        except OSError as exc:
            self.engine.log_op("user", "客户寄存器", "导出监控CSV",
                               target=count, result="失败", reason=str(exc))
            self.worker.ui_events.put({"type": "command_error",
                                       "message": t("export.failed_msg", error=exc)})
            return
        self.engine.log_op("user", "客户寄存器", "导出监控CSV",
                           target=count, result="成功",
                           detail={"path": str(target)})

    def _remove_customer_watch(self) -> None:
        selected = self.customer_tree.selection()
        if selected:
            self.worker.submit(self.engine.remove_customer_watch, int(selected[0]))

    def _select_customer_row(self, _event=None) -> None:
        selected = self.customer_tree.selection()
        if selected and f"D{selected[0]}" in self.customer_send_combo["values"]:
            self.send_address.set(f"D{selected[0]}")

    def _send_customer(self) -> None:
        if self._customer_pending or self.customer_send_btn.instate(["disabled"]):
            return
        address = int(self.send_address.get()[1:])
        self._customer_pending = True
        self.customer_status.configure(text=t("cust.sending"), fg=SUB)
        self._update_customer_send_state()
        self.worker.submit(self.engine.write_customer_register, address, self.send_value.get(),
                           session_token=self.engine.session_token)

    def _update_customer_send_state(self) -> None:
        enabled = (self.engine.state in (State.SIMULATING, State.MANUAL) and bool(self.send_address.get())
                   and not self._customer_pending and not self._closing)
        self.customer_send_btn.configure(state="normal" if enabled else "disabled")

    @staticmethod
    def _customer_display(raw, kind: str) -> str:
        """按工程注释类型把原始值换算为工程量显示（未知类型原样显示）。"""
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return str(raw)
        if kind == "bar01":
            return f"{value / 10:.1f} bar"
        if kind == "pv_bar":
            return f"{(value + 12) // 25 / 10:.1f} bar"
        if kind == "hz":
            return f"{value / 100:.2f} Hz"
        if kind == "sec01":
            return f"{value / 10:.1f} s"
        return str(value)

    def _set_error(self, text: str | None = None, *, key: str | None = None) -> None:
        """记录错误原文（或 i18n key）；渲染时按当前语言翻译，切语言后提示不会留在旧语种。"""
        if key:
            self._error_raw = ("key", key)
        elif text:
            self._error_raw = ("msg", str(text))
        else:
            self._error_raw = None
        self._refresh_error_text()

    def _refresh_error_text(self) -> None:
        if self._error_raw is None:
            self._last_error_message = None
            return
        kind, value = self._error_raw
        self._last_error_message = t(value) if kind == "key" else msg(value)

    def _refresh_io_labels(self) -> None:
        """标注本次脚本启用的点位：描边 + 点位下小字 + 卡片图例（无脚本映射时全部清空）。

        映射来自工程适配器（engine.io_labels），中文/英文各一份；纯界面展示，
        不影响写入与记录。
        """
        if not hasattr(self, "x_captions"):
            return                     # 卡片尚未构建（__init__ 早期调用）
        labels = getattr(self.engine, "io_labels", None) or {}

        def info(point: str):
            item = labels.get(point)
            if not item:
                return None
            if get_language() == "zh":
                return item.get("zh", ""), item.get("tag_zh", "")
            return (item.get("en") or item.get("zh", ""),
                    item.get("tag_en") or item.get("tag_zh", ""))

        groups: dict[str, list[str]] = {"X": [], "Y": [], "AD": [], "DA": []}
        for index, button in enumerate(self.x_buttons):
            item = info(f"X{index}")
            button.configure(highlightbackground=ACCENT if item else BORDER)
            self.x_captions[index].configure(text=item[1] if item else "")
            if item:
                groups["X"].append(f"X{index} {item[0]}")
        for index, tile in enumerate(self.y_tiles):
            item = info(f"Y{index}")
            tile.configure(highlightbackground=ACCENT if item else BORDER)
            self.y_captions[index].configure(text=item[1] if item else "")
            if item:
                groups["Y"].append(f"Y{index} {item[0]}")
        for index in range(4):
            item = info(f"AD{index}")
            if item:
                groups["AD"].append(f"AD{index} {item[0]}")
        for index in range(2):
            item = info(f"DA{index}")
            if item:
                groups["DA"].append(f"DA{index + 1} {item[0]}")
        for legend, key in ((self.di_legend, "X"), (self.do_legend, "Y"),
                            (self.ad_legend, "AD"), (self.da_legend, "DA")):
            entries = groups[key]
            legend.configure(
                text=t("io.legend", items=" · ".join(entries)) if entries else "")

    def _project_adapter(self):
        """加载的测试脚本若带工程适配器（如压力工程），返回其映射；否则 None。"""
        script = self._loaded_script()
        if script is None:
            return None
        try:
            from .script_projects import project_adapter
            return project_adapter(script.resolve())
        except (OSError, ValueError):
            return None

    def _project_manual_inputs(self):
        adapter = self._project_adapter()
        if not adapter:
            return None
        return {row["physical"]: dict(row) for row in adapter["inputs"]}

    def _project_identity(self):
        adapter = self._project_adapter()
        return tuple(adapter.get("identity", ())) if adapter else ()

    def _render_customer_values(self) -> None:
        state = self.engine.state
        stale = state == State.FAULT
        choices = []
        ids = set()
        for row in self._customer_rows:
            key = str(row["address"])
            ids.add(key)
            access = row.get("access", "读写")
            write_range = row.get("write_range")
            if row.get("protected") or access == "只读" or write_range is None:
                access_text = tr("只读")
            else:
                access_text = f"{tr(access)} {write_range[0]}–{write_range[1]}"
                choices.append(f"D{key}")
            readable = "读" in access and not row.get("protected")
            note, kind = self.engine.customer_notes.get(row["address"], ("", ""))
            name = row["name"]
            # 非中文界面用适配器给的英文名/注释；缺译文回退中文原文
            if get_language() != "zh":
                name = self.engine.customer_names_en.get(row["address"], name)
                note = self.engine.customer_notes_en.get(row["address"], note)
            value = self._customer_display(row.get("value", "—"), kind)
            status = row.get("wall", "")[11:19] or t("cust.status_pending")
            if state == State.DISCONNECTED:
                value, status = "—", tr("未连接")
            elif not readable:
                value, status = "—", t("cust.status_write_only")
            elif stale or row.get("error"):
                status = t("cust.status_stale", error=row.get("error") or tr(status))
            values = (f"D{key}", name, value, note, access_text, status)
            if self.customer_tree.exists(key):
                self.customer_tree.item(key, values=values)
            else:
                self.customer_tree.insert("", "end", iid=key, values=values)
        for key in self.customer_tree.get_children():
            if key not in ids:
                self.customer_tree.delete(key)
        self.customer_send_combo.configure(values=choices)
        if self.send_address.get() not in choices:
            self.send_address.set(choices[0] if choices else "")
        self._update_customer_send_state()

    # ---- 配置 → 控件 ---------------------------------------------------------------
    def _apply_config_to_widgets(self) -> None:
        config = self.ui_config
        if config.get("port"):
            self.port_var.set(config["port"])
        if config.get("baud"):
            self.baud_var.set(str(config["baud"]))
        if config.get("format"):
            self.format_var.set(config["format"])
        if config.get("station") is not None:
            self.station_var.set(str(config["station"]))
        if config.get("version_address"):
            self.version_var.set(str(config["version_address"]))
        if config.get("x_mode"):
            # 旧配置可能存过某语言的显示词：先还原引擎原值再按当前语言显示
            self.x_mode_var.set(tr(untr(config["x_mode"])))
        self._refresh_script_label()
        self.worker.refresh_ms = config.get("refresh_ms", 250)

    # ---- 测试脚本加载/启动 -------------------------------------------------------
    def _loaded_script(self) -> Path | None:
        value = str(self.ui_config.get("test_script") or "")
        return Path(value) if value else None

    def _script_args(self, path: Path) -> list[str]:
        args_map = self.ui_config.get("script_args") or {}
        return list(args_map.get(str(path), []))

    def _refresh_script_label(self) -> None:
        script = self._loaded_script()
        self.script_name_var.set(
            t("script.loaded", name=script.name) if script else t("script.none"))

    def _on_load_script(self) -> None:
        current = self._loaded_script()
        path = filedialog.askopenfilename(
            parent=self.root, title=t("load_script.title"),
            initialdir=str(current.parent) if current else "",
            filetypes=[(t("filetype.python"), "*.py")])
        if not path:
            return   # 取消不影响自动保存
        script = Path(path).resolve()
        self.ui_config["test_script"] = str(script)
        self._save_ui_config()
        self._refresh_script_label()
        self.worker.submit(self.engine.log_op, "user", script.name,
                           "加载测试脚本", target=str(script), result="成功")

    def _on_script(self) -> None:
        if self.engine.state == State.SCRIPT_CONFIRM:
            scripts = self.worker.scripts
            self._show_script_completion({"exit_code": getattr(scripts, "exit_code", 1),
                "report_status": scripts.report_status, "generation": scripts.generation,
                "command_count": scripts.command_count})
            return
        script = self._loaded_script()
        if script is None or not script.is_file():
            self._set_error(key="script.err.select_first")
            self._on_load_script()
            return
        self.start_script(script, self._script_args(script))

    # ---- 事件处理：连接 -------------------------------------------------------------
    def _read_connection_widgets(self) -> dict:
        version_text = self.version_var.get().strip()
        if version_text.upper().startswith("D"):
            digits = version_text[1:]
        else:
            digits = version_text
        if not digits.isascii() or not digits.isdecimal() or len(digits) > 4:
            raise ValueError(t("conn.err.version"))
        version_address = int(digits)
        station_text = self.station_var.get().strip()
        try:
            station = int(station_text)
        except ValueError as exc:
            raise ValueError(t("conn.err.station")) from exc
        return {"port": self.port_var.get().strip(),
                "baud": int(self.baud_var.get()),
                "format": self.format_var.get(),
                "station": station,
                "version_address": version_address}

    def _on_connect(self) -> None:
        if self._sync_settings_to_engine():
            self.worker.submit(self._safe_call, self.engine.connect,
                               ok_message=t("conn.ok_message"))

    def _sync_settings_to_engine(self) -> bool:
        try:
            data = self._read_connection_widgets()
            self.engine.apply_settings(port=data["port"], baud=data["baud"],
                                       format=data["format"],
                                       station=data["station"],
                                       version_address=data["version_address"])
        except (ValueError, PermissionError) as exc:
            self._set_error(str(exc))
            return False
        self._persist_config(data)
        return True

    def _persist_config(self, data: dict) -> None:
        # ui_config 存引擎原值（中文），不能存下拉框显示词，否则换语言后回显错位
        self.ui_config.update({**data, "version_address": self.version_var.get().strip(),
                               "x_mode": untr(self.x_mode_var.get()),
                               "refresh_ms": self.worker.refresh_ms})
        self._save_ui_config()

    def _safe_call(self, function, ok_message=None) -> None:
        function()

    def _on_disconnect(self) -> None:
        self.worker.submit(self.engine.disconnect, "用户断开")

    def _on_start_stop(self) -> None:
        if self.engine.state in (State.SIMULATING, State.MANUAL):
            self.worker.submit(self._safe_call, self.engine.stop_simulation)
            return
        if not self.demo:
            confirmed = messagebox.askyesno(
                t("confirm.start_title"), t("confirm.start_body"), parent=self.root)
            if not confirmed:
                return
        # 已连接时复用现有连接（设置已锁定），仅未连接时同步本机设置
        if self.engine.state == State.DISCONNECTED:
            if not self._sync_settings_to_engine():
                return
        # 工程适配器项目：开始按钮直接进入"手动接管"，按适配器映射写注入寄存器。
        # 这类批量接口工程没有会话握手寄存器，组提交路径（接口档案+confirmed）
        # 不适用；未走本路由的（演示/无适配器）保持原有组提交行为。
        inputs = self._project_manual_inputs()
        if inputs is not None:
            self.worker.submit(self.engine.start_project_manual, inputs,
                               self._project_identity())
            return
        self.worker.submit(self._safe_call, self.engine.start_simulation)

    # ---- 事件处理：输入 -------------------------------------------------------------
    def _on_x_click(self, index: int) -> None:
        if self.engine.x_mode == "按住有效":
            return   # 按住模式由 Press/Release 事件处理
        target = 0 if self.engine.target_x[index] else 1
        self.worker.submit(self.engine.set_x, index, target)

    def _on_x_press(self, index: int) -> None:
        if self.engine.x_mode == "按住有效" and self.engine.state in (State.SIMULATING, State.MANUAL):
            self.worker.submit(self.engine.press_x, index)

    def _on_x_release(self, index: int) -> None:
        if self.engine.x_mode == "按住有效" and self.engine.state in (State.SIMULATING, State.MANUAL):
            self.worker.submit(self.engine.release_x, index)

    def _on_x_leave(self, index: int) -> None:
        # 失焦/鼠标捕获丢失：取消本机按住状态（PRD §5）。
        if self.engine.x_mode == "按住有效" and self.engine.state in (State.SIMULATING, State.MANUAL):
            if self.engine.target_x[index]:
                self.worker.submit(self.engine.release_x, index)

    def _on_x_mode(self, _event=None) -> None:
        mode = untr(self.x_mode_var.get())   # 显示词 → 引擎原值
        self.worker.submit(self.engine.set_x_mode, mode)
        self.ui_config["x_mode"] = mode
        self._save_ui_config()

    def _on_step(self, _event=None) -> None:
        text = self.step_var.get().strip("%")
        if text.isdigit():
            self.worker.submit(self.engine.set_step, int(text))

    def _on_ad_nudge(self, index: int, direction: int) -> None:
        self.worker.submit(self.engine.nudge_ad, index, direction)

    def _on_ad_entry(self, index: int) -> None:
        text = self.ad_entries[index].get()
        self.worker.submit(self.engine.set_ad_eng, index, text)

    def _on_ad_range(self, index: int, range_var: tk.StringVar) -> None:
        kind = "V10" if range_var.get() == RANGE_LABELS["V10"] else "MA20"
        self.worker.submit(self.engine.set_ad_range, index, kind)

    def _on_da_range(self, index: int, range_var: tk.StringVar) -> None:
        kind = "V10" if range_var.get() == RANGE_LABELS["V10"] else "MA20"
        self.worker.submit(self.engine.set_da_range, index, kind)

    def _on_apply_all(self) -> None:
        self.worker.submit(self.engine.apply_all)

    def _on_reset(self) -> None:
        self.worker.submit(self.engine.reset_inputs)

    def _on_export(self) -> None:
        session_id = self.store.current_id
        if session_id is None:
            messagebox.showinfo(t("export.info_title"), t("export.none"), parent=self.root)
            return
        default_name = f"plcweave-bench-{session_id}.zip"
        target = filedialog.asksaveasfilename(
            title=t("export.info_title"), defaultextension=".zip", initialfile=default_name,
            filetypes=[(t("filetype.zip"), "*.zip")], parent=self.root)
        if not target:
            return   # 取消不影响自动保存
        try:
            path = self.store.export_session(session_id, target)
            self.worker.submit(self.engine.log_op, "user", "日志导出", "导出本次日志",
                               target=str(path), result="成功",
                               detail={"note": "会话尚未结束，导出为当前快照"}
                               if self.engine.state == State.SIMULATING else None)
            messagebox.showinfo(t("export.done_title"), t("export.done", path=path),
                                parent=self.root)
        except (OSError, ValueError) as exc:
            messagebox.showerror(t("export.failed_title"), msg(str(exc)), parent=self.root)

    # ---- 对话框 -------------------------------------------------------------------
    def start_script(self, path: str | Path, args: list[str]) -> None:
        if self.engine.state in (State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM):
            return
        self._set_error()
        text = self.version_var.get().strip().upper().removeprefix("D")
        if text and (not text.isascii() or not text.isdecimal() or len(text) > 4):
            self._set_error(key="script.err.addr_range")
            return
        self.worker.submit(self.worker.scripts.start, path, args, int(text) if text else None)

    def _show_script_completion(self, event: dict) -> None:
        if self._closing:
            return
        code = event["exit_code"]
        outcome = t("script.done_ok") if code == 0 else t("script.done_error")
        report = t("script.report", status=event["report_status"]) if event.get("report_status") else ""
        connected = self.worker.scripts.connection is not None
        handoff = t("script.handoff_connected") if connected else t("script.handoff_failed")
        result = messagebox.showinfo(t("script.done_title"),
            t("script.done_body", outcome=outcome, code=code, report=report,
              count=event["command_count"], handoff=handoff), parent=self.root)
        if result == "ok":
            self.worker.submit(self.worker.scripts.acknowledge, event["generation"])

    def _on_settings(self) -> None:
        if self.engine.state in (State.DISCONNECTED, State.FAULT):
            SettingsDialog(self)

    def _on_records(self) -> None:
        RecordsDialog(self)

    # ---- 窗口关闭 --------------------------------------------------------------------
    def _on_close(self) -> None:
        if self._closing:
            return
        if self.engine.state in (State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM):
            if not messagebox.askyesno(t("close.script_title"), t("close.script_body"),
                                       parent=self.root):
                return
        elif self.engine.state in (State.SIMULATING, State.MANUAL):
            detail = (t("close.manual_detail") if self.engine.state == State.MANUAL
                      else t("close.sim_detail"))
            if not messagebox.askyesno(
                    t("close.title"),
                    t("close.confirm", detail=detail), parent=self.root):
                return
        self._closing = True
        self.root.after_cancel(self._event_job)
        self._update_customer_send_state()
        self.root.withdraw()
        self._save_ui_config()
        while True:
            try:
                self.worker.commands.get_nowait()
            except queue.Empty:
                break
        self.worker.submit(self._disconnect_on_close)
        self._wait_for_worker_close()

    def _disconnect_on_close(self) -> None:
        try:
            self.worker.scripts.close()
        finally:
            try:
                self.engine.disconnect("关闭窗口结束")
            finally:
                self.worker.stop()

    def _wait_for_worker_close(self) -> None:
        if self.worker.is_alive():
            self.root.after(50, self._wait_for_worker_close)
        else:
            self.root.destroy()

    # ---- UI 事件泵 ---------------------------------------------------------------
    def _process_events(self) -> None:
        while True:
            try:
                event = self.worker.ui_events.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_ui_event(event)
            except Exception:
                # 单个事件的渲染/处理失败不得拖死整个界面事件循环，
                # 否则状态、参数与监控表全部停止刷新（表象即"无法操作"）。
                import traceback
                traceback.print_exc()
        self._update_status_line()
        self._event_job = self.root.after(50, self._process_events)

    def _handle_ui_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "script_connection":
            settings = event["settings"]
            self.port_var.set(settings.get("port", ""))
            self.baud_var.set(str(settings.get("baud", 9600)))
            self.format_var.set(f"{settings.get('bytesize', 8)}{settings.get('parity', 'N')}{settings.get('stopbits', 1)}")
            self.station_var.set(str(settings.get("station", 1)))
            address = self.engine.settings["version_address"]
            if address is not None:
                self.version_var.set(f"D{address}")
        elif kind == "script_targets":
            for index, entry in enumerate(self.ad_entries):
                raw = self.engine.target_ad_raw[index]
                entry.configure(state=tk.NORMAL)
                entry.delete(0, "end")
                entry.insert(0, eng_text(raw, self.engine.ad_range[index]) if 0 <= raw <= FULL_RAW else str(raw))
                entry.configure(state=tk.DISABLED)
        elif kind == "script_complete":
            self._show_script_completion(event)
        elif kind == "op":
            operation = event["event"]
            self._append_log(operation)
            self._clear_ad_error_from_event(operation)
            if operation["action"] == "发送客户寄存器" and operation["result"] != "待发送":
                self._customer_pending = False
                status = f"{tr(operation['object'])} {tr(operation['result'])}"
                if operation.get("effective") is not None:
                    status += f" {operation['effective']}"
                if operation.get("reason"):
                    status += f"  {tr(operation['reason'])}"
                self.customer_status.configure(text=status,
                    fg=GREEN if operation["result"] == "已读回" else RED)
                self._update_customer_send_state()
            elif operation["action"] in ("添加或更新寄存器监控", "移除寄存器监控"):
                self.customer_status.configure(
                    text=t("cust.updated", obj=tr(operation["object"])), fg=SUB)
            elif operation["action"] == "导入监控CSV":
                detail = operation.get("detail") or {}
                skipped = detail.get("skipped") or []
                status = t("cust.imported", count=operation["target"])
                if skipped:
                    reasons = "；".join(
                        t("cust.skip_line", line=item['line'], reason=tr(item['reason']))
                        for item in skipped[:3])
                    status += t("cust.import_skipped", count=len(skipped), reasons=reasons)
                self.customer_status.configure(
                    text=status, fg=SUB if not skipped else ORANGE)
            elif operation["action"] == "导出监控CSV":
                if operation["result"] == "成功":
                    self.customer_status.configure(
                        text=t("cust.exported", count=operation["target"]), fg=GREEN)
                # 失败由 command_error 分支显示原因
        elif kind == "state":
            self._last_state = event.get("state", self.engine.state)
            self.refresh_permissions()
            self._refresh_io_labels()
            self._update_version_label(event)
            self._render_customer_values()
        elif kind == "customer_values":
            self._customer_rows = event["rows"]
            self._render_customer_values()
            watches = [[row["address"], row["name"], row.get("access", "读写")]
                       for row in self._customer_rows]
            if watches != self.ui_config.get(self._watch_config_key):
                self.ui_config[self._watch_config_key] = watches
                self._save_ui_config()
        elif kind == "values":
            self._stale = bool(event.get("stale"))
            self.refresh_values()
        elif kind in ("error", "command_error", "store_error"):
            message = event.get("message")
            self._set_error(message) if message else self._set_error(key="status.unknown_error")
            self.customer_status.configure(text=self._last_error_message, fg=RED)
            if kind in ("command_error", "store_error"):
                self._customer_pending = False
                self._update_customer_send_state()
        else:
            pass

    def _localize_value(self, value) -> str:
        """目标/生效值里的中文监控名换成当前语言显示名；其余走数据词表 tr()。

        引擎与落盘记录始终保存中文名，这里只在显示边界替换。
        """
        if not isinstance(value, str) or not value:
            return "" if value is None else str(value)
        if get_language() != "zh":
            for address, english in self.engine.customer_names_en.items():
                watch = self.engine.customer_watches.get(address)
                name = getattr(watch, "name", watch)
                if name == value:
                    return english
        return msg(value)

    def _rebuild_log(self) -> None:
        """语言切换后按当前译文重放日志（日志行是插入式，不重建就会留旧语言）。"""
        if not hasattr(self, "log_tree"):
            return
        self.log_tree.delete(*self.log_tree.get_children())
        for event in self.engine._events[-200:]:
            self._append_log(event)

    def _append_log(self, event: dict) -> None:
        time_text = (event.get("wall") or "")[11:23]
        target = event.get("target")
        effective = event.get("effective")
        unit = event.get("unit") or ""
        if isinstance(target, dict):
            target_text = json.dumps(target, ensure_ascii=False)
        elif isinstance(target, float):
            target_text = f"{target:.2f}{unit}"
        else:
            target_text = "—" if target is None else self._localize_value(target) + unit
        if isinstance(effective, dict):
            effective_text = json.dumps(effective, ensure_ascii=False)
        elif isinstance(effective, float):
            effective_text = f"{effective:.2f}{unit}"
        else:
            effective_text = "—" if effective is None else self._localize_value(effective) + unit
        result = event.get("result") or ""
        reason = event.get("reason")
        result_text = msg(result) if not reason else f"{msg(result)} · {msg(reason)}"
        if isinstance(target, dict) or isinstance(effective, dict):
            value_text = f"{target_text} / {effective_text}"
        else:
            value_text = f"{target_text} / {effective_text}"
        self.log_tree.insert("", "end", values=(time_text, tr(event.get("object")),
                                                value_text, result_text))
        if self.log_tree.get_children():
            self.log_tree.see(self.log_tree.get_children()[-1])
        # 日志最多显示最近 200 行，避免内存膨胀（完整记录在磁盘）
        children = self.log_tree.get_children()
        if len(children) > 200:
            self.log_tree.delete(children[0])

    def _clear_ad_error_from_event(self, event: dict) -> None:
        obj = event.get("object") or ""
        if obj.startswith("AD") and obj[2:].isdigit():
            index = int(obj[2:])
            if index >= 4:
                return
            result = event.get("result")
            label = self._pending_ad_errors[index]
            if result in ("拒绝", "失败"):
                # 非法值/超范围就地报错（PRD §6.3），不发送
                label.configure(text=f"{tr(result)}: {msg(event.get('reason'))}"[:80])
                label.pack()
            else:
                label.configure(text="")
                label.pack_forget()

    def _update_version_label(self, event: dict | None = None) -> None:
        engine = self.engine
        if engine.state == State.FAULT:
            self.version_label.configure(text=t("version.invalid"), fg=ORANGE)
        elif engine.state != State.DISCONNECTED and engine.version_value is not None and engine.version_address is not None:
            self.version_label.configure(
                text=t("version.from", value=engine.version_value,
                       address=engine.version_address),
                fg=INK)
        elif engine.state in (State.CONNECTED, State.SIMULATING, State.STARTING):
            self.version_label.configure(text=t("version.unread"), fg=RED)
        else:
            self.version_label.configure(text=t("version.none"), fg=SUB)

    # ---- 状态/权限刷新 ---------------------------------------------------------------
    def refresh_permissions(self) -> None:
        state = self.engine.state
        disconnected_like = state in (State.DISCONNECTED, State.FAULT)
        connected = state in (State.CONNECTED, State.MANUAL)
        simulating = state == State.SIMULATING
        busy = state in (State.CONNECTING, State.STARTING, State.ENDING,
                         State.SCRIPT_RUNNING, State.SCRIPT_CONFIRM)

        # 连接区
        for widget in (self.port_combo, self.baud_combo, self.format_combo,
                       self.station_entry, self.version_entry):
            widget.configure(state=tk.NORMAL if disconnected_like else tk.DISABLED)
        self.connect_btn.configure(
            state=tk.NORMAL if disconnected_like and not busy else tk.DISABLED)
        self.disconnect_btn.configure(
            state=tk.NORMAL if (connected or simulating or state == State.FAULT)
            else tk.DISABLED)

        # 开始/结束（文字与宽度随语言调整）
        start_width = BTN_WIDTHS["start"].get(get_language(), 12)
        if simulating or state == State.MANUAL:
            self.start_btn.configure(
                text=t("btn.stop_manual") if state == State.MANUAL else t("btn.stop_sim"),
                state=tk.NORMAL, width=start_width)
        elif busy:
            self.start_btn.configure(state=tk.DISABLED, width=start_width,
                                     text=t("btn.stop_sim") if state == State.ENDING
                                     else t("btn.start"))
        else:
            self.start_btn.configure(text=t("btn.start"), width=start_width,
                                     state=tk.NORMAL if disconnected_like or connected
                                     else tk.DISABLED)

        # 输入控件：未连接/已连接可编辑待应用值；仿真中可提交
        editable = disconnected_like or state == State.CONNECTED or simulating
        for index, button in enumerate(self.x_buttons):
            allowed = editable or (state == State.MANUAL and f"X{index}" in self.engine.manual_inputs)
            button.configure(state=tk.NORMAL if allowed else tk.DISABLED)
        for index in range(4):
            mapped = state == State.MANUAL and f"D{8030+index}" in self.engine.manual_inputs
            for widget in (self.ad_minus_buttons[index], self.ad_plus_buttons[index], self.ad_apply_buttons[index]):
                widget.configure(state=tk.NORMAL if simulating or mapped else tk.DISABLED)
            self.ad_entries[index].configure(state=tk.NORMAL if editable or mapped else tk.DISABLED)
        for combo in (self.step_combo, self.x_mode_combo):
            combo.configure(state="readonly" if editable or (state == State.MANUAL and self.engine.manual_inputs) else tk.DISABLED)
        # 量程下拉始终可切（本机显示换算，不写 PLC）
        for widget in self._ad_range_combos + self._da_range_combos:
            widget.configure(state="readonly")

        mapped = state == State.MANUAL and bool(self.engine.manual_inputs)
        self.apply_all_btn.configure(state=tk.NORMAL if simulating or mapped else tk.DISABLED)
        self.reset_btn.configure(state=tk.NORMAL if simulating or mapped else tk.DISABLED)
        self.export_btn.configure(
            state=tk.NORMAL if (self.store.current_id and state in (
                State.SIMULATING, State.MANUAL, State.SCRIPT_RUNNING)) else tk.DISABLED)
        self.records_btn.configure(state=tk.NORMAL)
        self.settings_btn.configure(state=tk.NORMAL if disconnected_like else tk.DISABLED)
        confirming = state == State.SCRIPT_CONFIRM
        self.script_start_btn.configure(
            text=t("btn.script_confirm") if confirming else t("btn.script_start"),
            width=BTN_WIDTHS["script_start"].get(get_language(), 12),
            state=tk.DISABLED if busy and not confirming else tk.NORMAL)
        self.script_load_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.script_label.configure(fg=ORANGE if confirming else ACCENT_DARK)
        self._update_customer_send_state()

    def refresh_values(self, initial: bool = False) -> None:
        engine = self.engine
        stale = self._stale
        # X：按钮显示目标样式，小灯显示生效
        for index in range(8):
            target = engine.target_x[index]
            self.x_buttons[index].configure(
                bg="#DBEAFE" if target else "#EFF6FF",
                fg=ACCENT_DARK if target else "#64748B")
            effective = engine.effective_x[index]
            if effective is None:
                # 无输入映射的工程：小灯回落显示 FC02 直读的真实硬件 X 状态
                hardware = engine.hw_x[index]
                if hardware is None:
                    self.x_leds[index].update_state("unknown", stale=stale)
                else:
                    self.x_leds[index].update_state("on" if hardware else "off", stale=stale)
            else:
                self.x_leds[index].update_state("on" if effective else "off", stale=stale)
        # 硬件 X 诊断
        for index, label in enumerate(self.hw_x_labels):
            value = engine.hw_x[index]
            label.configure(text=f"X{index}: {'—' if value is None else value}")
        # Y
        for index in range(8):
            value = engine.y_bits[index]
            tile = self.y_tiles[index]
            if value is None:
                tile.configure(fg=SUB, bg="#F1F5F9")
                self.y_leds[index].update_state("unknown", stale=stale)
            else:
                tile.configure(fg="white" if value else SUB,
                               bg=GREEN if value else "#F1F5F9")
                self.y_leds[index].update_state("on" if value else "off", stale=stale)
        # AD
        for index in range(4):
            kind = engine.ad_range[index]
            unit = UNIT_LABELS[kind]
            effective_raw = engine.effective_ad[index]
            if effective_raw is None:
                set_bar(self.ad_bars[index], None, "", stale=stale)
                self.ad_value_labels[index].configure(text="—", fg=SUB)
                target_raw = engine.target_ad_raw[index]
                self.ad_target_labels[index].configure(
                    text=t("ai.target_effective", target=eng_text(target_raw, kind),
                           effective="—"), fg=SUB)
            else:
                fraction = effective_raw / FULL_RAW
                set_bar(self.ad_bars[index], fraction,
                        f"{eng_text(effective_raw, kind)}", stale=stale)
                self.ad_value_labels[index].configure(
                    text=f"{eng_text(effective_raw, kind)} {unit}",
                    fg=ORANGE if stale else INK)
                target_raw = engine.target_ad_raw[index]
                target_text = (eng_text(target_raw, kind) if 0 <= target_raw <= FULL_RAW
                               else t("ai.raw_over", raw=target_raw))
                self.ad_target_labels[index].configure(
                    text=t("ai.target_effective", target=target_text,
                           effective=eng_text(effective_raw, kind)), fg=SUB)
        # DA
        for index in range(2):
            kind = engine.da_range[index]
            unit = UNIT_LABELS[kind]
            raw = engine.da_raw[index]
            if raw is None:
                set_bar(self.da_bars[index], None, "", stale=stale)
                self.da_value_labels[index].configure(text="—", fg=SUB)
                self.da_raw_labels[index].configure(text=t("da.raw_none"))
            else:
                set_bar(self.da_bars[index], raw / FULL_RAW,
                        eng_text(raw, kind), stale=stale)
                self.da_value_labels[index].configure(
                    text=f"{eng_text(raw, kind)} {unit}", fg=ORANGE if stale else INK)
                self.da_raw_labels[index].configure(
                    text=t("da.raw_alias", raw=raw, alias=t(f"ao.alias{index}")))

    def _update_status_line(self) -> None:
        engine = self.engine
        self.status_label.configure(text=self._status_text(),
                                    fg=STATE_COLORS.get(engine.state, SUB))
        age = "—"
        block = engine.block_times.get("y")
        if block is not None:
            age = t("status.age_ago", seconds=f"{time.time() - block:.1f}")
        refresh = "—" if engine.last_poll_ms is None else f"{engine.last_poll_ms:.0f}ms"
        extra = ""
        if engine.in_flight is not None:
            extra = t("status.in_flight", group=engine.in_flight)
        if self.store.write_error:
            extra += f"   ⚠ {self.store.write_error}"
        if self._last_error_message:
            extra += f"   ⚠ {self._last_error_message}"
        self.data_age_label.configure(
            text=t("status.data_age", age=age, refresh=refresh,
                   state=tr(engine.state)) + extra)


STATE_COLORS = {
    State.DISCONNECTED: SUB,
    State.CONNECTING: ORANGE,
    State.CONNECTED: ACCENT,
    State.STARTING: ORANGE,
    State.SIMULATING: GREEN,
    State.ENDING: ORANGE,
    State.FAULT: RED,
    State.SCRIPT_RUNNING: ORANGE,
    State.SCRIPT_CONFIRM: ORANGE,
    State.MANUAL: GREEN,
}


def eng_text(raw: int | None, kind: str) -> str:
    from .engine import eng_from_raw
    if raw is None:
        return "—"
    return f"{eng_from_raw(raw, kind):.2f}"


# ---------------------------------------------------------------------------
# 对话框：版本与接口设置
# ---------------------------------------------------------------------------
class ScriptDialog(tk.Toplevel):
    def __init__(self, app: BenchApp):
        super().__init__(app.root)
        self.app = app
        self.title(t("dlg.script_title"))
        self.transient(app.root)
        self.configure(bg=CARD)
        priority = Path(__file__).resolve().parents[3] / "project/l01s-water-standard/run_hil_v3.py"
        default = str(priority) if not app.demo and priority.is_file() else ""
        self.path = tk.StringVar(value=app.ui_config.get("test_script") or default)
        ttk.Label(self, text=t("dlg.script.label")).grid(row=0, column=0, padx=10, pady=10)
        ttk.Entry(self, textvariable=self.path, width=65).grid(row=0, column=1, padx=5)
        ttk.Button(self, text=t("dlg.script.choose"), command=self._choose).grid(row=0, column=2, padx=10)
        ttk.Label(self, text=t("dlg.script.args")).grid(row=1, column=0, padx=10)
        self.arguments = tk.Text(self, height=4, width=65, font="bench9")
        self.arguments.grid(row=1, column=1, columnspan=2, padx=10, pady=4)
        self.arguments.insert("1.0", "\n".join(app._script_args(Path(self.path.get()))))
        ttk.Button(self, text=t("dlg.script.run"), command=self._start).grid(row=2, column=2, padx=10, pady=10)
        self.error = ttk.Label(self, text="")
        self.error.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 10))
        ttk.Label(self, text=t("dlg.script.note")
                  ).grid(row=4, column=0, columnspan=3, padx=10, pady=(0, 10))

    def _choose(self):
        path = filedialog.askopenfilename(parent=self, title=t("dlg.script.pick_title"),
                                          filetypes=[(t("filetype.python"), "*.py")])
        if path:
            self.path.set(path)
            self.arguments.delete("1.0", "end")
            self.arguments.insert("1.0", "\n".join(self.app._script_args(Path(path))))

    def _start(self):
        path = Path(self.path.get()).expanduser()
        if not path.is_file() or path.suffix.lower() != ".py":
            self.error.configure(text=t("dlg.script.err"))
            return
        arguments = [line for line in self.arguments.get("1.0", "end").splitlines() if line]
        resolved = str(path.resolve())
        self.app.ui_config["test_script"] = resolved
        self.app.ui_config.setdefault("script_args", {})[resolved] = arguments
        self.app._save_ui_config()
        self.app._refresh_script_label()
        self.app.start_script(path, arguments)
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: BenchApp) -> None:
        super().__init__(app.root)
        self.app = app
        self.title(t("dlg.settings_title"))
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app.root)
        frame = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text=t("dlg.settings.version_label"),
                 font="bench9", bg=CARD, fg=INK).grid(row=0, column=0, sticky="w",
                                                       padx=10, pady=(10, 2))
        self.version_entry = tk.Entry(frame, width=10, font="bench9")
        self.version_entry.grid(row=0, column=1, sticky="w", padx=10)
        self.version_entry.insert(0, app.version_var.get())

        tk.Label(frame, text=t("dlg.settings.profile"), font="bench9", bg=CARD,
                 fg=INK).grid(row=1, column=0, sticky="w", padx=10, pady=(8, 2))
        self.profile_var = tk.StringVar(value=app.ui_config.get("profile_path", ""))
        tk.Entry(frame, textvariable=self.profile_var, width=42,
                 font="bench8").grid(row=1, column=1, sticky="w", padx=10)
        self._button(frame, t("dlg.settings.pick"), self._pick_profile).grid(row=1, column=2, padx=(0, 10))

        self.profile_info = tk.Label(frame, text=self._profile_text(), font="bench8",
                                     bg=CARD, fg=SUB, justify="left", wraplength=380)
        self.profile_info.grid(row=2, column=0, columnspan=3, sticky="w", padx=10)

        tk.Label(frame, text=t("dlg.settings.refresh"), font="bench9", bg=CARD, fg=INK).grid(
            row=3, column=0, sticky="w", padx=10, pady=(8, 2))
        self.refresh_var = tk.StringVar(
            value={250: "250ms", 500: "500ms", 1000: "1000ms"}.get(
                app.worker.refresh_ms, "250ms"))
        ttk.Combobox(frame, textvariable=self.refresh_var, width=8, state="readonly",
                     values=list(REFRESH_CHOICES)).grid(row=3, column=1, sticky="w")

        tk.Label(frame, text=t("dlg.settings.storage"), font="bench9", bg=CARD, fg=INK).grid(
            row=4, column=0, sticky="w", padx=10, pady=(8, 2))
        tk.Label(frame, text=app.store.storage_path(), font="bench7", bg=CARD,
                 fg=SUB, wraplength=330, justify="left").grid(row=4, column=1,
                                                              columnspan=2, sticky="w")
        self._button(frame, t("dlg.settings.open_dir"), self._open_dir).grid(row=5, column=1,
                                                                             sticky="w", padx=10,
                                                                             pady=(2, 10))
        self._button(frame, t("dlg.settings.save"), self._save, primary=True).grid(
            row=5, column=2, sticky="e", padx=(0, 10), pady=(2, 10))

    def _button(self, parent, text, command, primary=False) -> tk.Button:
        return tk.Button(parent, text=text, command=command, font="bench9",
                         bg=ACCENT if primary else "white",
                         fg="white" if primary else INK,
                         relief="flat", bd=1, padx=10, pady=2, cursor="hand2")

    def _profile_text(self) -> str:
        profile = self.app.profile
        gate = t("profile.confirmed") if profile.confirmed else t("profile.unconfirmed")
        return t("profile.current", name=profile.name, status=profile.status, gate=gate,
                 digest=profile.digest()[:16], note=profile.note)

    def _pick_profile(self) -> None:
        target = filedialog.askopenfilename(title=t("dlg.settings.pick_title"),
                                            filetypes=[(t("filetype.json"), "*.json")],
                                            parent=self)
        if target:
            self.profile_var.set(target)

    def _save(self) -> None:
        app = self.app
        text = self.version_entry.get().strip()
        if text:
            app.version_var.set(text if text.upper().startswith("D") else f"D{text}")
        try:
            digits = text[1:] if text.upper().startswith("D") else text
            address = int(digits) if digits else None
            app.engine.apply_settings(version_address=address)
        except (ValueError, PermissionError) as exc:
            messagebox.showerror(t("dlg.settings.err_version_title"), msg(str(exc)), parent=self)
            return
        path = self.profile_var.get().strip()
        if path:
            try:
                profile = load_profile(path)
            except ValueError as exc:
                messagebox.showerror(t("dlg.settings.err_profile_title"), msg(str(exc)), parent=self)
                return
            app.profile = profile
            app.engine.profile = profile
            app.ui_config["profile_path"] = path
            app.worker.submit(app.engine._emit_customer_values)
        refresh_text = self.refresh_var.get()
        app.worker.refresh_ms = REFRESH_CHOICES.get(refresh_text, 250)
        app.ui_config["refresh_ms"] = app.worker.refresh_ms
        app._save_ui_config()
        messagebox.showinfo(t("dlg.settings.saved_title"), t("dlg.settings.saved"), parent=self)
        self.destroy()

    def _open_dir(self) -> None:
        import subprocess
        path = self.app.store.storage_path()
        try:
            subprocess.Popen(["explorer", path])
        except OSError as exc:
            messagebox.showerror(t("dlg.settings.err_open_title"), msg(str(exc)), parent=self)


# ---------------------------------------------------------------------------
# 对话框：调试记录
# ---------------------------------------------------------------------------
class RecordsDialog(tk.Toplevel):
    def __init__(self, app: BenchApp) -> None:
        super().__init__(app.root)
        self.app = app
        self.title(t("dlg.records_title"))
        self.configure(bg=BG)
        self.geometry("880x480")
        self.transient(app.root)
        frame = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("id", "started", "ended", "status", "reason")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        # reason 列放"断开结束（关闭窗口结束）"这类复合串的英文译文（最长约 42 字符）
        for key, key_i18n, width in (("id", "rec.col.id", 190), ("started", "rec.col.started", 146),
                                     ("ended", "rec.col.ended", 146), ("status", "rec.col.status", 80),
                                     ("reason", "rec.col.reason", 255)):
            self.tree.heading(key, text=t(key_i18n))
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        tk.Label(frame,
                 text=t("rec.note", path=app.store.storage_path()),
                 font="bench8", bg=CARD, fg=SUB).pack(anchor="w", padx=10)
        buttons = tk.Frame(frame, bg=CARD)
        buttons.pack(fill="x", padx=10, pady=(6, 10))
        tk.Button(buttons, text=t("btn.detail"), font="bench9", command=self._detail,
                  relief="flat", bg="white", padx=10, pady=2).pack(side="left")
        tk.Button(buttons, text=t("btn.export_selected"), font="bench9", command=self._export,
                  relief="flat", bg="white", padx=10, pady=2).pack(side="left", padx=8)
        tk.Button(buttons, text=t("btn.refresh"), font="bench9", command=self._reload,
                  relief="flat", bg="white", padx=10, pady=2).pack(side="left")
        self._reload()

    def _reload(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for summary in self.app.store.list_sessions():
            self.tree.insert("", "end", iid=summary["session_id"], values=(
                summary["session_id"], (summary.get("started_wall") or "")[:19],
                (summary.get("ended_wall") or "")[:19] or "—",
                msg(summary.get("status")), msg(summary.get("end_reason")) or "—"))

    def _selected(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _detail(self) -> None:
        session_id = self._selected()
        if session_id:
            SessionDetailDialog(self.app, session_id)

    def _export(self) -> None:
        session_id = self._selected()
        if not session_id:
            return
        target = filedialog.asksaveasfilename(
            title=t("rec.export_title"), defaultextension=".zip",
            initialfile=f"plcweave-bench-{session_id}.zip",
            filetypes=[(t("filetype.zip"), "*.zip")], parent=self)
        if not target:
            return
        try:
            path = self.app.store.export_session(session_id, target)
            messagebox.showinfo(t("export.done_title"), t("export.done", path=path), parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror(t("export.failed_title"), msg(str(exc)), parent=self)


class SessionDetailDialog(tk.Toplevel):
    def __init__(self, app: BenchApp, session_id: str) -> None:
        super().__init__(app.root)
        self.title(t("dlg.detail_title", id=session_id))
        self.configure(bg=BG)
        self.geometry("820x560")
        self.transient(app.root)
        frame = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        summary = next((item for item in app.store.list_sessions()
                        if item["session_id"] == session_id), {})
        info = "\n".join(
            f"{key}: {msg(value) if isinstance(value, str) else value}" for key, value in summary.items()
            if key in ("session_id", "status", "started_wall", "ended_wall",
                       "end_reason", "port", "baud", "format", "station",
                       "version_address", "version_value", "profile_name",
                       "profile_digest", "error"))
        tk.Label(frame, text=info, font="bench8", bg=CARD, fg=INK,
                 justify="left", wraplength=780).pack(anchor="w", padx=10, pady=(10, 4))
        columns = ("seq", "time", "object", "action", "value", "result")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for key, key_i18n, width in (("seq", "det.col.seq", 46), ("time", "det.col.time", 90),
                                     ("object", "det.col.object", 110),
                                     ("action", "det.col.action", 100),
                                     ("value", "det.col.value", 300),
                                     ("result", "det.col.result", 130)):
            tree.heading(key, text=t(key_i18n))
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        for event in app.store.read_events(session_id):
            if event.get("type") == "sample":
                continue
            target = event.get("target")
            effective = event.get("effective")
            value_text = (json.dumps(target, ensure_ascii=False) if isinstance(target, dict)
                          else ("—" if target is None else str(target)))
            value_text += " / "
            value_text += (json.dumps(effective, ensure_ascii=False)
                           if isinstance(effective, dict)
                           else ("—" if effective is None else str(effective)))
            result_text = f"{tr(event.get('result'))} {tr(event.get('reason'))}".strip()
            tree.insert("", "end", values=(
                event.get("seq"), (event.get("wall") or "")[11:23],
                tr(event.get("object")), tr(event.get("action")), value_text,
                result_text))


def run_app(*, script=None, script_args=None) -> None:
    root = tk.Tk()
    app = BenchApp(root)
    app.worker.start()
    if script:
        script = Path(script).resolve()
        app.ui_config["test_script"] = str(script)
        if script_args:
            app.ui_config.setdefault("script_args", {})[str(script)] = list(script_args)
        app._refresh_script_label()
        root.after(100, lambda: app.start_script(script, script_args or []))
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="PLCWeave 手动硬件在环仿真台（实机）")
    parser.add_argument("--script", type=Path, help="运行已有 Python 测试并显示通讯过程")
    parser.add_argument("--script-args", nargs=argparse.REMAINDER, default=[], help="原测试脚本的参数")
    args = parser.parse_args(argv)
    run_app(script=args.script, script_args=args.script_args)
    return 0
