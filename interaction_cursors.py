"""Small, cached hand cursors for the cat's actual touch regions.

The hotspot is the finger's contact point, so changing the cursor never changes
where the application detects a touch. These are widget-local cursors; this
module never installs a global cursor override or changes the system cursor.
"""
from functools import lru_cache
import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPixmap


CURSOR_SIZE = 36
_REGION_STYLE = {
    'head': 'stroke', 'cheek': 'stroke', 'neck': 'scratch',
    'belly': 'tickle', 'paw': 'boop', 'tail': 'pinch',
}
# Logical (device-independent) coordinates, at the fingertip/contact gap.
HOTSPOTS = {'stroke': (17, 3), 'scratch': (20, 10),
            'tickle': (21, 3), 'boop': (15, 3), 'pinch': (8, 13)}


def _path(start, commands):
    path = QPainterPath(QPointF(*start))
    for kind, points in commands:
        if kind == 'L':
            path.lineTo(*points)
        elif kind == 'Q':
            path.quadTo(*points)
        elif kind == 'C':
            path.cubicTo(*points)
    path.closeSubpath()
    return path


def _hand(style):
    if style == 'stroke':
        return _path((14, 33), [
            ('L', (13, 29)), ('Q', (9, 27, 5, 22)),
            ('C', (2, 19, 4, 16, 7, 18)), ('L', (11, 22)),
            ('L', (9, 11)), ('C', (8, 7, 12, 6, 13, 10)),
            ('L', (15, 18)), ('L', (14, 6)),
            ('C', (13.7, 2, 18, 1.7, 18.5, 5.5)), ('L', (20, 17)),
            ('L', (20.5, 7)), ('C', (20.5, 3.5, 24.8, 4, 24.6, 7.5)),
            ('L', (24.5, 19)), ('L', (26.8, 13)),
            ('C', (28, 9.8, 31.5, 11.5, 30.3, 15)),
            ('L', (28.7, 25)), ('Q', (28, 28, 25, 31)),
            ('L', (25, 33)),
        ])
    if style == 'scratch':
        return _path((13, 33), [
            ('L', (12, 29)), ('Q', (8, 26, 5, 21)),
            ('C', (3, 18, 6, 16, 8, 18)), ('L', (12, 21)),
            ('L', (12, 11)), ('C', (12, 6, 13.5, 3, 17, 3)),
            ('C', (21.5, 3, 24.5, 6.5, 23, 9)),
            ('C', (22, 11.5, 19, 12, 18, 9.5)),
            ('Q', (16, 7.5, 16.5, 11)), ('L', (17, 16)),
            ('Q', (18, 13.5, 20.5, 14.5)), ('Q', (22, 15, 22, 17.5)),
            ('Q', (24, 15, 26, 17)), ('L', (27, 20)),
            ('Q', (29.5, 18.5, 31, 21)), ('L', (30, 26)),
            ('Q', (29, 29, 26, 31)), ('L', (26, 33)),
        ])
    if style == 'tickle':
        return _path((13, 33), [
            ('L', (12, 29)), ('Q', (8, 26, 5, 21)),
            ('C', (3, 18, 6, 16, 8, 18)), ('L', (12, 21)),
            ('L', (10, 8)), ('C', (9.4, 4, 13.5, 3.5, 14.2, 7)),
            ('L', (17, 18)), ('L', (18, 6)),
            ('C', (18.2, 1.8, 23, 2.2, 22.7, 6)), ('L', (22, 19)),
            ('Q', (24, 16, 26, 18)), ('L', (27, 21)),
            ('Q', (29, 19, 31, 22)), ('L', (30, 26)),
            ('Q', (29, 29, 26, 31)), ('L', (26, 33)),
        ])
    if style == 'boop':
        return _path((13, 33), [
            ('L', (12, 29)), ('Q', (8, 26, 5, 21)),
            ('C', (3, 18.5, 6, 16, 8, 18)), ('L', (12, 21)),
            ('L', (12, 6)), ('C', (12, 2, 17, 2, 17, 6)),
            ('L', (17, 16.5)), ('Q', (19, 14, 21, 15.5)),
            ('L', (22, 18)), ('Q', (24, 15.5, 26, 17.5)),
            ('L', (27, 21)), ('Q', (29.5, 19, 31, 22)),
            ('L', (30, 26)), ('Q', (29, 29, 27, 31)),
            ('L', (27, 33)),
        ])
    if style == 'pinch':
        return _path((13, 33), [
            ('L', (12, 30)), ('C', (9, 27, 7, 25, 7, 22)),
            ('C', (6, 19, 7, 16, 9, 15)),
            ('Q', (12, 14, 14, 17)), ('L', (17, 20)),
            ('C', (19, 21, 21, 19, 19, 17)), ('L', (14, 12)),
            ('C', (11, 10, 8, 13, 6, 10)),
            ('C', (4, 7, 7, 4, 10, 4)),
            ('C', (14, 4, 18, 7, 22, 11)), ('L', (27, 17)),
            ('Q', (30, 19, 30, 23)), ('Q', (30, 28, 26, 31)),
            ('L', (26, 33)),
        ])
    raise ValueError(f'Unknown hand style: {style}')


