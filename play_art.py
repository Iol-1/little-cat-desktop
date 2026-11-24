"""Small, transient toys and reaction marks for the desktop cat's play actions."""
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainterPath, QPen

from scene_layout import CANVAS_H, CANVAS_W


def _pen(color, width=1.5):
    return QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _curve(start, control, end):
    path = QPainterPath(QPointF(*start))
    path.quadTo(QPointF(*control), QPointF(*end))
    return path


def _heart(painter, x, y, size, opacity=1.):
    painter.save()
    painter.setOpacity(painter.opacity() * max(0., min(1., opacity)))
    painter.translate(x, y)
    painter.scale(size, size)
    heart = QPainterPath(QPointF(0, .85))
    heart.cubicTo(-1.3, -.05, -.9, -1.1, 0, -.45)
    heart.cubicTo(.9, -1.1, 1.3, -.05, 0, .85)
    heart.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor('#e8a29d'))
    painter.drawPath(heart)
    painter.restore()


def _star(painter, x, y, size, rotation):
    painter.save()
    painter.translate(x, y)
    painter.rotate(rotation)
    path = QPainterPath()
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = size if i % 2 == 0 else size * .47
        point = QPointF(math.cos(angle) * radius, math.sin(angle) * radius)
        if i:
            path.lineTo(point)
        else:
            path.moveTo(point)
    path.closeSubpath()
    painter.setPen(_pen('#c89a4b', .85))
    painter.setBrush(QColor('#f4d78b'))
    painter.drawPath(path)
    painter.restore()


