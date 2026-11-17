"""GUI 冒烟测试：布局结构、连接/版本、仿真全流程、只读滑条、记录与导出。

tkinter 在本机有显示环境；测试用真实窗口但立即泵事件，不进入 mainloop。
注意：CPython 3.13 + Windows 上反复创建/销毁 Tk root 时，自动 GC 可能触发
0x80000003 崩溃（garbage-collecting pathlib 对象），因此测试期间停用自动 GC。
"""
import gc
import json
import time
import tkinter as tk
from pathlib import Path

import pytest

import plcweave.bench.app as bench_app
from plcweave.bench.app import BenchApp, BenchWorker
from plcweave.bench.contract import DEFAULT_DEMO_PROFILE
from plcweave.bench.engine import State
from plcweave.bench.store import SessionStore


@pytest.fixture(scope="module", autouse=True)
def tk_gc_guard():
    # Collect Tcl cycles on the GUI thread, never in a later worker allocation.
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    yield
    gc.collect()
    if enabled:
        gc.enable()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(bench_app, "UI_CONFIG_PATH", tmp_path / "ui_config.json")
    store = SessionStore(tmp_path / "sessions")
    root = bench_app.tk.Tk()
    instance = BenchApp(root, demo=True, store=store,
                        profile=DEFAULT_DEMO_PROFILE)
    instance.worker.start()
    yield instance
    instance.worker.submit(instance._disconnect_on_close)
    instance.worker.join(5)
    assert not instance.worker.is_alive()
    root.after_cancel(instance._event_job)
    root.destroy()


def pump(app, seconds=0.6):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.root.update()
        time.sleep(0.01)


def connect(app):
    app.version_var.set("D196")
    app._on_connect()
    pump(app, 1.0)


def test_customer_register_panel_reads_writes_and_logs(app):
    connect(app)
    assert app.customer_tree.item("260", "values")[2] == "60"
    assert app.customer_send_btn.instate(["disabled"])
    app.watch_address.set("D8030")
    app.watch_name.set("硬件原值")
    app._add_customer_watch()
    pump(app, 0.5)
    assert app.customer_tree.item("8030", "values")[4] == "只读"
    assert tuple(app.customer_send_combo["values"]) == ("D260",)
    app._on_start_stop()
    pump(app, 0.6)
    app.send_value.set("88")
    app.customer_send_btn.invoke()
    pump(app, 0.4)
    assert app.customer_tree.item("260", "values")[2] == "88"
    assert "已读回 88" in app.customer_status.cget("text")
    assert any(event.get("object") == "D260" and event.get("effective") == 88
               for event in app.store.read_events(app.store.current_id))


def test_script_completion_popup_keeps_window_open_for_manual_testing(app, monkeypatch):
    from pathlib import Path
    notifications = []

    def acknowledge(title, message, **kwargs):
        notifications.append((title, message))
        assert app.engine.state == State.SCRIPT_CONFIRM
        assert app.worker.scripts.process is None
        assert app.root.winfo_exists()
        return "ok"

    monkeypatch.setattr(bench_app.messagebox, "showinfo", acknowledge)
    script = Path(__file__).resolve().parents[1] / "demo/bench-script-demo.py"
    app.start_script(script, [])
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline and app.engine.state != State.SIMULATING:
        pump(app, 0.1)
    assert len(notifications) == 1 and notifications[0][0] == "测试完毕"
    assert app.root.winfo_exists() and app.engine.state == State.SIMULATING
    previous = app.engine.effective_x[0]
    app._on_x_click(0)
    pump(app, 0.4)
    assert app.engine.y_bits[0] == 1 - previous
    assert any(event.get("actor") == "script" for event in app.engine.events)
    app._on_start_stop()
    pump(app, 0.4)


def test_failed_script_also_waits_for_confirmation_and_leaves_window_open(app, tmp_path, monkeypatch):
    script = tmp_path / "broken.py"
    script.write_text("raise RuntimeError('expected-script-error')", encoding="utf-8")
    messages = []
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: (messages.append(args), "ok")[1])
    app.start_script(script, [])
    deadline = time.monotonic() + 8
    while not messages and time.monotonic() < deadline:
        pump(app, 0.1)
    assert messages and "退出码 1" in messages[0][1]
    assert app.root.winfo_exists()
    assert any("expected-script-error" in str(event.get("target")) for event in app.engine.events)


