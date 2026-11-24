"""Capture a blocked GUI's Python stack without recording user input."""
import faulthandler
from pathlib import Path
import platform
import time

from PyQt5.QtCore import QTimer, QT_VERSION_STR, PYQT_VERSION_STR

APP_VERSION = '3.2.0'


def runtime_description():
    return (f'version={APP_VERSION} os={platform.platform()} '
            f'arch={platform.machine()} python={platform.python_version()} '
            f'qt={QT_VERSION_STR} pyqt={PYQT_VERSION_STR}')


class GuiWatchdog:
    """Rearm a native watchdog from Qt; a frozen event loop leaves it armed.

    faulthandler's native thread can dump stacks even when another native call
    holds Python's GIL, unlike a Python thread watching a heartbeat variable.
    It never terminates the app or records key values, text, or screen pixels.
    """
    def __init__(self, directory, timeout=8.0, interval_ms=2000):
        self.closed = False
        self.timeout = timeout
        folder = Path(directory)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'hang-trace.log'
        # Bound diagnostics on disk, keeping the previous trace for comparison.
        if path.exists() and path.stat().st_size > 1_000_000:
            previous = folder / 'hang-trace.previous.log'
            previous.write_bytes(path.read_bytes()[-1_000_000:])
            path.write_bytes(b'')
        self.file = path.open('a', encoding='utf-8')
        self.file.write(f'\nSession {time.strftime("%Y-%m-%d %H:%M:%S")} {runtime_description()}\n')
        self.file.write(f'If the GUI stops processing events, the stack follows after {timeout:g} seconds.\n')
        self.file.flush()
        self.timer = QTimer()
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.beat)
        self.beat()
        self.timer.start()

    def beat(self):
        if not self.closed:
            faulthandler.dump_traceback_later(self.timeout, repeat=False, file=self.file)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        faulthandler.cancel_dump_traceback_later()
        self.file.close()