def _fish(painter, paw, progress, phase):
    # Its head points toward the mouth; the tail stays in the raised paw.
    painter.save()
    painter.translate(paw.x() - 13, paw.y() - 17)
    painter.rotate(-12 + 3 * math.sin(phase * 9))
    fish = QPainterPath(QPointF(-20, 0))
    fish.cubicTo(-12, -12, 2, -11, 12, -3)
    fish.lineTo(23, -10)
    fish.quadTo(20, 0, 23, 10)
    fish.lineTo(12, 3)
    fish.cubicTo(2, 11, -12, 12, -20, 0)
    fish.closeSubpath()
    # Three actual bites remove the silhouette, rather than fading a whole fish.
    bite = 0 if progress < .40 else 1 if progress < .57 else 2 if progress < .73 else 3
    for center, radius in [(-22, 13), (-8, 13), (6, 13)][:bite]:
        hole = QPainterPath()
        hole.addEllipse(QRectF(center - radius, -radius, radius * 2, radius * 2))
        fish = fish.subtracted(hole)
    if progress > .84:
        painter.setOpacity(painter.opacity() * max(0., (1 - progress) / .16))
    painter.setPen(_pen('#ab7950', 1.25))
    painter.setBrush(QColor('#e3b77a'))
    painter.drawPath(fish)
    painter.save()
    painter.setClipPath(fish)
    painter.setPen(_pen('#f7deb0', 1.4))
    painter.drawPath(_curve((-12, -3), (1, -8), (9, -2)))
    painter.setPen(_pen('#b88555', .9))
    painter.drawPath(_curve((1, -5), (-3, 0), (1, 5)))
    painter.drawLine(QPointF(13, 0), QPointF(20, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor('#5a4c3d'))
    painter.drawEllipse(QRectF(-12, -3, 2.8, 2.8))
    painter.restore()
    painter.restore()


def _yarn(painter, target, phase):
    x, y = target
    painter.save()
    painter.translate(x, y)
    painter.setPen(_pen('#c48179', 1.6))
    painter.setBrush(Qt.NoBrush)
    thread = QPainterPath(QPointF(-8, 10))
    thread.cubicTo(-22, 22, -4, 33, -21, 35)
    thread.cubicTo(-37, 37, -34, 22, -44, 28)
    painter.drawPath(thread)
    painter.rotate(math.sin(phase * 5) * 18 + phase * 70)
    painter.setPen(_pen('#ac716b', 1.3))
    painter.setBrush(QColor('#dda096'))
    painter.drawEllipse(QRectF(-14, -14, 28, 28))
    circle = QPainterPath()
    circle.addEllipse(QRectF(-13, -13, 26, 26))
    painter.setClipPath(circle)
    painter.setPen(_pen('#f4c5b2', 1.6))
    painter.setBrush(Qt.NoBrush)
    for offset in (-10, -4, 2, 8):
        painter.drawPath(_curve((-18, offset + 8), (-2, offset - 10), (18, offset)))
    painter.setPen(_pen('#c58178', 1.2))
    for offset in (-6, 1, 8):
        painter.drawPath(_curve((offset - 5, -18), (offset + 13, -1), (offset - 1, 18)))
    painter.restore()


def draw_play(painter, state, now):
    """Draw scene-space props after the cat and before key bubbles.

    The model owns all action timing. No state or painter settings are retained.
    Imports stay local so the core renderer can call this function directly.
    """
    action = state.get('play_action')
    strength = max(0., min(1., state.get('play_strength', 0.)))
    if not action or strength <= .001:
        return
    from cat_renderer import body_transform, face_transform, paw_endpoint, _tail_path

    phase = state.get('play_phase', 0.)
    progress = max(0., min(1., state.get('play_progress', 0.)))
    body = body_transform(state)
    face = face_transform(state)

    def face_point(x, y):
        return body.map(face.map(QPointF(x, y)))

    painter.save()
    painter.setClipRect(QRectF(0, 0, CANVAS_W, CANVAS_H), Qt.IntersectClip)
    painter.setOpacity(painter.opacity() * strength)
    if action == 'feed':
        if state.get('play_holding', True):
            _fish(painter, paw_endpoint(state, 'right', body), progress, phase)
        if progress > .63:
            center = face_point(68, -11)
            lift = (progress - .63) / .37
            _heart(painter, center.x() + 17, center.y() - lift * 22, 6, min(1., lift * 4))
            _heart(painter, center.x() + 30, center.y() + 9 - lift * 17, 4, min(1., lift * 3))
    elif action == 'toy':
        target = state.get('play_target') or (385., 260.)
        _yarn(painter, target, phase)
        x, y = target
        painter.setBrush(Qt.NoBrush)
        painter.setPen(_pen('#b99582', 1.5))
        side = 1 if math.cos(phase * 5) > 0 else -1
        for offset in (19, 25):
            painter.drawPath(_curve((x + side * offset, y - 7),
                                    (x + side * (offset + 4), y),
                                    (x + side * offset, y + 7)))
    elif action == 'dizzy':
        center = face_point(0, -97)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(_pen('#d5c3a2', 1.))
        painter.drawArc(QRectF(center.x() - 40, center.y() - 9, 80, 18), 5 * 16, 170 * 16)
        for index in range(3):
            angle = phase * 4.8 + index * math.tau / 3
            _star(painter, center.x() + math.cos(angle) * 38,
                  center.y() + math.sin(angle) * 8, 5.5, math.degrees(angle) * .5)
    elif action in ('poke_head', 'poke_cheek'):
        side = -1 if state.get('play_side') == 'left' else 1
        center = face_point(side * 93, -30)
        if action == 'poke_cheek':
            _heart(painter, center.x() + side * 9, center.y() - progress * 17, 5)
        else:
            painter.setPen(_pen('#c7a979', 2.))
            for dy in (-9, 4):
                painter.drawLine(QPointF(center.x() + side * 3, center.y() + dy),
                                 QPointF(center.x() + side * 13, center.y() + dy * 1.5))
    elif action == 'poke_belly':
        painter.setBrush(Qt.NoBrush)
        painter.setPen(_pen('#c6a77c', 1.8))
        for side in (-1, 1):
            center = body.map(QPointF(268 + side * 82, 282))
            for offset in (0, 7):
                painter.drawPath(_curve((center.x() + side * offset, center.y() - 8),
                                        (center.x() + side * (offset + 5), center.y()),
                                        (center.x() + side * offset, center.y() + 8)))
    elif action == 'poke_paw':
        side = state.get('play_side') or 'right'
        center = paw_endpoint(state, side, body)
        painter.setPen(_pen('#c6a77c', 1.7))
        for dx in (-23, 23):
            sign = 1 if dx > 0 else -1
            painter.drawLine(QPointF(center.x() + dx, center.y() - 6),
                             QPointF(center.x() + dx + sign * 6, center.y() - 12))
    elif action == 'poke_tail':
        tip = body.map(_tail_path(state, now).pointAtPercent(1.))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(_pen('#c6a77c', 1.7))
        for offset in (14, 21):
            painter.drawPath(_curve((tip.x() - 7, tip.y() - offset),
                                    (tip.x(), tip.y() - offset - 5),
                                    (tip.x() + 7, tip.y() - offset)))
    painter.restore()
