"""Exercise the actual Qt menu and hover/drag routing without global hooks."""
from pathlib import Path
import json
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication
import black_cat as app_module


class QuietInput:
    def __init__(self):
        self.events = queue.Queue()
        self.healthy = True

    def start(self):
        pass

    def stop(self):
        pass


class WindowInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.profile = tempfile.TemporaryDirectory(prefix='littlecat-test-')
        self.addCleanup(self.profile.cleanup)
        patches = [patch.object(app_module, 'APP_DIR', Path(self.profile.name)),
                   patch.object(app_module, 'GlobalInput', QuietInput),
                   patch.object(app_module.PetWindow, 'show', lambda self: None),
                   patch.object(app_module.PetWindow, 'apply_native_style', lambda self: None),
                   patch.object(app_module, 'get_cursor_pos', return_value=(0, 0))]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        args = SimpleNamespace(skin=None, demo=False, smoke_test=999, capture=None, report=None)
        self.window = app_module.PetWindow(self.app, args)
        self.window.timer.stop()
        self.window.tray.hide()
        self.window.settings['sound'] = False
        self.addCleanup(self.window.cleanup)

    def test_menu_switches_skin_and_persists_it_across_loading(self):
        window = self.window
        for skin in app_module.SKINS:
            window.skin_actions[skin].trigger()
            self.assertEqual(window.state['skin'], skin)
            self.assertEqual(app_module.load_settings()['skin'], skin)
            self.assertEqual([key for key, action in window.skin_actions.items() if action.isChecked()], [skin])
            self.assertFalse(window.tray.icon().isNull())
        saved = json.loads((Path(self.profile.name) / 'settings.json').read_text(encoding='utf-8'))
        saved['skin'] = 'removed-custom-skin'
        (Path(self.profile.name) / 'settings.json').write_text(json.dumps(saved), encoding='utf-8')
        self.assertEqual(app_module.load_settings()['skin'], 'black')

    def test_random_skin_changes_coat_and_saves_the_selection(self):
        old = self.window.settings['skin']
        self.window.random_skin()
        self.assertNotEqual(self.window.settings['skin'], old)
        self.assertEqual(app_module.load_settings()['skin'], self.window.settings['skin'])

    def test_play_menu_runs_actions_and_pause_cancels_them(self):
        window = self.window
        for play in ('feed', 'toy'):
            window.play_actions[play].trigger()
            state = window.animation.update(window.animation.now + .02)
            self.assertEqual(state['play_action'], play)
        window.pause_action.setChecked(True)
        self.assertFalse(window.start_play('feed'))
        self.assertIsNone(window.animation.update(window.animation.now + .1)['play_action'])
        self.assertTrue(all(not action.isEnabled() for action in window.play_actions.values()))
        window.pause_action.setChecked(False)
        self.assertTrue(window.start_play('feed'))

    def test_hover_routes_to_model_and_is_suppressed_by_drag_menu_and_pass_through(self):
        window = self.window
        with patch.object(app_module, 'hit_test', return_value='head'), \
                patch.object(window.animation, 'set_touch', wraps=window.animation.set_touch) as touch:
            window.tick()
            self.assertEqual(touch.call_args.args[0], 'head')
            window.dragging = True
            window.tick()
            self.assertIsNone(touch.call_args.args[0])
            window.set_click_through(True)
            self.assertFalse(window.dragging)
            self.assertIsNone(window.drag_offset)
            window.tick()
            self.assertIsNone(touch.call_args.args[0])
            window.set_click_through(False)
            with patch.object(window.menu, 'isVisible', return_value=True):
                window.tick()
                self.assertIsNone(touch.call_args.args[0])
            window.petting_action.setChecked(False)
            window.tick()
            self.assertIsNone(touch.call_args.args[0])
            window.petting_action.setChecked(True)
            window.tick()
            self.assertEqual(touch.call_args.args[0], 'head')

    def test_small_hand_motion_is_petting_and_deliberate_drag_moves_the_window(self):
        window = self.window
        before = window.pos()
        point = before + app_module.QPoint(100, 100)

        def event(kind, delta=0, button=Qt.NoButton, buttons=Qt.LeftButton):
            return QMouseEvent(kind, QPointF(100 + delta, 100),
                               QPointF(point.x() + delta, point.y()), button, buttons, Qt.NoModifier)

        window.mousePressEvent(event(QEvent.MouseButtonPress, button=Qt.LeftButton))
        window.mouseMoveEvent(event(QEvent.MouseMove, 1))
        self.assertFalse(window.dragging)
        self.assertEqual(window.pos(), before)
        delta = QApplication.startDragDistance() + 12
        window.mouseMoveEvent(event(QEvent.MouseMove, delta))
        self.assertTrue(window.dragging)
        self.assertEqual(window.x(), before.x() + delta)
        window.mouseReleaseEvent(event(QEvent.MouseButtonRelease, delta, Qt.LeftButton, Qt.NoButton))
        self.assertFalse(window.dragging)
        self.assertIsNone(window.drag_offset)
        self.assertEqual(app_module.load_settings()['x'], window.x())

    def test_three_light_clicks_including_qt_double_click_trigger_the_combo(self):
        window = self.window
        point = QPointF(265 * window.scale, 115 * window.scale)
        global_point = QPointF(window.x() + point.x(), window.y() + point.y())
        now = window.animation.now
        for index in range(3):
            now += .15
            kind = QEvent.MouseButtonDblClick if index == 1 else QEvent.MouseButtonPress
            press = QMouseEvent(kind, point, global_point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
            release = QMouseEvent(QEvent.MouseButtonRelease, point, global_point,
                                  Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
            with patch.object(app_module.time, 'monotonic', return_value=now):
                if index == 1:
                    window.mouseDoubleClickEvent(press)
                else:
                    window.mousePressEvent(press)
                window.mouseReleaseEvent(release)
            window.state = window.animation.update(now + .01)
        self.assertEqual(window.state['play_action'], 'dizzy')
        self.assertFalse(window.dragging)

    def test_dragging_never_triggers_a_tap(self):
        window = self.window
        point = QPointF(265 * window.scale, 115 * window.scale)
        global_point = QPointF(window.x() + point.x(), window.y() + point.y())
        offset = QPointF(QApplication.startDragDistance() + 15, 0)
        with patch.object(window.animation, 'tap', wraps=window.animation.tap) as tap:
            window.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, point, global_point,
                                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            window.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, point + offset, global_point + offset,
                                              Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            window.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, point + offset,
                                                 global_point + offset, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
            tap.assert_not_called()

    def test_stationary_cursor_pets_the_visible_head_and_belly_during_body_motion(self):
        window = self.window
        now = window.animation.now
        for region, point in [('head', (265, 115)), ('belly', (265, 293))]:
            cursor = (window.x() + point[0] * window.scale,
                      window.y() + point[1] * window.scale)
            with patch.object(app_module, 'get_cursor_pos', return_value=cursor):
                for _ in range(75):
                    now += .02
                    with patch.object(app_module.time, 'monotonic', return_value=now):
                        window.tick()
            self.assertEqual(window.state['touch_region'], region)
            self.assertGreater(window.state['touch_strength'], .85)

    def test_hover_cursor_matches_region_immediately_and_reuses_installed_cursor(self):
        window = self.window
        with patch.object(app_module, 'hit_test') as hit, \
                patch.object(window, 'setCursor', wraps=window.setCursor) as installed:
            shapes = {}
            for region in ('head', 'cheek', 'neck', 'belly', 'paw', 'tail'):
                hit.return_value = region
                window.tick()
                self.assertEqual(window.cursor().shape(), Qt.BitmapCursor)
                expected = app_module.get_interaction_cursor(region, window.devicePixelRatioF())
                self.assertEqual(window.cursor().hotSpot(), expected.hotSpot())
                self.assertEqual(window.cursor().pixmap().cacheKey(), expected.pixmap().cacheKey())
                shapes[region] = expected.pixmap().cacheKey()
                count = installed.call_count
                for _ in range(4):
                    window.tick()
                self.assertEqual(installed.call_count, count)
            self.assertEqual(shapes['head'], shapes['cheek'])
            self.assertEqual(len(set(shapes.values())), 5)
            hit.return_value = None
            window.tick()
            self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
        self.assertIsNone(QApplication.overrideCursor())

    def test_hand_cursor_resets_on_disable_pause_menu_leave_and_pass_through(self):
        window = self.window
        with patch.object(app_module, 'hit_test', return_value='neck'):
            for disable, enable in (
                (lambda: window.set_petting(False), lambda: window.set_petting(True)),
                (lambda: window.set_paused(True), lambda: window.set_paused(False)),
                (lambda: window.set_click_through(True), lambda: window.set_click_through(False)),
            ):
                window.tick()
                self.assertEqual(window.cursor().shape(), Qt.BitmapCursor)
                disable()
                self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
                window.tick()
                self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
                enable()
                self.assertEqual(window.cursor().shape(), Qt.BitmapCursor)
            window.menu.aboutToShow.emit()
            self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
            with patch.object(window.menu, 'isVisible', return_value=True):
                window.tick()
                self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
            window.tick()
            window.leaveEvent(QEvent(QEvent.Leave))
            self.assertEqual(window.cursor().shape(), Qt.ArrowCursor)
            window.enterEvent(QEvent(QEvent.Enter))
            self.assertEqual(window.cursor().shape(), Qt.BitmapCursor)

    def test_drag_cursor_takes_priority_then_restores_hand_at_release(self):
        window = self.window
        point = QPointF(212, 201)
        global_point = QPointF(window.x() + point.x(), window.y() + point.y())
        offset = QPointF(QApplication.startDragDistance() + 15, 0)
        with patch.object(app_module, 'hit_test', return_value='neck'):
            window.tick()
            window.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, point, global_point,
                                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            window.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, point + offset, global_point + offset,
                                              Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            window.tick()
            self.assertTrue(window.dragging)
            self.assertEqual(window.cursor().shape(), Qt.ClosedHandCursor)
            window.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, point,
                                                 global_point + offset, Qt.LeftButton,
                                                 Qt.NoButton, Qt.NoModifier))
            self.assertFalse(window.dragging)
            self.assertEqual(window.cursor().shape(), Qt.BitmapCursor)


if __name__ == '__main__':
    unittest.main()
