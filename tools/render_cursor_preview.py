"""Show the five interaction hands at normal size and enlarged for the user."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication
from interaction_cursors import CURSOR_SIZE, HOTSPOTS, get_interaction_cursor, render_cursor_image


def main():
    app = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parents[1] / 'analysis' / 'v7' / 'cursors-preview.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(1000, 460, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor('#e6e3df'))
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setFont(QFont('Microsoft YaHei UI', 13))
    p.setPen(QColor('#34353d'))
    p.drawText(26, 33, '摸到哪里，手势就跟着变')
    p.setFont(QFont('Microsoft YaHei UI', 9))
    p.setPen(QColor('#817367'))
    p.drawText(QRectF(500, 13, 470, 26), Qt.AlignRight | Qt.AlignVCenter,
               '上方：实际大小，浅色 / 深色背景　下方：放大预览')
    entries = [('头顶 · 脸颊', '轻轻摸摸，蹭一蹭', 'stroke', 'head'),
               ('脖子', '弯弯食指，挠挠痒', 'scratch', 'neck'),
               ('肚子', '伸出两指，轻轻挠', 'tickle', 'belly'),
               ('爪子', '伸出食指，碰一碰', 'boop', 'paw'),
               ('尾巴', '轻捏手势，逗一逗', 'pinch', 'tail')]
    for index, (name, description, style, region) in enumerate(entries):
        x = 20 + index * 196
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#fffdf8'))
        p.drawRoundedRect(QRectF(x, 55, 184, 380), 12, 12)
        p.setPen(QColor('#34353d'))
        p.setFont(QFont('Microsoft YaHei UI', 11, QFont.DemiBold))
        p.drawText(QRectF(x, 68, 184, 24), Qt.AlignCenter, name)
        actual = render_cursor_image(style)
        p.drawImage(QPointF(x + 35, 112), actual)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#292c35'))
        p.drawRoundedRect(QRectF(x + 93, 102, 65, 56), 8, 8)
        p.drawImage(QPointF(x + 108, 112), actual)
        detail = render_cursor_image(style, 4)
        p.drawImage(QRectF(x + 20, 204, CURSOR_SIZE * 4, CURSOR_SIZE * 4), detail)
        hx, hy = HOTSPOTS[style]
        p.setFont(QFont('Microsoft YaHei UI', 10))
        p.setPen(QColor('#817367'))
        p.drawText(QRectF(x, 384, 184, 24), Qt.AlignCenter, description)
        for ratio in (1, 1.5, 2):
            cursor = get_interaction_cursor(region, ratio)
            assert cursor.pixmap().width() == round(CURSOR_SIZE * ratio)
            assert cursor.pixmap().devicePixelRatio() == ratio
            assert cursor.hotSpot().x() == hx and cursor.hotSpot().y() == hy
            assert get_interaction_cursor(region, ratio) is cursor
    assert get_interaction_cursor(None).shape() == Qt.ArrowCursor
    p.end()
    assert image.save(str(output))
    print(str(output))


if __name__ == '__main__':
    main()
