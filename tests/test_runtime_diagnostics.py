"""An actual blocked Qt callback must leave a diagnostic traceback."""
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication
from runtime_diagnostics import GuiWatchdog


class WatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_blocked_gui_callback_leaves_stack_and_watchdog_can_close(self):
        with tempfile.TemporaryDirectory() as profile:
            watch = GuiWatchdog(profile, timeout=.15, interval_ms=30)
            loop = QEventLoop()

            def slow_native_boundary():
                time.sleep(.3)
                loop.quit()

            QTimer.singleShot(30, slow_native_boundary)
            loop.exec_()
            watch.close()
            content = (Path(profile) / 'hang-trace.log').read_text(encoding='utf-8')
            self.assertIn('Timeout', content)
            self.assertIn('slow_native_boundary', content)
            self.assertIn('version=', content)
            watch.close()

    def test_responsive_gui_does_not_report_a_hang(self):
        with tempfile.TemporaryDirectory() as profile:
            watch = GuiWatchdog(profile, timeout=.15, interval_ms=30)
            loop = QEventLoop()
            QTimer.singleShot(300, loop.quit)
            loop.exec_()
            watch.close()
            content = (Path(profile) / 'hang-trace.log').read_text(encoding='utf-8')
            self.assertNotIn('Timeout', content)


if __name__ == '__main__':
    unittest.main()
