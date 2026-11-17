"""启动演示模式仿真台并截图，供 hmi/docs/screens 文档使用。

用法: .venv/Scripts/python.exe hmi/prototype/scripts/screenshot.py
输出: hmi/docs/assets/screenshots/*.png
"""
import sys
import time
from tempfile import TemporaryDirectory
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import tkinter as tk  # noqa: E402

from PIL import ImageGrab, PngImagePlugin  # noqa: E402

from plcweave.bench import app as bench_app  # noqa: E402
from plcweave.bench.engine import State  # noqa: E402
from plcweave.bench.store import SessionStore  # noqa: E402

OUT = ROOT / "hmi" / "docs" / "assets" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def pump(root, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def grab(window, output, name):
    window.update_idletasks()
    window.update()
    with ImageGrab.grab(window=window.winfo_id()) as image:
        if image.getbbox() is None:
            raise RuntimeError(f"空窗口截图: {name}")
        info = PngImagePlugin.PngInfo()
        info.add_text("PLCWeave", bench_app.TOOL_VERSION)
        info.add_text("Scenario", name)
        info.add_text("Tk scaling", str(window.tk.call("tk", "scaling")))
        image.save(output / f"{name}.png", pnginfo=info)
        print(f"saved {name}.png  {image.width}x{image.height}")


def assert_vertically_visible(widget, root):
    assert widget.winfo_viewable() and widget.winfo_height() >= widget.winfo_reqheight()
    bottom = widget.winfo_rooty() + widget.winfo_height()
    parent = widget.master
    while parent is not None:
        assert bottom <= parent.winfo_rooty() + parent.winfo_height(), str(widget)
        if parent is root:
            break
        parent = parent.master


def capture(app, output):
    root = app.root

    pump(root, 0.8)
    for widget in (*app.ad_target_labels, *app.ad_entries, *app.ad_apply_buttons,
                   app.customer_tree, app.customer_send_combo, app.customer_value_entry,
                   app.customer_send_btn):
        assert_vertically_visible(widget, root)
    grab(root, output, "main-disconnected")

    # 连接 → 开始仿真
    app.version_var.set("D196")
    app._on_connect()
    pump(root, 1.2)
    assert app.engine.state == State.CONNECTED
    grab(root, output, "main-connected")

    app._on_start_stop()
    pump(root, 1.5)

    assert app.engine.state == State.SIMULATING

    # 摆出与参考图一致的场景：X0/X3 ON；AD0=5V AD1=10mA(切换mA) AD2=2.5V AD3=15mA
    app._on_x_click(0)
    pump(root, 0.4)
    app._on_x_click(3)
    pump(root, 0.4)
    for index, text in ((0, "5.0"), (2, "2.5")):
        app.ad_entries[index].insert(0, text)
        app._on_ad_entry(index)
        pump(root, 0.4)
    app.ad_range_vars[1].set("0–20mA")
    app._on_ad_range(1, app.ad_range_vars[1])
    app.ad_entries[1].insert(0, "10")
    app._on_ad_entry(1)
    pump(root, 0.4)
    app.ad_range_vars[3].set("0–20mA")
    app._on_ad_range(3, app.ad_range_vars[3])
    app.ad_entries[3].insert(0, "15")
    app._on_ad_entry(3)
    pump(root, 0.4)
    app.da_range_vars[0].set("0–10V")
    app._on_da_range(0, app.da_range_vars[0])
    app.da_range_vars[1].set("0–20mA")
    app._on_da_range(1, app.da_range_vars[1])
    pump(root, 0.8)
    grab(root, output, "main-simulating")

    # V0.6 布局：日志常驻底部、客户寄存器常驻右侧，无面板切换
    pump(root, 0.2)
    for widget in (*app.ad_entries, *app.ad_apply_buttons, app.log_tree,
                   app.customer_tree, app.customer_send_btn):
        assert_vertically_visible(widget, root)
    grab(root, output, "main-simulating-log")

    # 展开硬件原值诊断
    app._toggle_hw_x()
    pump(root, 0.3)
    grab(root, output, "main-simulating-diagnostics")
    app._toggle_hw_x()

    app.send_value.set("88")
    app.customer_send_btn.invoke()
    pump(root, 0.5)
    assert app.customer_tree.item("260", "values")[2] == "88"
    for widget in (app.customer_send_btn, *app.da_raw_labels, *app.ad_entries):
        assert_vertically_visible(widget, root)
    grab(root, output, "main-customer-registers")
    app._on_start_stop()
    pump(root, 0.5)
    assert app.engine.state == State.CONNECTED and app.store.current_id is None

    app.store.storage_path = lambda: "演示临时目录"
    dialog = bench_app.RecordsDialog(app)
    pump(root, 0.3)
    grab(dialog, output, "records")
    dialog.destroy()

    # Run the unchanged executable demo through the actual child-process bridge.
    # Capture and confirm this process's native completion dialog only.
    import ctypes
    import os
    import threading
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    captured = []
    monitor_stop = threading.Event()

    def confirm_own_dialog():
        @callback_type
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            title = ctypes.create_unicode_buffer(128)
            user32.GetWindowTextW(hwnd, title, len(title))
            if pid.value == os.getpid() and title.value == "测试完毕":
                with ImageGrab.grab(window=hwnd) as image:
                    image.save(output / "script-complete.png")
                captured.append(True)
                @callback_type
                def press(button, _):
                    label = ctypes.create_unicode_buffer(128)
                    kind = ctypes.create_unicode_buffer(128)
                    user32.GetWindowTextW(button, label, len(label))
                    user32.GetClassNameW(button, kind, len(kind))
                    if kind.value == "Button" and label.value.replace("&", "") == "确定":
                        user32.PostMessageW(button, 0xF5, 0, 0)  # BM_CLICK, observed button.
                    return True
                user32.EnumChildWindows(hwnd, press, 0)
            return True
        deadline = time.monotonic() + 20
        while not captured and not monitor_stop.is_set() and time.monotonic() < deadline:
            user32.EnumWindows(visit, 0)
            time.sleep(0.05)

    # Native Windows message boxes do not reliably service Tk after callbacks.
    # This monitor uses only Win32 for this process's own dialog, never Tk APIs.
    monitor = threading.Thread(target=confirm_own_dialog, name="bench-screenshot-dialog", daemon=True)
    app._screenshot_monitor = (monitor, monitor_stop)
    monitor.start()
    app.start_script(ROOT / "demo/bench-script-demo.py", ["--step-delay", "1.5"])
    deadline = time.monotonic() + 5
    while (app.engine.state != State.SCRIPT_RUNNING or app.engine.da_raw[0] is None) and time.monotonic() < deadline:
        pump(root, 0.05)
    assert app.engine.state == State.SCRIPT_RUNNING
    grab(root, output, "main-script-running")
    pump(root, 6)
    monitor.join(3)
    assert not monitor.is_alive()
    assert captured and app.engine.state == State.SIMULATING
    assert app.root.winfo_exists()
    app.send_value.set("77")
    app.customer_send_btn.invoke()
    pump(root, 0.4)
    assert app.customer_tree.item("260", "values")[2] == "77"
    grab(root, output, "main-script-manual")
    app._on_start_stop()
    pump(root, 0.3)


def main():
    with TemporaryDirectory(prefix="plcweave-ui-") as directory:
        temp = Path(directory)
        output = temp / "screenshots"
        output.mkdir()
        original_config = bench_app.UI_CONFIG_PATH
        bench_app.UI_CONFIG_PATH = temp / "ui_config.json"
        root = tk.Tk()
        app = None
        try:
            app = bench_app.BenchApp(root, demo=True, store=SessionStore(temp / "sessions"))
            app.worker.start()
            capture(app, output)
            for path in output.glob("*.png"):
                (OUT / path.name).write_bytes(path.read_bytes())
        finally:
            if app is not None:
                if hasattr(app, "_screenshot_monitor"):
                    monitor, stop = app._screenshot_monitor
                    stop.set()
                    monitor.join(5)
                    if monitor.is_alive():
                        raise RuntimeError("截图弹窗线程未释放")
                root.after_cancel(app._event_job)
                app.worker.submit(app._disconnect_on_close)
                app.worker.join(8)
                if app.worker.is_alive():
                    raise RuntimeError("截图工作线程未在时限内释放")
            root.destroy()
            bench_app.UI_CONFIG_PATH = original_config


if __name__ == "__main__":
    main()
