"""Small Windows bridge for a desktop pet.

Only virtual key codes, button state, and pointer positions are kept in memory.
The low-level hooks always forward input and do no animation or disk I/O.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import queue
import threading
import time


_IS_WINDOWS = os.name == "nt"
_last_cursor = (0, 0)

if _IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _LRESULT = ctypes.c_ssize_t
    _ULONG_PTR = ctypes.c_size_t
    _HOOKPROC = ctypes.WINFUNCTYPE(
        _LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    )

    class _KeyboardHookData(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _MouseHookData(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    _user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
    ]
    _user32.SetWindowsHookExW.restype = wintypes.HANDLE
    _user32.CallNextHookEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
    ]
    _user32.CallNextHookEx.restype = _LRESULT
    _user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
    _user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
    ]
    _user32.GetMessageW.restype = wintypes.BOOL
    _user32.PeekMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND,
        wintypes.UINT, wintypes.UINT, wintypes.UINT,
    ]
    _user32.PeekMessageW.restype = wintypes.BOOL
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.TranslateMessage.restype = wintypes.BOOL
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = _LRESULT
    _user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _user32.SetTimer.argtypes = [wintypes.HWND, _ULONG_PTR, wintypes.UINT, ctypes.c_void_p]
    _user32.SetTimer.restype = _ULONG_PTR
    _user32.KillTimer.argtypes = [wintypes.HWND, _ULONG_PTR]
    _user32.KillTimer.restype = wintypes.BOOL
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _user32.GetCursorPos.restype = wintypes.BOOL
    _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LastInputInfo)]
    _user32.GetLastInputInfo.restype = wintypes.BOOL
    _kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    _kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    _kernel32.GetCurrentThreadId.argtypes = []
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _kernel32.GetTickCount.argtypes = []
    _kernel32.GetTickCount.restype = wintypes.DWORD

    # LONG_PTR / HWND must remain pointer-sized on 64-bit Windows.
    _get_window_long = getattr(_user32, "GetWindowLongPtrW", _user32.GetWindowLongW)
    _set_window_long = getattr(_user32, "SetWindowLongPtrW", _user32.SetWindowLongW)
    _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_window_long.restype = ctypes.c_ssize_t
    _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _set_window_long.restype = ctypes.c_ssize_t
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL


def _win_error(operation: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(code, f"{operation}: {ctypes.FormatError(code).strip()}")


def get_cursor_pos() -> tuple[int, int]:
    """Return screen coordinates, retaining the last value on a locked desktop."""
    global _last_cursor
    if _IS_WINDOWS:
        point = wintypes.POINT()
        if _user32.GetCursorPos(ctypes.byref(point)):
            _last_cursor = (int(point.x), int(point.y))
    return _last_cursor


def get_idle_seconds() -> float:
    """Time since input in this Windows session (not an absence detector)."""
    if not _IS_WINDOWS:
        return 0.0
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not _user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # Both values are DWORD ticks; subtraction must handle the 49.7-day wrap.
    elapsed_ms = (int(_kernel32.GetTickCount()) - int(info.dwTime)) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


def configure_window(hwnd: int, click_through: bool = False) -> None:
    """Keep a Qt translucent window above others without activating it.

    Qt owns the alpha surface. WS_EX_TRANSPARENT on the layered window makes
    the entire pet click-through when requested. In normal mode its transparent
    pixels still use Windows' layered-window hit testing.
    """
    if not _IS_WINDOWS:
        return
    handle = wintypes.HWND(int(hwnd))
    ctypes.set_last_error(0)
    old_style = int(_get_window_long(handle, -20))  # GWL_EXSTYLE
    if old_style == 0 and ctypes.get_last_error():
        raise _win_error("GetWindowLongPtrW")
    style = old_style | 0x00000080 | 0x08000000 | 0x00080000
    style &= ~0x00040000  # WS_EX_APPWINDOW: keep the pet out of the taskbar.
    if click_through:
        style |= 0x00000020
    else:
        style &= ~0x00000020
    ctypes.set_last_error(0)
    previous = _set_window_long(handle, -20, style)
    if previous == 0 and ctypes.get_last_error():
        raise _win_error("SetWindowLongPtrW")
    flags = 0x0001 | 0x0002 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOACTIVATE|FRAMECHANGED
    if not _user32.SetWindowPos(handle, wintypes.HWND(-1), 0, 0, 0, 0, flags):
        raise _win_error("SetWindowPos")


class GlobalInput:
    """Background input observer; drain ``events`` from the animation thread.

    ``key`` and ``button`` events preserve every press/release. Pointer motion
    is coalesced to its most recent location and flushed by a 10 ms Windows
    timer (usually 60-100 Hz), so high-polling mice do not flood the UI queue.
    ``healthy`` reports the message thread and successful hook installation;
    Windows does not expose a query for silently timed-out low-level hooks.
    """

    def __init__(self) -> None:
        self.events: queue.SimpleQueue[dict] = queue.SimpleQueue()
        self.error = ""
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._running = threading.Event()
        self._stop_requested = threading.Event()
        self._pressed: set[int] = set()
        self._pending_move: dict | None = None
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_callback = None
        self._mouse_callback = None
        self._timer_id = 0

    @property
    def healthy(self) -> bool:
        return bool(
            self._running.is_set() and self._thread and self._thread.is_alive()
        )

    def start(self) -> None:
        if self.healthy:
            return
        if not _IS_WINDOWS:
            self.error = "Global keyboard and mouse observation requires Windows."
            raise RuntimeError(self.error)
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Previous input thread has not stopped.")
        self.error = ""
        self._ready.clear()
        self._stop_requested.clear()
        self._pressed.clear()
        self._pending_move = None
        self._thread = threading.Thread(target=self._run, name="CatInput", daemon=True)
        self._thread.start()
        if not self._ready.wait(3.0):
            self.error = "Timed out while installing Windows input hooks."
            self.stop()
            raise RuntimeError(self.error)
        if not self.healthy:
            raise RuntimeError(self.error or "Unable to start Windows input observer.")

    def stop(self) -> None:
        self._stop_requested.set()
        if _IS_WINDOWS and self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                self.error = "Windows input thread has not exited yet."

    def _flush_mouse(self) -> None:
        event = self._pending_move
        self._pending_move = None
        if event is not None:
            self.events.put(event)

    def _on_keyboard(self, code: int, message: int, address: int) -> int:
        if code >= 0:
            try:
                if message in (0x0100, 0x0101, 0x0104, 0x0105):
                    data = ctypes.cast(address, ctypes.POINTER(_KeyboardHookData)).contents
                    vk = int(data.vkCode)
                    down = message in (0x0100, 0x0104)
                    repeat = down and vk in self._pressed
                    if down:
                        self._pressed.add(vk)
                    else:
                        self._pressed.discard(vk)
                    # Preserve ordering relative to the latest pointer position.
                    self._flush_mouse()
                    self.events.put({
                        "type": "key", "time": time.monotonic(),
                        "vk": vk, "down": down, "repeat": repeat,
                        "scan": int(data.scanCode), "extended": bool(data.flags & 1),
                    })
            except Exception as exc:
                self.error = f"Keyboard observer: {exc}"
        return _user32.CallNextHookEx(None, code, message, address)

    def _on_mouse(self, code: int, message: int, address: int) -> int:
        if code >= 0:
            try:
                data = ctypes.cast(address, ctypes.POINTER(_MouseHookData)).contents
                timestamp = time.monotonic()
                x, y = int(data.pt.x), int(data.pt.y)
                if message == 0x0200:  # WM_MOUSEMOVE
                    self._pending_move = {
                        "type": "move", "time": timestamp, "x": x, "y": y
                    }
                else:
                    button = {
                        0x0201: ("left", True), 0x0202: ("left", False),
                        0x0204: ("right", True), 0x0205: ("right", False),
                        0x0207: ("middle", True), 0x0208: ("middle", False),
                    }.get(message)
                    if button:
                        self._flush_mouse()
                        self.events.put({
                            "type": "button", "time": timestamp,
                            "button": button[0], "down": button[1], "x": x, "y": y,
                        })
                    elif message in (0x020A, 0x020E):  # wheel / horizontal wheel
                        self._flush_mouse()
                        delta = ctypes.c_short((int(data.mouseData) >> 16) & 0xFFFF).value
                        self.events.put({
                            "type": "wheel", "time": timestamp, "delta": delta,
                            "horizontal": message == 0x020E, "x": x, "y": y,
                        })
            except Exception as exc:
                self.error = f"Mouse observer: {exc}"
        return _user32.CallNextHookEx(None, code, message, address)

    def _run(self) -> None:
        try:
            message = wintypes.MSG()
            # Ensure a queue exists before another thread can post WM_QUIT.
            _user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            self._thread_id = int(_kernel32.GetCurrentThreadId())
            module = _kernel32.GetModuleHandleW(None)
            self._keyboard_callback = _HOOKPROC(self._on_keyboard)
            self._mouse_callback = _HOOKPROC(self._on_mouse)
            self._keyboard_hook = _user32.SetWindowsHookExW(
                13, self._keyboard_callback, module, 0  # WH_KEYBOARD_LL
            )
            if not self._keyboard_hook:
                raise _win_error("Install keyboard hook")
            self._mouse_hook = _user32.SetWindowsHookExW(
                14, self._mouse_callback, module, 0  # WH_MOUSE_LL
            )
            if not self._mouse_hook:
                raise _win_error("Install mouse hook")
            self._timer_id = int(_user32.SetTimer(None, 0, 10, None))
            if not self._timer_id:
                raise _win_error("Create input timer")
            self._running.set()
            self._ready.set()
            while not self._stop_requested.is_set():
                result = int(_user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if result == -1:
                    raise _win_error("Input GetMessageW")
                if result == 0:
                    break
                if message.message == 0x0113 and message.wParam == self._timer_id:
                    self._flush_mouse()
                else:
                    _user32.TranslateMessage(ctypes.byref(message))
                    _user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:
            self.error = str(exc)
        finally:
            self._running.clear()
            if self._timer_id:
                _user32.KillTimer(None, self._timer_id)
                self._timer_id = 0
            for hook in (self._keyboard_hook, self._mouse_hook):
                if hook:
                    _user32.UnhookWindowsHookEx(hook)
            self._keyboard_hook = self._mouse_hook = None
            self._thread_id = 0
            self._pressed.clear()
            self._pending_move = None
            self._ready.set()

    def __enter__(self) -> "GlobalInput":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()
