"""Render the real playful actions as an animated preview and contact sheet."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication
from animation import CatAnimation
from cat_renderer import draw_pet, key_target


def frame(state, now, label):
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
    return img


def main():
    app = QApplication([])
    out = ROOT / 'analysis' / 'v5'
    out.mkdir(parents=True, exist_ok=True)
    frames, snapshots = [], []
    scenarios = [('head', '轻点头顶：咦？', 'black', 1.3, .3),
                 ('dizzy', '连点彩蛋：晃晃脑袋', 'silver_tabby', 2.4, .8),
                 ('feed', '喂一条小鱼干', 'orange_tabby', 3.5, 1.4),
                 ('toy', '逗毛线球', 'cow', 4.4, 1.5)]
    for action, label, skin, seconds, snapshot_at in scenarios:
        cat = CatAnimation(key_target, now=100)
        if action in ('feed', 'toy'):
            cat.start_play(action, 100)
        else:
            cat.tap('head', 100)
        for index in range(round(seconds * 25)):
            elapsed = index / 25
            now = 100 + elapsed
            if action == 'dizzy' and index in (4, 8):
                cat.tap('head', now)
            state = cat.update(now)
            state['skin'] = skin
            img = frame(state, now, label)
            if index == round(snapshot_at * 25):
                snapshots.append(img.copy())
                img.save(str(out / f'{action}-preview.png'))
            rgba = img.convertToFormat(QImage.Format_RGBA8888)
            data = rgba.bits()
            data.setsize(rgba.byteCount())
            frames.append(Image.frombytes('RGBA', (rgba.width(), rgba.height()), bytes(data)).convert('RGB'))
    frames[0].save(out / 'play.gif', save_all=True, append_images=frames[1:], duration=40,
                   loop=0, optimize=False)
    strip = QImage(1248, 318, QImage.Format_RGB32)
    strip.fill(QColor('#e5e9e6'))
    painter = QPainter(strip)
    for index, img in enumerate(snapshots):
        painter.drawImage(QRectF(index * 312, 0, 312, 318), img)
    painter.end()
    strip.save(str(out / 'play-preview.png'))
    print(out / 'play.gif')


if __name__ == '__main__':
    main()
