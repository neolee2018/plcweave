"""Own only the test host and its descendants; release them before manual access."""
from __future__ import annotations

import os
import signal
import time
import threading


class ProcessTree:
    def __init__(self):
        self.handle = None
        self.pid = None
        self.owned_handles = {}
        self.lock = threading.RLock()
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinWorkingSet", ctypes.c_size_t),
                        ("MaxWorkingSet", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in ("User", "Kernel", "PeriodUser", "PeriodKernel")] + [
                (name, wintypes.DWORD) for name in ("Faults", "Total", "Active", "Terminated")]

        self.Accounting = Accounting

        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateJobObjectW", [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetInformationJobObject", [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            ("AssignProcessToJobObject", [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            ("TerminateJobObject", [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            ("QueryInformationJobObject", [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            ("OpenProcess", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            ("WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
        ):
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE, no breakaway.
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process):
        self.pid = process.pid
        if os.name == "nt" and not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            import ctypes
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(self):
        if os.name == "nt":
            with self.lock:
                if self.handle:
                    self._capture_handles()
                    self.kernel.TerminateJobObject(self.handle, 1)
        elif self.pid is not None:
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self):
        with self.lock:
            if self.handle:
                self.kernel.CloseHandle(self.handle)
                self.handle = None
            for handle in self.owned_handles.values():
                self.kernel.CloseHandle(handle)
            self.owned_handles.clear()

    def _capture_handles(self):
        import ctypes
        # JobObjectBasicProcessIdList: two DWORDs, then ULONG_PTR process IDs.
        capacity = 64
        while True:
            buffer = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            ok = self.kernel.QueryInformationJobObject(self.handle, 3, buffer, len(buffer), None)
            if ok:
                count = ctypes.c_uint32.from_buffer(buffer, 4).value
                pids = (ctypes.c_size_t * count).from_buffer(buffer, 8)
                for pid in pids:
                    if pid not in self.owned_handles:
                        handle = self.kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                        if handle:
                            self.owned_handles[pid] = handle
                return
            if ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                raise ctypes.WinError(ctypes.get_last_error())
            capacity *= 2

    def wait_empty(self, timeout=5):
        if os.name != "nt" or not self.handle:
            return
        import ctypes
        deadline = time.monotonic() + timeout
        while True:
            with self.lock:
                self._capture_handles()
                counters = self.Accounting()
                if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(counters), ctypes.sizeof(counters), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                # Active==0 can precede process-object signalling by milliseconds.
                # Retain owned process handles and await their final teardown too.
                if counters.Active == 0 and all(self.kernel.WaitForSingleObject(handle, 0) == 0
                                                for handle in self.owned_handles.values()):
                    return
            if time.monotonic() >= deadline:
                raise RuntimeError("脚本子进程尚未全部退出，禁止手动接管")
            time.sleep(0.01)
