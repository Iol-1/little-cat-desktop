"""Render the actual desktop artwork in repeatable input poses."""
from pathlib import Path
import sys
import importlib.util
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from animation import CatAnimation
from cat_renderer import draw_pet, key_target, KEYS, make_icon
from scene_layout import CANVAS_W, CANVAS_H


def make_poses():
    labels = {k['vk']: k['label'] for k in KEYS}
    cat = CatAnimation(key_target, labels, now=100)
    idle = cat.update(100)
    cat.mouse_screen = (100, 100)
    cat.handle({'type': 'move', 'time': 100, 'x': 125, 'y': 95})
    cat.set_gaze(-.55, -.12)
    for i in range(36):
        mouse = cat.update(100 + i / 120)
    cat = CatAnimation(key_target, labels, now=200)
    cat.mouse_screen = (100, 100)
    for i in range(84):
        t = 200 + i / 120
        if i % 7 == 0:
            for vk in list(cat.pressed):
                cat.handle({'type': 'key', 'time': t, 'vk': vk, 'down': False})
            cat.handle({'type': 'key', 'time': t, 'vk': ord('ASDFJKLQWER'[i // 7 % 11]), 'down': True})
            cat.handle({'type': 'move', 'time': t, 'x': 100 + i, 'y': 100})
        cat.set_gaze(.6, -.35)
        busy = cat.update(t)
    cat = CatAnimation(key_target, labels, now=300)
    for i in range(180):
        sleep = cat.update(346 + i / 120)
    return idle, mouse, busy, sleep


def panel(p, state, x, y, scale=.8, renderer=draw_pet):
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    renderer(p, state, 206)
    p.restore()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='analysis/v2')
    parser.add_argument('--baseline', help='Optional older renderer for a before/after comparison')
    parser.add_argument('--before-label', default='第一版')
    args = parser.parse_args()
    app = QApplication([])
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    poses = make_poses()
    strip = QImage(1260, 430, QImage.Format_ARGB32_Premultiplied)
    strip.fill(QColor('#e4e8e5'))
    p = QPainter(strip)
    p.setRenderHint(QPainter.Antialiasing)
    for i, (label, state) in enumerate(zip(('跟随鼠标', '边打字边动鼠标', '睡觉'), poses[1:])):
        panel(p, state, i * 420, 5)
        p.setFont(QFont('Microsoft YaHei', 10))
        p.setPen(QColor('#51605a'))
        p.drawText(QRectF(i * 420, 402, 420, 24), Qt.AlignCenter, label)
    p.end()
    strip.save(str(out / 'preview.png'))
    if args.baseline:
        spec = importlib.util.spec_from_file_location('previous_renderer', ROOT / args.baseline)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        baseline = (dict(poses[0], left_paw=(226, 335), right_paw=(300, 335), mouse=(70, 390))
                    if 'v1-backup' in args.baseline else dict(poses[0]))
        compare = QImage(1040, 540, QImage.Format_ARGB32_Premultiplied)
        compare.fill(QColor('#e4e8e5'))
        p = QPainter(compare)
        p.setRenderHint(QPainter.Antialiasing)
        panel(p, baseline, 0, 0, 1.0, old.draw_pet)
        panel(p, poses[0], 520, 0, 1.0)
        p.setFont(QFont('Microsoft YaHei', 12))
        p.setPen(QColor('#51605a'))
        p.drawText(QRectF(0, 496, 520, 30), Qt.AlignCenter, args.before_label)
        p.drawText(QRectF(520, 496, 520, 30), Qt.AlignCenter, '这次调整')
        p.end()
        compare.save(str(out / 'comparison.png'))
    # Check articulation against a dark desktop too.
    dark = QImage(CANVAS_W, CANVAS_H, QImage.Format_ARGB32_Premultiplied)
    dark.fill(QColor('#252b31'))
    p = QPainter(dark)
    p.setRenderHint(QPainter.Antialiasing)
    panel(p, poses[2], 0, 0, 1.0)
    p.end()
    dark.save(str(out / 'dark-desktop.png'))
    make_icon().pixmap(256, 256).save(str(ROOT / 'assets' / 'black-cat.png'))
    print(out)


if __name__ == '__main__':
    main()