def _draw_hand(painter, style):
    painter.setRenderHint(QPainter.Antialiasing)
    hand = _hand(style)
    # A light outside edge keeps the dark outline legible over the black cat;
    # the inner dark outline stays legible over white coats and white windows.
    painter.setPen(QPen(QColor('#fffaf0'), 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(QColor('#fff5df'))
    painter.drawPath(hand)
    painter.setPen(QPen(QColor('#34353d'), 1.65, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawPath(hand)

    painter.save()
    painter.setClipPath(hand)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor('#ead9b9'))
    shade = QPainterPath(QPointF(8, 26))
    shade.cubicTo(15, 30, 23, 29, 29, 25)
    shade.lineTo(30, 36)
    shade.lineTo(7, 36)
    shade.closeSubpath()
    painter.drawPath(shade)
    painter.restore()
    # Restore the lower outline after the clipped palm shadow.
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor('#34353d'), 1.65, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawPath(hand)
    painter.setPen(QPen(QColor('#9f8b70'), 1.0, Qt.SolidLine, Qt.RoundCap))
    crease = QPainterPath()
    if style == 'stroke':
        crease.moveTo(15, 24)
        crease.quadTo(19, 21, 24, 23)
    elif style == 'pinch':
        crease.moveTo(22, 15)
        crease.lineTo(25, 19)
        crease.moveTo(22, 25)
        crease.quadTo(17, 24, 14, 27)
    else:
        crease.moveTo(21, 18)
        crease.lineTo(21, 23)
        crease.moveTo(25.5, 21)
        crease.lineTo(25.5, 24.5)
        crease.moveTo(14.5, 25)
        crease.quadTo(17, 23, 19, 25)
    painter.drawPath(crease)


def render_cursor_image(style, dpr=1.0):
    """Render a hand at the requested DPR (also used by the preview tool)."""
    pixels = math.ceil(CURSOR_SIZE * dpr)
    image = QImage(pixels, pixels, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    image.setDevicePixelRatio(dpr)
    painter = QPainter(image)
    _draw_hand(painter, style)
    painter.end()
    return image


@lru_cache(maxsize=40)
def _cached_cursor(style, dpr):
    if style is None:
        return QCursor(Qt.ArrowCursor)
    pixmap = QPixmap.fromImage(render_cursor_image(style, dpr))
    return QCursor(pixmap, *HOTSPOTS[style])


def get_interaction_cursor(region, dpr=1.0):
    """Return a cached Qt cursor; call only on the GUI thread after QApplication.

    Unknown regions use the ordinary arrow. DPR is rounded to quarter steps to
    keep cache size bounded while covering common Windows display scales.
    """
    try:
        ratio = float(dpr)
        if not math.isfinite(ratio):
            ratio = 1.0
    except (TypeError, ValueError):
        ratio = 1.0
    ratio = round(max(1.0, min(4.0, ratio)) * 4) / 4
    return _cached_cursor(_REGION_STYLE.get(region), ratio)
