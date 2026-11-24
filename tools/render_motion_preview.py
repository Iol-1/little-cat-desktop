"""Capture the real animation model/renderer as a compact demonstration GIF."""
from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication
from animation import CatAnimation
from cat_renderer import KEYS, draw_pet, key_target


def main():
    app = QApplication([])
    out = ROOT / 'analysis' / 'v4'
    out.mkdir(parents=True, exist_ok=True)
    cat = CatAnimation(key_target, {k['vk']: k['label'] for k in KEYS}, now=100)
    cat.mouse_screen = (600, 400)
    frames = []
    for frame in range(150):
        elapsed = frame / 25
        now = 100 + elapsed
        if elapsed < 2.4:
            cat.set_touch(None, now)
            cat.set_gaze(math.sin(elapsed * 2.3), -.2)
            cat.handle({'type': 'move', 'x': int(600 + 160 * math.sin(elapsed * 3)),
                        'y': int(400 + 50 * math.cos(elapsed * 2)), 'time': now})
            if frame % 3 == 0:
                for vk in list(cat.pressed):
                    cat.handle({'type': 'key', 'vk': vk, 'down': False, 'time': now})
                cat.handle({'type': 'key', 'vk': ord('ASDFJKLQWERTY'[frame // 3 % 12]),
                            'down': True, 'time': now})
            label = '一起忙：肩膀、腰身跟着动'
        else:
            for vk in list(cat.pressed):
                cat.handle({'type': 'key', 'vk': vk, 'down': False, 'time': now})
            cat.set_gaze(0, 0)
            region = 'head' if elapsed < 4.1 else 'belly'
            cat.set_touch(region, now)
            label = '摸头：眯眼蹭蹭' if region == 'head' else '挠肚子：怕痒扭一扭'
        state = cat.update(now)
        state['skin'] = 'black'
        img = QImage(416, 424, QImage.Format_RGB32)
        img.fill(QColor('#e5e9e6'))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.save()
        painter.scale(.8, .8)
        draw_pet(painter, state, now)
        painter.restore()
        painter.setPen(QColor('#42564b'))
        painter.setFont(QFont('Microsoft YaHei', 10))
        painter.drawText(QRectF(0, 394, 416, 26), Qt.AlignCenter, label)
        painter.end()
        rgb = img.convertToFormat(QImage.Format_RGBA8888)
        data = rgb.bits()
        data.setsize(rgb.byteCount())
        frames.append(Image.frombytes('RGBA', (rgb.width(), rgb.height()), bytes(data)).convert('RGB'))
    frames[0].save(out / 'motion.gif', save_all=True, append_images=frames[1:],
                   duration=40, loop=0, optimize=False)
    print(out / 'motion.gif')


if __name__ == '__main__':
    main()