def test_completion_without_explicit_ok_keeps_confirmation_pending(app, monkeypatch):
    from pathlib import Path
    calls = []
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: calls.append(args))
    app.start_script(Path(__file__).resolve().parents[1] / "demo/bench-script-demo.py", [])
    deadline = time.monotonic() + 10
    while not calls and time.monotonic() < deadline:
        pump(app, 0.1)
    assert app.engine.state == State.SCRIPT_CONFIRM
    assert app.worker.scripts.waiting_confirmation and app.worker.scripts.process is None
    assert app.engine.client is None
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: "ok")
    assert app.script_start_btn.cget("text") == "确认测试结束"
    app.script_start_btn.invoke()
    pump(app, 0.8)
    assert app.engine.state == State.SIMULATING and app.root.winfo_exists()
    app._on_start_stop()
    pump(app, 0.3)


def test_script_uses_version_address_from_visible_setting(app, tmp_path, monkeypatch):
    script = tmp_path / "empty.py"
    script.write_text("print('done')", encoding="utf-8")
    notices = []
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: notices.append(args))
    app.version_var.set("D500")
    app.start_script(script, [])
    deadline = time.monotonic() + 8
    while not notices and time.monotonic() < deadline:
        pump(app, 0.1)
    assert app.engine.settings["version_address"] == 500
    assert app.engine.state == State.SCRIPT_CONFIRM
    assert app.engine.version_value is None


def test_load_script_persists_selection_and_start_button_runs_it(app, tmp_path, monkeypatch):
    script = tmp_path / "project_a.py"
    script.write_text("print('done')", encoding="utf-8")
    notices = []
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: notices.append(args))
    monkeypatch.setattr(bench_app.filedialog, "askopenfilename",
                        lambda **kwargs: str(script))
    app.script_load_btn.invoke()
    assert app.script_name_var.get() == f"脚本：{script.name}"
    assert app.ui_config["test_script"] == str(script.resolve())
    assert app.worker.scripts.process is None and app.engine.state == State.DISCONNECTED
    # 开始脚本测试：一键复跑已加载脚本，无需再走文件对话框
    app.script_start_btn.invoke()
    deadline = time.monotonic() + 8
    while not notices and time.monotonic() < deadline:
        pump(app, 0.1)
    assert notices and app.engine.state == State.SCRIPT_CONFIRM
    assert app.script_start_btn.cget("state") == tk.NORMAL
    assert app.script_load_btn.cget("state") == tk.DISABLED


def test_start_button_without_loaded_script_prompts_file_dialog(app, monkeypatch):
    picked = []
    monkeypatch.setattr(bench_app.filedialog, "askopenfilename",
                        lambda **kwargs: picked.append(kwargs) or "")
    app.script_start_btn.invoke()
    assert picked and "未加载" in app.script_name_var.get()
    assert app.engine.state == State.DISCONNECTED


def test_script_args_remembered_per_script_and_legacy_config_migrated(app, tmp_path, monkeypatch):
    other = tmp_path / "project_b.py"
    other.write_text("print('done')", encoding="utf-8")
    first = Path(__file__).resolve().parents[1] / "demo/bench-script-demo.py"
    app.ui_config["test_script"] = str(first)
    app.ui_config["script_args"] = {str(first): ["--step-delay", "0.2"]}
    dialog = bench_app.ScriptDialog(app)
    assert "--step-delay" in dialog.arguments.get("1.0", "end")
    dialog.path.set(str(other))
    dialog.arguments.delete("1.0", "end")
    dialog.arguments.insert("1.0", "--restart")
    notices = []
    monkeypatch.setattr(bench_app.messagebox, "showinfo", lambda *args, **kwargs: notices.append(args))
    dialog._start()
    assert app.ui_config["test_script"] == str(other.resolve())
    assert app.ui_config["script_args"][str(first)] == ["--step-delay", "0.2"]
    assert app.ui_config["script_args"][str(other.resolve())] == ["--restart"]
    assert app.script_name_var.get() == f"脚本：{other.name}"
    deadline = time.monotonic() + 8
    while not notices and time.monotonic() < deadline:
        pump(app, 0.1)
    assert notices and app.engine.state == State.SCRIPT_CONFIRM
    app.worker.submit(app.worker.scripts.acknowledge, app.worker.scripts.generation)
    pump(app, 0.4)
    app._on_start_stop()
    pump(app, 0.3)


