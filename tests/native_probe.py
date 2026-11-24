"""Windows-only OS input smoke test, confined to a temporary owned window.

Run with: python tests/native_probe.py
Exit codes: 0 passed, 1 failed, 77 safely skipped (foreground not confirmed).
No keyboard input is sent unless this process owns the foreground window and
the temporary input field has focus. No mouse buttons are ever injected.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run() -> tuple[int, dict]:
    if os.name != "nt":
        return 77, {"status": "skip", "reason": "Windows is required"}

    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QLineEdit
    from native_input import GlobalInput, get_cursor_pos

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    imm32 = ctypes.WinDLL("imm32", use_last_error=True)
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetFocus.argtypes = []
    user32.GetFocus.restype = wintypes.HWND
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    imm32.ImmAssociateContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    imm32.ImmAssociateContext.restype = wintypes.HANDLE

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG), ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t),
        ]

    class KeyboardInput(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [("mi", MouseInput), ("ki", KeyboardInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("data", InputUnion)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    edit = QLineEdit()
    edit.setWindowTitle("Black Cat - temporary input probe")
    edit.setPlaceholderText("Temporary keyboard test; closes automatically")
    edit.setAttribute(Qt.WA_InputMethodEnabled, False)
    edit.resize(420, 44)
    edit.move(100, 100)
    handle = int(edit.winId())
    original_foreground = user32.GetForegroundWindow()
    original_cursor = get_cursor_pos()
    previous_ime = None
    cursor_after_injection = None
    observer = GlobalInput()
    captured: list[dict] = []

    def pump(seconds: float) -> None:
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            app.processEvents()
            while True:
                try:
                    captured.append(observer.events.get_nowait())
                except queue.Empty:
                    break
            time.sleep(0.004)

    def owns_foreground() -> bool:
        return bool(
            user32.GetForegroundWindow() == handle
            and user32.GetFocus() == handle
            and edit.hasFocus()
        )

    try:
        observer.start()
        edit.show()
        edit.raise_()
        edit.activateWindow()
        edit.setFocus(Qt.OtherFocusReason)
        user32.SetForegroundWindow(handle)
        pump(0.25)
        if not owns_foreground():
            return 77, {
                "status": "skip", "reason": "Owned input window did not obtain foreground/focus",
                "keyboard_injected": False, "hooks_installed": observer.healthy,
            }
        # Disable IME only for this temporary HWND. Existing app contexts remain untouched.
        previous_ime = imm32.ImmAssociateContext(handle, None)
        pump(0.03)
        modifiers = [0x10, 0x11, 0x12, 0x5B, 0x5C]
        if any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in modifiers):
            return 77, {
                "status": "skip", "reason": "A modifier is held; refusing to inject a shortcut",
                "keyboard_injected": False,
            }
        if edit.text():
            return 77, {
                "status": "skip", "reason": "Input arrived before the probe; user may be typing",
                "keyboard_injected": False,
            }
        key_events = (Input * 2)()
        key_events[0].type = key_events[1].type = 1  # INPUT_KEYBOARD
        key_events[0].data.ki = KeyboardInput(0x41, 0, 0, 0, 0)
        key_events[1].data.ki = KeyboardInput(0x41, 0, 0x0002, 0, 0)  # KEYUP
        # Keep this final ownership check immediately next to the one atomic batch.
        if not owns_foreground():
            return 77, {
                "status": "skip", "reason": "Foreground changed before SendInput",
                "keyboard_injected": False,
            }
        sent = int(user32.SendInput(2, key_events, ctypes.sizeof(Input)))
        if sent != 2:
            raise AssertionError(f"SendInput delivered {sent}/2 keyboard events")
        pump(0.25)
        key_observed = [e for e in captured if e["type"] == "key" and e["vk"] == 0x41]
        assert edit.text().lower() == "a", f"Target input received {edit.text()!r}, expected 'a'"
        assert any(e["down"] for e in key_observed), "Hook missed A down"
        assert any(not e["down"] for e in key_observed), "Hook missed A up"
        assert observer.healthy and not observer.error, observer.error

        # Move a few pixels without clicking. The background hook should see it.
        mouse_event = Input()
        mouse_event.type = 0  # INPUT_MOUSE
        mouse_event.data.mi = MouseInput(2, 1, 0, 0x0001, 0, 0)
        pointer_start = time.monotonic()
        assert user32.SendInput(1, ctypes.byref(mouse_event), ctypes.sizeof(Input)) == 1
        pump(0.06)
        cursor_after_injection = get_cursor_pos()
        move_observed = [
            e for e in captured if e["type"] == "move" and e["time"] >= pointer_start
        ]
        assert move_observed, "Hook missed pointer movement"
        assert observer.healthy and not observer.error, observer.error
        return 0, {
            "status": "pass", "keyboard_injected": True,
            "target_received": edit.text(),
            "hook_key_down": any(e["down"] for e in key_observed),
            "hook_key_up": any(not e["down"] for e in key_observed),
            "hook_pointer_motion": True,
            "pointer_from": original_cursor, "pointer_to": cursor_after_injection,
            "hooks_healthy": observer.healthy,
        }
    except Exception as exc:
        return 1, {"status": "fail", "error": str(exc), "observer_error": observer.error}
    finally:
        # Do not override a new user movement if the pointer has changed meanwhile.
        if cursor_after_injection is not None and get_cursor_pos() == cursor_after_injection:
            user32.SetCursorPos(*original_cursor)
        if previous_ime:
            imm32.ImmAssociateContext(handle, previous_ime)
        owned_at_close = user32.GetForegroundWindow() == handle
        observer.stop()
        edit.close()
        app.processEvents()
        if owned_at_close and original_foreground and user32.IsWindow(original_foreground):
            user32.SetForegroundWindow(original_foreground)


if __name__ == "__main__":
    code, result = run()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(code)
