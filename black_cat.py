"""Little black cat: an offline, input-driven Windows desktop companion."""
import argparse
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import queue
import random
import sys
import time

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication, QAction, QActionGroup, QMenu, QMessageBox, QSystemTrayIcon, QWidget

from animation import CatAnimation
from cat_renderer import CANVAS_W, CANVAS_H, KEYS, draw_pet, key_target, make_icon, resolve_vk, hit_test
from skins import SKINS
from native_input import GlobalInput, configure_window, get_cursor_pos
from scene_layout import FACE_CENTER
from sound_player import PurrPlayer
from runtime_diagnostics import APP_VERSION, GuiWatchdog, runtime_description
from interaction_cursors import get_interaction_cursor

APP_NAME = '小黑猫'
APP_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'LittleBlackCat'
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
LOG = logging.getLogger('blackcat')


def setup_logging():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(APP_DIR / 'app.log', maxBytes=150_000, backupCount=1, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def load_settings():
    defaults = {'scale': .80, 'sound': True, 'trails': True, 'sleep_after': 45,
                'click_through': False, 'skin': 'black', 'petting': True}
    try:
        data = json.loads((APP_DIR / 'settings.json').read_text(encoding='utf-8'))
        if isinstance(data, dict):
            defaults.update(data)
    except (OSError, ValueError):
        pass
    try:
        defaults['scale'] = max(.45, min(1.4, float(defaults['scale'])))
        defaults['sleep_after'] = max(10, min(300, int(defaults['sleep_after'])))
    except (TypeError, ValueError):
        defaults['scale'], defaults['sleep_after'] = .80, 45
    if defaults.get('skin') not in SKINS:
        defaults['skin'] = 'black'
    return defaults


class PetWindow(QWidget):
    def __init__(self, app, args):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.app, self.args = app, args
        self.settings = load_settings()
        if getattr(args, 'skin', None):
            self.settings['skin'] = args.skin
        if getattr(args, 'mute', False):
            self.settings['sound'] = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(make_icon(self.settings['skin']))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.scale = self.settings['scale']
        self.resize(round(CANVAS_W * self.scale), round(CANVAS_H * self.scale))
        labels = {k['vk']: k['label'] for k in KEYS}
        self.animation = CatAnimation(key_target, {vk: labels[resolve_vk(vk)] for vk in range(512)
                                                   if resolve_vk(vk) in labels})
        self.animation.sleep_after = self.settings['sleep_after']
        self.animation.trails_enabled = self.settings['trails']
        self.state = self.animation.update()
        self.state['skin'] = self.settings['skin']
        self.drag_offset = None
        self.drag_origin = None
        self.dragging = False
        self.tap_candidate = None
        self.purring = False
        self.sound = PurrPlayer(RESOURCE_DIR / 'assets' / 'purr.wav')
        self.sound_error = ''
        self.max_tick_ms = 0.0
        self.max_paint_ms = 0.0
        self.closing = False
        self.paused = False
        self._cursor_kind = None
        self.shortcut_down = set()
        self.input = GlobalInput()
        self.menu = self.build_menu()
        self.menu.aboutToShow.connect(self.clear_hover)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip('小猫 · 摸摸、轻点，右键喂食、逗猫或换毛色')
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.place_window()
        self.show()
        self.apply_native_style()
        try:
            self.input.start()
        except RuntimeError:
            LOG.exception('Global input could not start')
        self.animation.mouse_screen = get_cursor_pos()
        self.started = time.monotonic()
        self.demo_last_index = -1
        self.frame_count = 0
        if getattr(args, 'play', None):
            self.animation.start_play(args.play, self.started)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        app.aboutToQuit.connect(self.cleanup)
        LOG.info('Started desktop companion. Global input healthy=%s %s sound=%s',
                 self.input.healthy, runtime_description(), self.settings['sound'])
        if not self.input.healthy:
            QTimer.singleShot(500, lambda: self.tray.showMessage(APP_NAME, '键鼠监听未能启动，请退出后重新打开。', QSystemTrayIcon.Warning, 5000))
        elif not args.smoke_test:
            QTimer.singleShot(700, lambda: self.tray.showMessage(APP_NAME, '轻点不同部位逗逗它，连点头顶有彩蛋。右键可以喂食、逗毛线球，或换毛色。', QSystemTrayIcon.Information, 3500))

    def build_menu(self):
        menu = QMenu()
        title = menu.addAction(f'小猫 {APP_VERSION} · 陪你忙一会儿')
        title.setEnabled(False)
        menu.addSeparator()
        skins_menu = menu.addMenu('小猫毛色')
        self.skin_group = QActionGroup(skins_menu)
        self.skin_actions = {}
        for skin_id, skin in SKINS.items():
            action = skins_menu.addAction(make_icon(skin_id), skin['name'])
            action.setCheckable(True)
            action.setChecked(skin_id == self.settings['skin'])
            action.triggered.connect(lambda checked=False, value=skin_id: self.set_skin(value))
            self.skin_group.addAction(action)
            self.skin_actions[skin_id] = action
        skins_menu.addSeparator()
        skins_menu.addAction('换个随机毛色', self.random_skin)
        play_menu = menu.addMenu('陪它玩')
        self.play_actions = {}
        for play_id, label in [('feed', '喂一条小鱼干'), ('toy', '逗毛线球')]:
            self.play_actions[play_id] = play_menu.addAction(
                label, lambda checked=False, value=play_id: self.start_play(value))
        self.petting_action = menu.addAction('鼠标停在身上时摸摸')
        self.petting_action.setCheckable(True)
        self.petting_action.setChecked(bool(self.settings['petting']))
        self.petting_action.toggled.connect(self.set_petting)
        self.pause_action = menu.addAction('暂停跟随')
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.set_paused)
        self.trail_action = menu.addAction('快速打字的猫爪残影')
        self.trail_action.setCheckable(True)
        self.trail_action.setChecked(bool(self.settings['trails']))
        self.trail_action.toggled.connect(self.set_trails)
        self.sound_action = menu.addAction('打呼噜声音')
        self.sound_action.setCheckable(True)
        self.sound_action.setChecked(bool(self.settings['sound']))
        self.sound_action.toggled.connect(self.set_sound)
        self.through_action = menu.addAction('鼠标穿透（从托盘恢复）')
        self.through_action.setCheckable(True)
        self.through_action.setChecked(bool(self.settings['click_through']))
        self.through_action.toggled.connect(self.set_click_through)
        sizes = menu.addMenu('大小')
        group = QActionGroup(sizes)
        for title, scale in [('小一点', .60), ('标准', .80), ('大一点', 1.0), ('超大', 1.20)]:
            action = sizes.addAction(title)
            action.setCheckable(True)
            action.setChecked(abs(scale - self.scale) < .05)
            action.triggered.connect(lambda checked=False, value=scale: self.set_scale(value))
            group.addAction(action)
        sleep_menu = menu.addMenu('多久不操作后睡觉')
        sleep_group = QActionGroup(sleep_menu)
        for title, seconds in [('15 秒', 15), ('45 秒', 45), ('2 分钟', 120)]:
            action = sleep_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(self.settings['sleep_after'] == seconds)
            action.triggered.connect(lambda checked=False, value=seconds: self.set_sleep_after(value))
            sleep_group.addAction(action)
        menu.addSeparator()
        menu.addAction('移回屏幕右下角', self.reset_position)
        menu.addAction('试试打个盹', lambda: QTimer.singleShot(600, self.take_nap))
        menu.addAction('操作说明', self.show_help)
        menu.addAction('打开诊断日志文件夹', self.open_diagnostics)
        menu.addSeparator()
        menu.addAction('退出小黑猫    Ctrl+Alt+Shift+Q', self.app.quit)
        return menu

    def apply_native_style(self):
        configure_window(int(self.winId()), bool(self.settings['click_through']))

    def save_settings(self):
        self.settings.update({'x': self.x(), 'y': self.y(), 'scale': self.scale})
        try:
            temp = APP_DIR / 'settings.tmp'
            payload = json.dumps(self.settings, ensure_ascii=False, indent=2)
            temp.write_text(payload, encoding='utf-8')
            try:
                temp.replace(APP_DIR / 'settings.json')
            except OSError as error:
                # Some redirected Windows profiles reject atomic rename even
                # between sibling paths. These small preferences can be copied.
                if getattr(error, 'winerror', None) != 17:
                    raise
                (APP_DIR / 'settings.json').write_text(payload, encoding='utf-8')
        except OSError:
            LOG.exception('Could not save settings')

    def place_window(self):
        try:
            if 'x' in self.settings and 'y' in self.settings:
                x, y = int(self.settings['x']), int(self.settings['y'])
                body = QPoint(x + self.width() // 2, y + self.height() // 2)
                if any(screen.availableGeometry().contains(body) for screen in self.app.screens()):
                    self.move(x, y)
                    return
        except (TypeError, ValueError):
            pass
        self.reset_position(save=False)

    def reset_position(self, checked=False, save=True):
        area = self.app.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 28, area.bottom() - self.height() - 18)
        if save:
            self.save_settings()

    def set_scale(self, scale):
        bottom = self.y() + self.height()
        self.scale = scale
        self.resize(round(CANVAS_W * scale), round(CANVAS_H * scale))
        self.move(self.x(), bottom - self.height())
        self.save_settings()

    def set_trails(self, checked):
        self.settings['trails'] = checked
        self.animation.trails_enabled = checked
        self.save_settings()

    def set_skin(self, skin_id):
        if skin_id not in SKINS:
            return
        self.settings['skin'] = skin_id
        self.state['skin'] = skin_id
        icon = make_icon(skin_id)
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)
        self.skin_actions[skin_id].setChecked(True)
        self.update()
        self.save_settings()

    def set_petting(self, checked):
        self.settings['petting'] = checked
        self.refresh_hover()
        self.save_settings()

    def random_skin(self):
        choices = [skin for skin in SKINS if skin != self.settings['skin']]
        if choices:
            self.set_skin(random.choice(choices))

    def start_play(self, action):
        if self.paused or self.dragging:
            return False
        self.animation.set_touch(None)
        return self.animation.start_play(action)

    def set_sound(self, checked):
        self.settings['sound'] = checked
        if not checked:
            self.stop_purr()
        self.save_settings()

    def set_click_through(self, checked):
        self.settings['click_through'] = checked
        if checked:
            self.drag_offset = None
            self.drag_origin = None
            self.dragging = False
            self.tap_candidate = None
            self.animation.set_touch(None)
        self.refresh_hover()
        self.apply_native_style()
        self.save_settings()

    def set_sleep_after(self, seconds):
        self.settings['sleep_after'] = seconds
        self.animation.sleep_after = seconds
        self.save_settings()

    def set_paused(self, checked):
        self.paused = checked
        self.animation.pressed.clear()
        self.animation.mouse_buttons.clear()
        self.animation.strokes = {'left': None, 'right': None}
        self.animation.last_activity = time.monotonic()
        self.animation.set_touch(None)
        self.animation.cancel_play()
        self.tap_candidate = None
        for action in self.play_actions.values():
            action.setEnabled(not checked)
        self.stop_purr()
        self.refresh_hover()

    def take_nap(self):
        self.animation.cancel_play()
        self.animation.pressed.clear()
        self.animation.mouse_buttons.clear()
        self.animation.force_sleep = True

    def show_help(self):
        QMessageBox.information(self, '小黑猫 · 操作说明',
            '移动鼠标：眼睛和头跟随光标，猫爪推动小鼠标。\n'
            '敲击键盘：猫爪敲相应位置，快速输入出现残影。\n'
            '鼠标和键盘同时操作：两只爪子会一起忙。\n'
            '停一会儿：小猫闭眼休息，轻轻打呼噜。\n\n'
            '鼠标停在身上：光标变成对应的小手，头顶和脸颊可抚摸，脖子和肚子可挠痒，爪子和尾巴也有互动。\n'
            '轻点不同部位：吃惊、蹭脸、怕痒、缩爪或回头。连续轻点头顶三下有晃脑袋彩蛋。\n'
            '右键 → 陪它玩：喂小鱼干，或逗毛线球。\n'
            f'右键 → 小猫毛色：{len(SKINS)} 种毛色，可随机换一只，选择会记住。\n\n'
            '拖动小猫：调整位置。右键或托盘：设置、退出。\n'
            'Ctrl+Alt+Shift+M：开关鼠标穿透。\n'
            'Ctrl+Alt+Shift+Q：退出。\n\n'
            '小猫离线运行，只使用即时按键状态，不保存输入内容。')

    def open_diagnostics(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR)))

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.through_action.setChecked(False)
            self.show()
            self.apply_native_style()

    def handle_shortcut(self, event):
        if event['type'] != 'key':
            return False
        vk = event['vk']
        if not event['down']:
            self.shortcut_down.discard(vk)
            return False
        pressed = self.animation.pressed
        ctrl = bool(pressed & {0x11, 0xA2, 0xA3})
        alt = bool(pressed & {0x12, 0xA4, 0xA5})
        shift = bool(pressed & {0x10, 0xA0, 0xA1})
        if ctrl and alt and shift and vk in (ord('Q'), ord('M')):
            if vk not in self.shortcut_down:
                self.shortcut_down.add(vk)
                if vk == ord('Q'):
                    self.app.quit()
                else:
                    self.through_action.setChecked(not self.through_action.isChecked())
            return True
        return False

    def demo_events(self, now):
        elapsed = now - self.started
        # Deterministic input for visual smoke tests, never injects OS keystrokes.
        index = int(elapsed * 14)
        if index != self.demo_last_index:
            self.demo_last_index = index
            sequence = 'ASDFJKLQWERTYUIOP'
            vk = ord(sequence[index % len(sequence)])
            if self.animation.pressed:
                for held in list(self.animation.pressed):
                    self.animation.handle({'type': 'key', 'vk': held, 'down': False, 'time': now})
            self.animation.handle({'type': 'key', 'vk': vk, 'down': True, 'time': now})
            self.animation.handle({'type': 'move', 'x': int(900 + 220 * math.sin(elapsed * 3)),
                                   'y': int(500 + 140 * math.cos(elapsed * 2)), 'time': now})
        self.animation.set_gaze(math.sin(elapsed * 1.8), math.cos(elapsed * 1.6) * .8)

    def update_interaction_cursor(self, region):
        # Set only this widget's cursor; other apps and menus keep their own.
        kind = 'drag' if self.dragging else region
        dpr = self.devicePixelRatioF()
        key = (kind, dpr)
        if key != self._cursor_kind:
            if kind == 'drag':
                self.setCursor(Qt.ClosedHandCursor)
            elif kind is None:
                self.unsetCursor()
            else:
                self.setCursor(get_interaction_cursor(kind, dpr))
            self._cursor_kind = key

    def clear_hover(self):
        self.animation.set_touch(None)
        self.update_interaction_cursor(None)

    def refresh_hover(self, now=None, position=None):
        now = time.monotonic() if now is None else now
        region = None
        if (self.settings['petting'] and not self.settings['click_through']
                and not self.dragging and not self.menu.isVisible() and not self.paused):
            x, y = get_cursor_pos() if position is None else (position.x(), position.y())
            region = hit_test(((x - self.x()) / self.scale, (y - self.y()) / self.scale),
                              self.state, now)
        self.animation.set_touch(region, now)
        self.update_interaction_cursor(region)
        return region

    def enterEvent(self, event):
        self.refresh_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.clear_hover()
        super().leaveEvent(event)

    def tick(self):
        if self.closing:
            return
        frame_started = time.perf_counter()
        try:
            now = time.monotonic()
            for _ in range(2048):
                try:
                    event = self.input.events.get_nowait()
                except queue.Empty:
                    break
                # Windows uses VK_RETURN for both Enter keys; the extended
                # flag identifies the physical Enter in the new numeric pad.
                if event['type'] == 'key' and event['vk'] == 13 and event.get('extended'):
                    event = dict(event, vk=0x10D)
                if self.handle_shortcut(event):
                    continue
                # Keep modifier state while paused so global recovery shortcuts work.
                if not self.paused or event['type'] == 'key':
                    self.animation.handle(event)
            if self.args.demo:
                self.demo_events(now)
            else:
                x, y = get_cursor_pos()
                eye_x = self.x() + FACE_CENTER[0] * self.scale
                eye_y = self.y() + FACE_CENTER[1] * self.scale
                self.animation.set_gaze((x - eye_x) / (450 * self.scale), (y - eye_y) / (360 * self.scale))
                self.refresh_hover(now, QPointF(x, y))
            if not self.paused:
                self.state = self.animation.update(now)
                self.state['skin'] = self.settings['skin']
                self.update()
                self.sync_purr()
                interval = 33 if self.state['sleep'] > .9 else 16
                if self.timer.interval() != interval:
                    self.timer.setInterval(interval)
            self.frame_count += 1
            if self.args.smoke_test and now - self.started >= self.args.smoke_test:
                if self.args.capture:
                    self.save_render(self.args.capture)
                if self.args.report:
                    report = {'frames': self.frame_count, 'seconds': now - self.started,
                              'input_healthy': self.input.healthy, 'visible': self.isVisible(),
                              'ghost_count': len(self.state['ghosts']),
                              'skin': self.settings['skin'], 'body_lean': self.state.get('body_lean', 0),
                              'touch_region': self.state.get('touch_region'),
                              'play_action': self.state.get('play_action'),
                              'play_progress': self.state.get('play_progress'),
                              'skin_count': len(SKINS),
                              'version': APP_VERSION, 'sound_status': self.sound.status,
                              'max_tick_ms': self.max_tick_ms, 'max_paint_ms': self.max_paint_ms,
                              'left_paw': self.state['left_paw'], 'right_paw': self.state['right_paw'],
                              'position': [self.x(), self.y()], 'size': [self.width(), self.height()]}
                    Path(self.args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
                self.app.quit()
        except Exception:
            LOG.exception('Animation tick failed')
            self.app.quit()
        finally:
            elapsed_ms = (time.perf_counter() - frame_started) * 1000
            self.max_tick_ms = max(self.max_tick_ms, elapsed_ms)
            if elapsed_ms > 250:
                LOG.warning('Slow animation tick %.1f ms', elapsed_ms)

    def sync_purr(self):
        enjoying_touch = (self.state.get('touch_region') in ('head', 'cheek', 'neck')
                          and self.state.get('touch_strength', 0) > .8
                          and not self.state.get('play_action'))
        should_purr = self.settings['sound'] and (self.state['sleep'] > .92 or enjoying_touch)
        if should_purr and not self.purring:
            self.sound.set_playing(True)
            self.purring = True
        elif not should_purr and self.purring:
            self.stop_purr()
        if self.sound.error and self.sound.error != self.sound_error:
            self.sound_error = self.sound.error
            LOG.warning('Purr disabled after audio error: %s', self.sound_error)

    def stop_purr(self):
        self.sound.set_playing(False)
        self.purring = False

    def paintEvent(self, event):
        paint_started = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.scale(self.width() / CANVAS_W, self.height() / CANVAS_H)
        draw_pet(painter, self.state, time.monotonic())
        painter.end()
        elapsed_ms = (time.perf_counter() - paint_started) * 1000
        self.max_paint_ms = max(self.max_paint_ms, elapsed_ms)
        if elapsed_ms > 250:
            LOG.warning('Slow paint %.1f ms skin=%s', elapsed_ms, self.settings['skin'])

    def save_render(self, path):
        image = QImage(CANVAS_W * 2, CANVAS_H * 2, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(2, 2)
        draw_pet(painter, self.state, time.monotonic())
        painter.end()
        if not image.save(str(path)):
            raise OSError('Could not save preview')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.settings['click_through']:
            self.drag_offset = event.globalPos() - self.pos()
            self.drag_origin = event.globalPos()
            self.dragging = False
            point = (event.pos().x() / self.scale, event.pos().y() / self.scale)
            now = time.monotonic()
            region = hit_test(point, self.state, now)
            self.tap_candidate = (region, now, 'left' if point[0] < FACE_CENTER[0] else 'right') if region else None
            event.accept()

    def mouseDoubleClickEvent(self, event):
        # Qt sends a double-click instead of the second press in a quick burst.
        self.mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            if not self.dragging and (event.globalPos() - self.drag_origin).manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
                self.tap_candidate = None
                self.animation.set_touch(None)
                self.update_interaction_cursor(None)
            if self.dragging:
                self.move(event.globalPos() - self.drag_offset)
        self.refresh_hover(position=event.globalPos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            moved = self.dragging
            candidate = self.tap_candidate
            self.tap_candidate = None
            self.drag_offset = None
            self.drag_origin = None
            self.dragging = False
            self.refresh_hover(position=event.globalPos())
            if moved:
                self.save_settings()
            elif candidate and not self.paused and not self.settings['click_through']:
                region, started, side = candidate
                now = time.monotonic()
                if now - started <= .5:
                    self.animation.tap(region, now, side=side)

    def contextMenuEvent(self, event):
        LOG.info('Menu opened')
        self.menu.exec_(event.globalPos())
        LOG.info('Menu closed')

    def closeEvent(self, event):
        self.app.quit()
        event.accept()

    def cleanup(self):
        if self.closing:
            return
        self.closing = True
        self.timer.stop()
        self.input.stop()
        self.stop_purr()
        self.sound.close()
        self.tray.hide()
        if not self.args.smoke_test:
            self.save_settings()
        LOG.info('Stopped cleanly after %d frames', self.frame_count)


def acquire_instance():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, 'Local\\LittleBlackCatDesktop_v1')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    exists = ctypes.get_last_error() == 183
    return handle, exists


def main():
    parser = argparse.ArgumentParser(description='小黑猫桌宠')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--smoke-test', type=float, default=0)
    parser.add_argument('--capture')
    parser.add_argument('--report')
    parser.add_argument('--skin', choices=list(SKINS))
    parser.add_argument('--play', choices=['feed', 'toy'])
    parser.add_argument('--mute', action='store_true', help='Start with purring sound disabled')
    args = parser.parse_args()
    setup_logging()
    mutex, exists = acquire_instance()
    if exists:
        return 0
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    def handle_error(exc_type, value, tb):
        LOG.error('Unhandled exception', exc_info=(exc_type, value, tb))
        app.quit()
    sys.excepthook = handle_error
    watchdog = None
    try:
        try:
            watchdog = GuiWatchdog(APP_DIR)
        except OSError:
            LOG.exception('Could not open hang diagnostics')
        window = PetWindow(app, args)
        return app.exec_()
    finally:
        if watchdog:
            watchdog.close()
        kernel = ctypes.windll.kernel32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    raise SystemExit(main())