def test_legacy_test_script_args_migrate_into_per_script_map(app, tmp_path, monkeypatch):
    script = tmp_path / "legacy.py"
    script.write_text("print('done')", encoding="utf-8")
    bench_app.UI_CONFIG_PATH.write_text(json.dumps({
        "test_script": str(script), "test_script_args": ["--restart"]}),
        encoding="utf-8")
    fresh_ui = bench_app.BenchApp.__new__(bench_app.BenchApp)
    fresh_ui.demo = True
    fresh_ui._load_ui_config()
    assert "test_script_args" not in fresh_ui.ui_config
    assert fresh_ui.ui_config["script_args"][str(script)] == ["--restart"]


class TestLayout:
    def test_default_window_shows_ad_settings_and_customer_commands(self, app):
        def check(widget):
            assert widget.winfo_viewable(), str(widget)
            assert widget.winfo_height() >= widget.winfo_reqheight(), str(widget)
            bottom = widget.winfo_rooty() + widget.winfo_height()
            parent = widget.master
            while parent is not None:
                assert bottom <= parent.winfo_rooty() + parent.winfo_height(), str(widget)
                parent = parent.master

        for geometry in (None, "1530x740"):
            if geometry:
                app.root.geometry(geometry)
            app.root.update()
            for widget in (*app.ad_target_labels, *app.ad_entries, *app.ad_apply_buttons,
                           *app.da_raw_labels, app.customer_tree, app.customer_send_combo,
                           app.customer_value_entry, app.customer_send_btn):
                check(widget)

    def test_structure_counts(self, app):
        # PRD A01：22 点位全部可见——8X + 4AD + 8Y + 2DA
        assert len(app.x_buttons) == 8
        assert len(app.x_leds) == 8
        assert len(app.y_tiles) == 8
        assert len(app.y_leds) == 8
        assert len(app.ad_bars) == 4
        assert len(app.da_bars) == 2
        assert app.root.title().startswith("PLCWeave · 手动硬件在环仿真台")

    def test_connection_options(self, app):
        # PRD A02：全部波特率与数据格式选项
        assert list(app.baud_combo.cget("values")) == [
            "600", "1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
        assert list(app.format_combo.cget("values")) == [
            "8N1", "8N2", "8E1", "8O1", "8E2", "8O2"]

    def test_sliders_are_readonly(self, app):
        # PRD A07：拖动/点击/滚轮/键盘都不能改变滑条或发命令
        for bar in app.ad_bars + app.da_bars:
            assert str(bar.cget("takefocus")) == "0"
            for sequence in ("<Button-1>", "<B1-Motion>", "<MouseWheel>",
                             "<ButtonRelease-1>", "<Key>", "<Touch>"):
                assert not bar.bind(sequence), f"滑条不得绑定 {sequence}"

    def test_y_tiles_are_labels_not_buttons(self, app):
        # Y 点位牌只读，不是可点击按钮
        for tile in app.y_tiles:
            assert isinstance(tile, bench_app.tk.Label)


class TestConnectFlow:
    def test_connect_reads_version(self, app):
        connect(app)
        assert app.engine.state == State.CONNECTED
        assert "101" in app.version_label.cget("text")
        assert "D196" in app.version_label.cget("text")
        # 连接后设置锁定（A03 配套）
        assert str(app.port_combo.cget("state")) == "disabled"

    def test_connect_without_version_address_rejected(self, app):
        app.version_var.set("")
        app._on_connect()
        pump(app, 0.4)
        assert app.engine.state == State.DISCONNECTED


class TestSimulationFlow:
    def start(self, app):
        connect(app)
        app._on_start_stop()   # demo 模式跳过台架确认弹窗
        pump(app, 1.2)

    def test_full_cycle(self, app):
        self.start(app)
        assert app.engine.state == State.SIMULATING
        assert app.start_btn.cget("text") == "结束仿真"
        # 会话记录已建立（先于连接：PRD §9.1）
        assert app.store.current_id is not None

        # X0 点击 → 提交 → 生效 → Y0 亮
        app._on_x_click(0)
        pump(app, 0.8)
        assert app.engine.effective_x[0] == 1
        assert app.x_leds[0].text.cget("text") == "ON"
        pump(app, 0.5)
        assert app.engine.y_bits[0] == 1           # 演示程序 Y0=X0
        assert app.y_leds[0].text.cget("text") == "ON"

        # AD0 7.5V → raw 3000 → DA1 显示 7.50 V（与参考图一致）
        app.ad_entries[0].insert(0, "7.5")
        app._on_ad_entry(0)
        pump(app, 0.8)
        assert app.engine.effective_ad[0] == 3000
        assert app.da_value_labels[0].cget("text").startswith("7.50")
        assert app.da_raw_labels[0].cget("text") == "raw 3000 · 手册 DA0 / D8050"

        # 步长调整
        app.step_var.set("10%")
        app._on_step()
        pump(app, 0.3)
        assert app.engine.step_pct == 10

        # 结束仿真 → 回到已连接，输出清零
        app._on_start_stop()
        pump(app, 1.0)
        assert app.engine.state == State.CONNECTED
        assert app.engine.y_bits == [0] * 8
        assert app.engine.da_raw == [0, 0]
        assert app.store.current_id is None
        summary = app.store.list_sessions()[0]
        assert summary["status"] == "正常结束"
        assert summary["version_value"] == 101

        # 日志行包含操作与结果
        rows = [app.log_tree.item(item)["values"]
                for item in app.log_tree.get_children()]
        results = [str(row[3]) for row in rows]
        assert any("已生效" in text for text in results)
        assert any("正常结束" in text for text in results)

    def test_rejected_ad_entry_shows_inline_error(self, app):
        self.start(app)
        app.ad_entries[1].insert(0, "abc")
        app._on_ad_entry(1)
        pump(app, 0.5)
        assert "拒绝" in app._pending_ad_errors[1].cget("text")
        assert app.engine.target_ad_raw[1] == 0   # 未发送

    def test_hold_mode_press_release(self, app):
        self.start(app)
        app.x_mode_var.set("按住有效")
        app._on_x_mode()
        pump(app, 0.3)
        app._on_x_press(2)
        pump(app, 0.8)
        assert app.engine.effective_x[2] == 1
        app._on_x_release(2)
        pump(app, 0.8)
        assert app.engine.effective_x[2] == 0

    def test_apply_all_and_reset(self, app):
        self.start(app)
        app._on_x_click(1)
        pump(app, 0.6)
        app._on_apply_all()
        pump(app, 0.6)
        assert app.engine.effective_x[1] == 1
        app._on_reset()
        pump(app, 0.6)
        assert app.engine.effective_x == [0] * 8
        assert app.engine.effective_ad == [0] * 4

    def test_watchdog_fault_shown(self, app):
        # 心跳停止 3s+ → 虚拟 PLC 会话失效 → 引擎进入故障态
        self.start(app)
        device = app.engine.transport.device
        # 把 PLC 记录的心跳时间回拨，模拟 PC 崩溃后恢复轮询
        device.last_heartbeat_change -= 4.0
        pump(app, 1.5)
        assert app.engine.state == State.FAULT
        assert "会话已失效" in (app.engine.last_error or "")

    def test_disconnect_marks_session_interrupted(self, app):
        self.start(app)
        app._on_disconnect()
        pump(app, 0.6)
        assert app.engine.state == State.DISCONNECTED
        summary = app.store.list_sessions()[0]
        assert summary["status"] == "异常中断"


class TestRecords:
    def test_records_dialog_lists_and_exports(self, app, tmp_path):
        # 先造一条已结束记录
        app.store.record("start", {"port": "loopback", "demo": True})
        app.store.record("event", {"seq": 1, "wall": "2026-11-04T10:00:00",
                                   "object": "X0", "action": "提交输入",
                                   "target": 1, "result": "已生效"})
        app.store.record("end", {"status": "正常结束", "end_reason": "正常结束"})
        dialog = bench_app.RecordsDialog(app)
        pump(app, 0.3)
        children = dialog.tree.get_children()
        assert len(children) == 1
        dialog.tree.selection_set(children[0])
        target = tmp_path / "export.zip"
        # 直接调用导出核心（跳过文件对话框）
        path = app.store.export_session(children[0], target)
        assert path.exists()

    def test_export_button_requires_running_session(self, app):
        assert str(app.export_btn.cget("state")) == "disabled"


class TestCustomerAccessAndCsv:
    """V0.4.2：监控条目读写权限开关 + CSV 导入。"""

    def test_add_row_access_toggle_and_send_combo(self, app):
        app.watch_address.set("D320")
        app.watch_name.set("测试读写")
        app._add_customer_watch()
        pump(app, 0.5)
        assert app.customer_tree.item("320", "values")[4].startswith("读写")
        assert "D320" in app.customer_send_combo["values"]

        app.watch_address.set("D321")
        app.watch_name.set("测试只读")
        app.watch_access.set("只读")
        app._add_customer_watch()
        pump(app, 0.5)
        assert app.customer_tree.item("321", "values")[4] == "只读"
        assert "D321" not in app.customer_send_combo["values"]

    def test_writeonly_row_sends_without_polling(self, app):
        connect(app)   # 连接后状态非未连接，只写行显示“只写·不轮询”
        app.watch_address.set("D322")
        app.watch_name.set("命令字")
        app.watch_access.set("只写")
        app._add_customer_watch()
        pump(app, 0.8)
        values = app.customer_tree.item("322", "values")
        assert values[4].startswith("只写")
        assert values[5] == "只写·不轮询"
        assert values[2] == "—"
        assert "D322" in app.customer_send_combo["values"]
        # 仿真中发送只写寄存器 → 已发送（不读回）
        app._on_start_stop()
        pump(app, 1.2)
        app.send_address.set("D322")
        app.send_value.set("9")
        app._send_customer()
        pump(app, 0.8)
        assert "已发送（不读回）" in app.customer_status.cget("text")
        assert app.engine.client.read_words(322, 1)[0] == 9

    def test_csv_import_updates_tree_and_status(self, app):
        csv_text = "\n".join([
            "地址,名称,权限,最小,最大",
            "D330,导入读写,读写,0,2000",
            "D331,导入只读,只读",
            "坏行",
        ])
        app.engine.import_customer_watches_csv(csv_text)
        pump(app, 0.6)
        assert app.customer_tree.item("330", "values")[4] == "读写 0–2000"
        assert app.customer_tree.item("331", "values")[4] == "只读"
        status = app.customer_status.cget("text")
        assert "CSV 导入 2 条" in status and "跳过 1 条" in status

    def test_persisted_watches_include_access(self, app):
        app.watch_address.set("D340")
        app.watch_name.set("持久")
        app.watch_access.set("只写")
        app._add_customer_watch()
        pump(app, 0.6)
        saved = app.ui_config[app._watch_config_key]
        entry = next(row for row in saved if row[0] == 340)
        assert entry[1] == "持久" and entry[2] == "只写"


class TestCustomerCsvExportAndLayout:
    """V0.4.3：导出CSV按钮 + 按钮与输入框等高。"""

    def test_buttons_align_with_entries(self, app):
        pump(app, 0.4)
        add_row = app.watch_access_combo.master
        entries = [w for w in add_row.winfo_children()
                   if isinstance(w, bench_app.ttk.Entry)]
        entry_height = entries[0].winfo_height()
        assert entry_height > 0
        for button in app.customer_buttons:
            assert abs(button.winfo_height() - entry_height) <= 1,                 f"{button.cget('text')} 高度 {button.winfo_height()} ≠ 输入框 {entry_height}"

    def test_export_button_in_row(self, app):
        labels = [str(b.cget("text")) for b in app.customer_buttons]
        assert labels == ["添加监控", "移除选中", "导入CSV", "导出CSV"]

    def test_export_writes_file_and_logs(self, app, tmp_path):
        app.engine.set_customer_watch(350, "导出行", "读写", 0, 500)
        target = tmp_path / "out.csv"
        app._export_customer_csv_task(str(target))
        content = target.read_text(encoding="utf-8-sig")
        assert "地址,名称,权限,最小,最大" in content
        assert "D350,导出行,读写,0,500" in content
        assert any(op["action"] == "导出监控CSV" and op["result"] == "成功"
                   for op in app.engine.events)
        pump(app, 0.3)
        # demo 默认含 D260 演示条目 + 本测试 D350 = 2 条
        assert "已导出 2 条监控" in app.customer_status.cget("text")

    def test_export_write_failure_logged(self, app, tmp_path):
        app.engine.set_customer_watch(351, "失败行", "只读")
        bad = tmp_path / "no-such-dir" / "out.csv"   # 目录不存在 → OSError
        app._export_customer_csv_task(str(bad))
        assert any(op["action"] == "导出监控CSV" and op["result"] == "失败"
                   for op in app.engine.events)

    def test_export_empty_list_hint(self, app):
        # 清空监控后点导出：提示而不写文件
        for address in list(app.engine.customer_watches):
            app.engine.remove_customer_watch(address)
        pump(app, 0.3)
        app._export_customer_csv()
        assert "监控列表为空" in app.customer_status.cget("text")


def test_x_led_falls_back_to_hardware_value_when_unmapped(app):
    # 无输入映射的工程（如水站）：X 小灯回落显示 FC02 直读的真实硬件状态
    engine = app.engine
    engine.effective_x = [None] * 8
    engine.hw_x = [1, 0, None] + [None] * 5
    app.refresh_values()
    assert app.x_leds[0].text.cget("text") == "ON"
    assert app.x_leds[1].text.cget("text") == "OFF"
    assert app.x_leds[2].text.cget("text") == "未知"
    engine.effective_x[0] = 0          # 注入生效值存在时优先于硬件值
    app.refresh_values()
    assert app.x_leds[0].text.cget("text") == "OFF"


def test_customer_display_normalization():
    # V0.6：压力/频率归一化显示（未知类型与非法值原样显示）
    display = bench_app.BenchApp._customer_display
    assert display(60, "bar01") == "6.0 bar"
    assert display(1600, "bar01") == "160.0 bar"
    assert display(1400, "pv_bar") == "5.6 bar"      # (1400+12)//25 = 56 → 5.6 bar
    assert display(2450, "hz") == "24.50 Hz"
    assert display(1, "") == "1"
    assert display("—", "") == "—"


def test_language_switch_updates_widgets_and_persists(app):
    # i18n：右上角语言下拉即时切换，写入 ui_config；切回中文逐字还原
    from plcweave.bench.i18n import LANGUAGES
    app.lang_var.set(LANGUAGES["en"])
    app._on_language()
    pump(app, 0.3)
    assert app.root.title().startswith("PLCWeave · Manual HIL Bench")
    assert app.start_btn.cget("text") == "Start simulation"
    assert app.script_start_btn.cget("text") == "Start script test"
    assert list(app.x_mode_combo["values"])[0] == "Toggle"
    assert list(app.watch_access_combo["values"]) == ["RO", "WO", "RW"]
    assert app.x_leds[2].text.cget("text") == "Unknown"
    saved = json.loads(bench_app.UI_CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved["language"] == "en"
    # X 模式当前显示值应已映射为英文，而引擎/配置仍持有中文原值
    assert app.x_mode_var.get() == "Toggle"
    assert app.ui_config["x_mode"] in ("保持开关", "按住有效")
    assert len(list(app.lang_combo["values"])) == 6
    app.lang_var.set(LANGUAGES["fr"])
    app._on_language()
    pump(app, 0.3)
    assert app.root.title().startswith("PLCWeave · Banc d'essai HIL manuel")
    assert app.start_btn.cget("text") == "Démarrer la simulation"
    assert list(app.watch_access_combo["values"]) == ["Lecture", "Écriture", "Lec/Écr"]
    app.lang_var.set(LANGUAGES["zh"])
    app._on_language()
    pump(app, 0.3)
    assert app.root.title().startswith("PLCWeave · 手动硬件在环仿真台")
    assert app.start_btn.cget("text") == "开始仿真"
    assert app.x_mode_var.get() in ("保持开关", "按住有效")


def test_language_persisted_config_restores_english(app, tmp_path, monkeypatch):
    # ui_config 里记录的 language 在下次构造时直接生效（无需手动切换）
    bench_app.UI_CONFIG_PATH.write_text(json.dumps({"language": "en"}), encoding="utf-8")
    store = SessionStore(tmp_path / "sessions-en")
    root = bench_app.tk.Tk()
    instance = bench_app.BenchApp(root, demo=True, store=store,
                                  profile=DEFAULT_DEMO_PROFILE)
    try:
        assert instance.root.title().startswith("PLCWeave · Manual HIL Bench")
        assert instance.start_btn.cget("text") == "Start simulation"
    finally:
        instance.worker.stop()
        root.after_cancel(instance._event_job)
        root.destroy()
