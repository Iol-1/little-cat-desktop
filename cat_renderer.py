"""Articulated kitten coats, closed paw silhouettes and visible-part hit tests."""
import math
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient,
                         QPainter, QPainterPath, QPainterPathStroker, QPen,
                         QPixmap, QTransform)
from scene_layout import CANVAS_W, CANVAS_H, FACE_CENTER, SHOULDERS, PAW_REST, MOUSE_HOME
from keyboard_art import KEYS, key_target, resolve_vk, draw_keyboard
from skins import SKINS


def _path(points):
    path = QPainterPath()
    for op in points:
        if op[0] == 'M': path.moveTo(*op[1:])
        elif op[0] == 'L': path.lineTo(*op[1:])
        elif op[0] == 'C': path.cubicTo(*op[1:])
        elif op[0] == 'Q': path.quadTo(*op[1:])
        elif op[0] == 'Z': path.closeSubpath()
    return path


def _pen(color, width=1):
    return QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _color(color, alpha):
    result = QColor(color)
    result.setAlpha(alpha)
    return result


def _ellipse(p, color, x, y, w, h):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(x, y, w, h))


def _clamp(value, lo=-1., hi=1.):
    return max(lo, min(hi, value))


def _skin(state):
    return SKINS.get(state.get('skin', 'black'), SKINS['black'])


def body_transform(state):
    """Map the seated skeleton around the hips; planted key/mouse paws stay put."""
    lean = _clamp(state.get('body_lean', 0.))
    twist = _clamp(state.get('body_twist', 0.))
    sleep = _clamp(state.get('sleep', 0.), 0., 1.)
    breath = state.get('breathing', 0.) * (1.6 + sleep * 2.)
    transform = QTransform()
    transform.translate(268 + lean * 9, 349 + state.get('body_bob', 0.) - breath)
    transform.rotate(lean * 6.)
    transform.shear(-twist * .035, 0.)
    transform.translate(-268, -349)
    return transform


def face_transform(state):
    """Map local face coordinates into the body's resting coordinate space."""
    hx = _clamp(state.get('head_x', 0.))
    hy = _clamp(state.get('head_y', 0.))
    sleep = _clamp(state.get('sleep', 0.), 0., 1.)
    chin_lift = (state.get('touch_strength', 0.) * 3
                 if state.get('touch_region') == 'neck' else 0.)
    if state.get('play_action') == 'poke_neck':
        chin_lift = state.get('play_strength', 0.) * 3
    transform = QTransform()
    transform.translate(FACE_CENTER[0] + hx * 6,
                        FACE_CENTER[1] + hy * 4 + sleep * 7
                        - state.get('breathing', 0.) * 1.4 - chin_lift)
    transform.rotate(hx * 4.5)
    return transform


def paw_endpoint(state, side, transform=None):
    """Scene paw point, blending out of contact without a coordinate-space pop."""
    endpoint = QPointF(*state.get(side + '_paw', PAW_REST[side]))
    local = (transform or body_transform(state)).map(endpoint)
    weight = _clamp(state.get(side + '_contact_weight',
                             float(state.get(side + '_contact', False))), 0., 1.)
    return QPointF(local.x() * (1 - weight) + endpoint.x() * weight,
                   local.y() * (1 - weight) + endpoint.y() * weight)


def _body_path():
    return _path([('M', 222, 219),
                  ('C', 242, 209, 288, 209, 309, 220),
                  ('C', 325, 234, 332, 254, 336, 278),
                  ('C', 347, 301, 353, 332, 341, 350),
                  ('C', 329, 367, 299, 368, 270, 367),
                  ('C', 240, 369, 209, 366, 195, 351),
                  ('C', 183, 336, 189, 306, 197, 282),
                  ('C', 200, 258, 207, 233, 222, 219), ('Z',)])


def _rear_paw_paths():
    # Include the outer toes and a closed inner haunch, not just an open seam.
    return (
        _path([('M', 218, 306), ('C', 200, 313, 191, 331, 197, 346),
               ('C', 190, 354, 194, 363, 204, 365),
               ('C', 218, 368, 230, 365, 231, 357),
               ('C', 235, 341, 232, 320, 218, 306), ('Z',)]),
        _path([('M', 319, 305), ('C', 337, 313, 346, 331, 340, 346),
               ('C', 347, 354, 342, 363, 333, 365),
               ('C', 320, 368, 307, 365, 306, 357),
               ('C', 302, 340, 305, 319, 319, 305), ('Z',)]),
    )


def _ear_motion(state):
    if state.get('touch_region') not in ('head', 'cheek', 'neck'):
        return 0.
    return state.get('touch_strength', 0.) * math.sin(state.get('touch_phase', 0.) * 7.) * 2.8


def _face_path(state):
    ear = _ear_motion(state)
    return _path([('M', -77, -28),
                  ('C', -79, -43, -77 - ear, -72, -70 - ear, -84 + abs(ear)),
                  ('C', -65 - ear, -92 + abs(ear), -52, -77, -38, -60),
                  ('C', -15, -66, 15, -66, 38, -60),
                  ('C', 52, -77, 65 - ear, -92 + abs(ear), 70 - ear, -84 + abs(ear)),
                  ('C', 77 - ear, -72, 79, -43, 77, -28),
                  ('C', 90, -13, 97, 8, 91, 30),
                  ('C', 87, 54, 68, 70, 44, 77),
                  ('C', 18, 86, -18, 86, -44, 77),
                  ('C', -68, 70, -87, 54, -91, 30),
                  ('C', -97, 8, -90, -13, -77, -28), ('Z',)])


def _tail_path(state, now):
    sleep = _clamp(state.get('sleep', 0.), 0., 1.)
    touch = state.get('touch_strength', 0.) if state.get('touch_region') == 'tail' else 0.
    wave = math.sin(now * 1.65) * (3.4 - sleep * 2.6)
    wave += math.sin(state.get('touch_phase', 0.) * 9) * touch * 8
    lift = touch * 12
    return _path([('M', 339, 332),
                  ('C', 363, 344, 382, 337 + wave - lift * .3, 391, 318 + wave - lift),
                  ('C', 400, 301 + wave - lift, 411, 292 + wave - lift,
                   424, 298 + wave - lift)])


def _stroke_shape(path, width):
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return stroker.createStroke(path)


def _patch(p, color, x, y, width, height, rotation=0):
    """A soft, irregular coat patch. Callers clip it to the moving silhouette."""
    p.save()
    p.translate(x, y)
    p.rotate(rotation)
    p.scale(width, height)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(_path([('M', -.45, -.1), ('C', -.6, -.38, -.23, -.55, -.05, -.4),
                      ('C', .12, -.55, .53, -.35, .43, -.13),
                      ('C', .61, .09, .33, .49, .13, .39),
                      ('C', -.1, .58, -.48, .31, -.39, .1),
                      ('Q', -.52, .03, -.45, -.1), ('Z',)]))
    p.restore()


def _bands(p, path, color, positions, width=7):
    """Stripe bands follow the limb/tail centre line as it bends."""
    p.setPen(_pen(color, width))
    p.setBrush(Qt.NoBrush)
    for t in positions:
        point = path.pointAtPercent(t)
        before = path.pointAtPercent(max(0, t - .015))
        after = path.pointAtPercent(min(1, t + .015))
        dx, dy = after.x() - before.x(), after.y() - before.y()
        length = max(.001, math.hypot(dx, dy))
        nx, ny = -dy / length * 25, dx / length * 25
        p.drawLine(QPointF(point.x() - nx, point.y() - ny),
                   QPointF(point.x() + nx, point.y() + ny))


def _extra_body(p, palette):
    pattern = palette.get('pattern')
    if pattern == 'tabby':
        _ellipse(p, palette['bib'], 237, 235, 61, 115)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(palette['stripe'], 8))
        for y in (257, 281, 306, 330):
            p.drawPath(_path([('M', 184, y - 8), ('Q', 216, y - 3, 228, y + 7)]))
            p.drawPath(_path([('M', 348, y - 7), ('Q', 320, y - 1, 308, y + 9)]))
    elif pattern == 'tuxedo':
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(palette['white']))
        p.drawPath(_path([('M', 230, 220), ('Q', 264, 238, 307, 219),
                          ('Q', 293, 262, 283, 291), ('Q', 267, 310, 250, 290),
                          ('Q', 236, 257, 230, 220), ('Z',)]))
    elif pattern == 'cow':
        _patch(p, palette['patch'], 212, 256, 77, 74, -25)
        _patch(p, palette['patch'], 326, 315, 78, 93, 15)
        _patch(p, palette['patch'], 256, 353, 35, 26, -20)
    elif pattern == 'tortie':
        for x, y, width, height, rot in ((218, 246, 43, 53, -20),
                (305, 259, 51, 38, 17), (247, 290, 35, 48, 40),
                (319, 331, 55, 45, -20), (205, 335, 30, 35, 10)):
            _patch(p, palette['orange'], x, y, width, height, rot)
        _patch(p, palette['orange_light'], 264, 351, 31, 25)


def _extra_foot(p, palette, index):
    pattern = palette.get('pattern')
    x = 213 if index == 0 else 324
    if pattern == 'tabby':
        p.setPen(_pen(palette['stripe'], 6))
        p.drawLine(QPointF(x - 24, 329), QPointF(x + 24, 335))
        p.drawLine(QPointF(x - 24, 344), QPointF(x + 24, 349))
    elif pattern == 'tuxedo':
        _ellipse(p, palette['arm'], x - 29, 293, 58, 56)
    elif pattern == 'cow' and index == 1:
        _patch(p, palette['patch'], x + 5, 326, 45, 46, 25)
    elif pattern == 'tortie':
        _patch(p, palette['orange'], x - 3, 345 if index == 0 else 323, 37, 38, -22)


def _extra_arm(p, palette, centre, side, x, y):
    pattern = palette.get('pattern')
    if pattern == 'tabby':
        _bands(p, centre, palette['stripe'], (.34, .60, .80), 7)
    elif pattern in ('tuxedo', 'siamese'):
        middle = centre.pointAtPercent(.84 if pattern == 'tuxedo' else .73)
        p.setPen(_pen(palette['white'] if pattern == 'tuxedo' else palette['point'], 38))
        p.drawLine(middle, QPointF(x, y + 7))
    elif pattern == 'cow':
        middle = centre.pointAtPercent(.46 if side == 'left' else .77)
        _patch(p, palette['patch'], middle.x(), middle.y(), 45, 45, 20)
    elif pattern == 'tortie':
        for t, width in ((.33, 31), (.73, 39)):
            middle = centre.pointAtPercent(t)
            _patch(p, palette['orange'], middle.x(), middle.y(), width, 34,
                   20 if side == 'left' else -25)


def _extra_face(p, palette):
    pattern = palette.get('pattern')
    if pattern == 'tabby':
        _ellipse(p, palette['bib'], -48, 27, 96, 68)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(palette['stripe']))
        # Short forehead stripes leave the eye line free, preserving the vacant expression.
        for x, direction in ((-26, 1), (0, 0), (26, -1)):
            p.drawPath(_path([('M', x - 5, -73), ('Q', x - 6, -44, x + direction * 6, -25),
                              ('Q', x + 8, -43, x + 6, -73), ('Z',)]))
        p.setPen(_pen(palette['stripe'], 5))
        for sign in (-1, 1):
            for y in (18, 32):
                p.drawPath(_path([('M', sign * 96, y - 7),
                                  ('Q', sign * 84, y - 1, sign * 73, y + 3)]))
    elif pattern == 'tuxedo':
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(palette['white']))
        p.drawPath(_path([('M', 0, 10), ('C', -10, 27, -29, 47, -65, 62),
                          ('Q', 0, 105, 65, 62), ('C', 29, 47, 10, 27, 0, 10), ('Z',)]))
    elif pattern == 'cow':
        _patch(p, palette['patch'], -61, -44, 89, 129, -15)
        _patch(p, palette['patch'], 83, 35, 50, 60, 22)
    elif pattern == 'siamese':
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(palette['point']))
        for sign in (-1, 1):
            p.drawPath(_path([('M', sign * 37, -59), ('L', sign * 72, -102),
                              ('L', sign * 91, -22), ('Q', sign * 65, -42, sign * 37, -59), ('Z',)]))
        mask = QLinearGradient(0, -40, 0, 65)
        mask.setColorAt(0, QColor(palette['point']))
        mask.setColorAt(1, QColor(palette['point_light']))
        p.setBrush(mask)
        p.drawPath(_path([('M', -70, -28), ('Q', -43, -49, 0, -41),
                          ('Q', 43, -49, 70, -28), ('Q', 89, -1, 73, 41),
                          ('Q', 55, 76, 0, 71), ('Q', -55, 76, -73, 41),
                          ('Q', -89, -1, -70, -28), ('Z',)]))
    elif pattern == 'tortie':
        for color, x, y, width, height, rot in (
                ('orange', -59, -52, 58, 97, -18), ('orange', 24, -42, 48, 59, 25),
                ('orange_light', -77, 26, 41, 41, 5), ('orange', 59, 43, 65, 58, 28),
                ('orange_light', -13, 68, 37, 26, -15)):
            _patch(p, palette[color], x, y, width, height, rot)


def _mouse(p, position, down=False):
    x, y = position
    p.save()
    p.translate(x, y)
    p.rotate(14)
    _ellipse(p, QColor(0, 0, 0, 27), -15, -12, 31, 36)
    gradient = QLinearGradient(-13, -19, 12, 17)
    gradient.setColorAt(0, QColor('#eceeea'))
    gradient.setColorAt(.5, QColor('#c9cfcb'))
    gradient.setColorAt(1, QColor('#9fa8a5'))
    p.setPen(_pen('#7d8884', .85))
    p.setBrush(gradient)
    p.drawEllipse(QRectF(-14, -20 + (1.8 if down else 0), 28, 37))
    p.setPen(_pen('#7c8882', .8))
    p.drawLine(QPointF(0, -17), QPointF(0, -5))
    _ellipse(p, '#b6e8a0' if down else '#68766f', -1.5, -13, 3, 6)
    p.restore()


def _tail(p, state, now):
    palette = _skin(state)
    tail = _tail_path(state, now)
    shape = _stroke_shape(tail, 17)
    p.setPen(_pen(palette['edge'], .8))
    p.setBrush(QColor(palette['tail']))
    p.drawPath(shape)
    if state.get('skin') == 'calico':
        p.save()
        p.setClipPath(shape)
        _ellipse(p, palette['orange'], 367, 301, 39, 62)
        tip = tail.pointAtPercent(1.)
        _ellipse(p, palette['paw'], tip.x() - 12, tip.y() - 12, 25, 25)
        p.restore()
    p.save()
    p.setClipPath(shape)
    pattern = palette.get('pattern')
    if pattern == 'tabby':
        _bands(p, tail, palette['stripe'], (.20, .42, .64, .83, .97), 7)
    elif pattern == 'cow':
        tip = tail.pointAtPercent(.96)
        _ellipse(p, palette['paw'], tip.x() - 12, tip.y() - 12, 25, 25)
    elif pattern == 'tortie':
        for t in (.28, .71):
            point = tail.pointAtPercent(t)
            _patch(p, palette['orange'], point.x(), point.y(), 28, 31)
    p.restore()
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(_color(palette['seam'], 85), 1.2))
    p.drawPath(tail)


def _coat_body(p, body, state):
    palette = _skin(state)
    p.save()
    p.setClipPath(body)
    p.setPen(Qt.NoPen)
    if state.get('skin') == 'calico':
        p.setBrush(QColor(palette['orange']))
        p.drawPath(_path([('M', 196, 211), ('C', 222, 213, 244, 227, 231, 249),
                          ('C', 219, 264, 231, 279, 215, 297),
                          ('C', 196, 313, 179, 287, 185, 265), ('Z',)]))
        p.setBrush(QColor(palette['patch']))
        p.drawPath(_path([('M', 325, 251), ('C', 299, 255, 311, 282, 294, 302),
                          ('C', 278, 325, 305, 353, 338, 359),
                          ('L', 369, 337), ('L', 348, 261), ('Z',)]))
        p.setBrush(QColor(palette['orange_light']))
        p.drawPath(_path([('M', 245, 338), ('C', 239, 346, 243, 365, 257, 370),
                          ('L', 278, 376), ('Q', 280, 348, 264, 341),
                          ('Q', 252, 330, 245, 338), ('Z',)]))
    elif state.get('skin') == 'ragdoll':
        p.setBrush(QColor(palette['point_light']))
        p.drawPath(_path([('M', 317, 249), ('C', 298, 280, 316, 330, 332, 356),
                          ('L', 358, 367), ('L', 359, 263), ('Z',)]))
        p.setBrush(QColor(palette['white']))
        p.drawPath(_path([('M', 233, 226), ('Q', 265, 248, 302, 225),
                          ('Q', 288, 249, 285, 278),
                          ('Q', 267, 301, 246, 280), ('Q', 243, 248, 233, 226), ('Z',)]))
    _extra_body(p, palette)
    p.restore()


def _body(p, state):
    palette = _skin(state)
    body = _body_path()
    gradient = QLinearGradient(199, 228, 342, 363)
    gradient.setColorAt(0, QColor(palette['body']))
    gradient.setColorAt(1, QColor(palette['body_shadow']))
    p.setPen(_pen(palette['edge'], .9))
    p.setBrush(gradient)
    p.drawPath(body)
    _coat_body(p, body, state)
    for index, paw in enumerate(_rear_paw_paths()):
        # Fill and contour share the exact same closed silhouette, including toes.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(palette['paw']))
        p.drawPath(paw)
        p.save()
        p.setClipPath(paw)
        if state.get('skin') == 'calico':
            _ellipse(p, palette['orange'] if index == 0 else palette['patch'],
                     183 if index == 0 else 306, 298, 49, 54)
        elif state.get('skin') == 'ragdoll':
            _ellipse(p, palette['point_light'], 185 if index == 0 else 304, 298, 46, 57)
        _extra_foot(p, palette, index)
        p.restore()
        p.setPen(_pen(_color(palette['seam'], 175), 1.75))
        p.setBrush(Qt.NoBrush)
        p.drawPath(paw)
    p.setPen(_pen(_color(palette['seam'], 175), 1.3))
    for x in (205, 212, 325, 332):
        p.drawPath(_path([('M', x, 358), ('Q', x - 1, 361, x, 363)]))


def _arm_geometry(side, shoulder, endpoint):
    sx, sy = shoulder.x(), shoulder.y()
    x, y = endpoint.x(), endpoint.y()
    dx, dy = x - sx, y - sy
    length = max(1., math.hypot(dx, dy))
    outward = -1 if side == 'left' else 1
    # The upper arm moves with the shoulder; the elbow opens to reach its target.
    bend = 20 + max(0., 1. - length / 170.) * 12
    cp1 = (sx + outward * bend + dx * .16, sy + dy * .40)
    cp2 = (x - dx * .24 + outward * 7, y - dy * .18 - 9)
    centre = _path([('M', sx, sy), ('C', *cp1, *cp2, x, y)])
    upper, lower = [], []
    for index in range(25):
        t = index / 24
        inv = 1 - t
        cx = inv**3 * sx + 3 * inv**2 * t * cp1[0] + 3 * inv * t**2 * cp2[0] + t**3 * x
        cy = inv**3 * sy + 3 * inv**2 * t * cp1[1] + 3 * inv * t**2 * cp2[1] + t**3 * y
        tx = 3 * inv**2 * (cp1[0] - sx) + 6 * inv * t * (cp2[0] - cp1[0]) + 3 * t**2 * (x - cp2[0])
        ty = 3 * inv**2 * (cp1[1] - sy) + 6 * inv * t * (cp2[1] - cp1[1]) + 3 * t**2 * (y - cp2[1])
        tangent = max(1., math.hypot(tx, ty))
        nx, ny = -ty / tangent, tx / tangent
        radius = 12 + 4.5 * math.sin(min(t / .25, 1) * math.pi / 2) - 2.5 * t
        upper.append((cx + nx * radius, cy + ny * radius))
        lower.append((cx - nx * radius, cy - ny * radius))
    shape = QPainterPath(QPointF(*upper[0]))
    for point in upper[1:]:
        shape.lineTo(*point)
    shape.quadTo(x + dx / length * 16, y + dy / length * 16, *lower[-1])
    for point in reversed(lower[:-1]):
        shape.lineTo(*point)
    shape.quadTo(sx - dx / length * 12, sy - dy / length * 12, *upper[0])
    shape.closeSubpath()
    paw = QPainterPath()
    paw.addEllipse(QRectF(x - 17, y - 13.8, 34, 28))
    return shape.united(paw), centre


def _arm_shape(side, shoulder, endpoint):
    return _arm_geometry(side, shoulder, endpoint)[0]


def _arm(p, side, endpoint, shoulder, state, alpha=1., ghost=False):
    if alpha <= .001:
        return
    palette = _skin(state)
    shape, centre = _arm_geometry(side, shoulder, endpoint)
    sx, sy, x, y = shoulder.x(), shoulder.y(), endpoint.x(), endpoint.y()
    p.save()
    p.setOpacity(max(0., min(1., alpha)))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(palette['arm']))
    p.drawPath(shape)
    p.save()
    p.setClipPath(shape)
    if state.get('skin') == 'calico':
        middle = centre.pointAtPercent(.30 if side == 'left' else .60)
        _ellipse(p, palette['orange'] if side == 'left' else palette['patch'],
                 middle.x() - 26, middle.y() - 27, 51, 54)
        if side == 'right':
            _ellipse(p, palette['orange_light'], x - 23, y - 25, 24, 23)
    elif state.get('skin') == 'ragdoll':
        middle = centre.pointAtPercent(.77)
        p.setPen(_pen(palette['point_light'], 34))
        p.drawLine(middle, QPointF(x, y + 3))
        _ellipse(p, palette['white'], x - 20, y + 1, 40, 23)
    _extra_arm(p, palette, centre, side, x, y)
    p.restore()
    # Outline the same filled path: no unmatched curve below the paw.
    gradient = QLinearGradient(sx, sy, x, y)
    for stop, opacity in ((0., 0), (.17, 145), (.45, 185), (1., 220)):
        gradient.setColorAt(stop, _color(palette['seam'], opacity))
    p.setPen(QPen(QBrush(gradient), 4. if ghost else 1.85,
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(shape)
    if not ghost:
        p.setPen(_pen(_color(palette['seam'], 175), 1.3))
        for offset in (-5, 4):
            p.drawPath(_path([('M', x + offset, y + 7),
                              ('Q', x + offset - 1, y + 10, x + offset, y + 12)]))
    p.restore()


def _coat_face(p, face, state):
    palette = _skin(state)
    p.save()
    p.setClipPath(face)
    p.setPen(Qt.NoPen)
    if state.get('skin') == 'calico':
        p.setBrush(QColor(palette['orange']))
        p.drawPath(_path([('M', -103, -103), ('L', -18, -103),
                          ('C', -11, -67, -35, -52, -23, -28),
                          ('C', -14, -12, -25, 15, -47, 26),
                          ('C', -64, 35, -86, 17, -103, 29), ('Z',)]))
        p.setBrush(QColor(palette['patch']))
        p.drawPath(_path([('M', 39, -100), ('L', 106, -100), ('L', 105, 40),
                          ('C', 81, 52, 61, 42, 42, 25),
                          ('C', 27, 12, 12, 8, 19, -12),
                          ('C', 29, -31, 28, -45, 42, -57), ('Z',)]))
        p.setBrush(QColor(palette['orange_light']))
        p.drawPath(_path([('M', -62, 51), ('Q', -47, 46, -41, 57),
                          ('Q', -34, 68, -49, 79), ('L', -73, 73), ('Z',)]))
    elif state.get('skin') == 'ragdoll':
        mask = QLinearGradient(0, -73, 0, 63)
        mask.setColorAt(0., QColor(palette['point']))
        mask.setColorAt(1., QColor(palette['point_light']))
        p.setBrush(mask)
        p.drawPath(_path([('M', -105, -110), ('L', 105, -110), ('L', 102, 48),
                          ('C', 75, 74, 50, 71, 23, 51),
                          ('Q', 0, 39, -23, 51),
                          ('C', -50, 71, -75, 74, -102, 48), ('Z',)]))
        # A white inverted-V blaze is a coat marking, not an oversized muzzle.
        p.setBrush(QColor(palette['white']))
        p.drawPath(_path([('M', 0, -35), ('C', -9, -10, -18, 11, -30, 26),
                          ('C', -40, 39, -49, 51, -63, 64),
                          ('Q', 0, 103, 63, 64),
                          ('C', 49, 51, 40, 39, 30, 26),
                          ('C', 18, 11, 9, -10, 0, -35), ('Z',)]))
    _extra_face(p, palette)
    p.restore()


def _face(p, state, now):
    palette = _skin(state)
    gx, gy = _clamp(state.get('gaze_x', 0)), _clamp(state.get('gaze_y', 0))
    hx = _clamp(state.get('head_x', 0))
    sleep = _clamp(state.get('sleep', 0), 0., 1.)
    blink = max(sleep, _clamp(state.get('blink', 0), 0., 1.))
    mouth = _clamp(state.get('play_mouth', 0), 0., 1.)
    expression = state.get('play_face')
    if (not state.get('play_action') and state.get('touch_region') == 'neck'
            and state.get('touch_strength', 0.) > .6):
        expression = 'happy'
    p.save()
    p.setTransform(face_transform(state), True)
    # Keep the v3 round kitten face and wide, slightly vacant eyes.
    face = _face_path(state)
    gradient = QLinearGradient(-65, -78, 64, 75)
    gradient.setColorAt(0, QColor(palette['face']))
    gradient.setColorAt(1, QColor(palette['face_shadow']))
    p.setPen(_pen(palette['edge'], .95))
    p.setBrush(gradient)
    p.drawPath(face)
    _coat_face(p, face, state)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(palette['ear']))
    ear = _ear_motion(state)
    p.drawPath(_path([('M', -67 - ear, -74 + abs(ear)),
                      ('Q', -72 - ear, -58, -68, -46), ('L', -49, -56), ('Z',)]))
    p.drawPath(_path([('M', 67 - ear, -74 + abs(ear)), ('L', 49, -56),
                      ('L', 68, -46), ('Q', 72 - ear, -58, 67 - ear, -74 + abs(ear)), ('Z',)]))
    openness = max(0., 1 - blink)
    for index, eye_x in enumerate((-40, 40)):
        eye_y = 6 + index * .6 + (eye_x / 40) * hx * .35
        if openness < .08:
            closed_color = palette['eye'] if state.get('skin', 'black') == 'black' else palette['pupil']
            p.setPen(_pen(closed_color, 2.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(_path([('M', eye_x - 18, eye_y + 4),
                              ('Q', eye_x, eye_y + 10, eye_x + 18, eye_y + 4)]))
            continue
        height = (44 + (3 * mouth if expression == 'surprised' else 0)) * openness
        eye = QPainterPath()
        eye.addEllipse(QRectF(eye_x - 24, eye_y - height / 2, 48, height))
        iris = QLinearGradient(eye_x, eye_y - 22, eye_x, eye_y + 22)
        iris.setColorAt(0, QColor(palette.get('eye_right', palette['eye']) if index else palette['eye']))
        iris.setColorAt(1, QColor(palette.get('eye_right_light', palette['eye_light']) if index else palette['eye_light']))
        p.setPen(Qt.NoPen)
        p.setBrush(iris)
        p.drawPath(eye)
        p.save()
        p.setClipPath(eye)
        pupil_x = eye_x + gx * 11 + (-1.1 if index == 0 else 1.1)
        pupil_y = eye_y + gy * 7 * openness + (0 if index == 0 else .5)
        _ellipse(p, palette['pupil'], pupil_x - 8, pupil_y - 12 * openness, 16, 24 * openness)
        _ellipse(p, QColor(242, 250, 235, 150), pupil_x - 3.5,
                 pupil_y - 6.5 * openness, 2., 2. * openness)
        p.restore()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(palette['nose']))
    p.drawPath(_path([('M', -3, 35), ('Q', 0, 33, 3, 35), ('Q', 0, 39, -3, 35), ('Z',)]))
    if mouth > .06:
        _ellipse(p, palette['mouth'], -2 - mouth * 3, 43, 4 + mouth * 6, 4 + mouth * 8)
        if expression == 'happy':
            _ellipse(p, palette['nose'], -mouth * 2.5, 47 + mouth * 2, mouth * 5, mouth * 3)
    elif expression == 'happy':
        p.setPen(_pen(palette['mouth'], 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(_path([('M', -4, 43), ('Q', 0, 48, 4, 43)]))
    else:
        _ellipse(p, palette['mouth'], -1.5, 43, 3., 4.)
    p.setPen(_pen(_color(palette['whisker'], 169), 1.25))
    for sign in (-1, 1):
        for offset, slope in [(0, -2), (9, 2)]:
            p.drawPath(_path([('M', sign * 58, 40 + offset),
                              ('Q', sign * 68, 40 + offset + slope,
                               sign * 79, 40 + offset + slope * 1.5)]))
    p.restore()


def hit_test(point, state, now=0):
    """Return the visible touched part in scene coordinates, or None on gaps."""
    if not isinstance(point, QPointF):
        point = QPointF(*point)
    transform = body_transform(state)
    inverse, valid = transform.inverted()
    if not valid:
        return None
    local = inverse.map(point)
    for side in ('left', 'right'):
        shoulder = transform.map(QPointF(*SHOULDERS[side]))
        if _arm_shape(side, shoulder, paw_endpoint(state, side, transform)).contains(point):
            return 'paw'
    if any(paw.contains(local) for paw in _rear_paw_paths()):
        return 'paw'
    body = _body_path()
    if not body.contains(local) and _stroke_shape(_tail_path(state, now), 17).contains(local):
        return 'tail'
    face_inverse, valid = face_transform(state).inverted()
    if valid:
        face_point = face_inverse.map(local)
        if _face_path(state).contains(face_point):
            return 'cheek' if face_point.y() > 22 and abs(face_point.x()) > 22 else 'head'
    if body.contains(local):
        # Only the exposed patch beneath the chin is scratchable. Face and
        # foreground paws have already won their visible-part hit tests above.
        if ((local.x() - 265) / 32) ** 2 + ((local.y() - 249) / 17) ** 2 <= 1:
            return 'neck'
        return 'belly'
    return None


def _bubbles(p, bubbles):
    p.save()
    font = QFont('Segoe UI')
    font.setPixelSize(13)
    font.setWeight(QFont.DemiBold)
    p.setFont(font)
    for bubble in bubbles:
        alpha = max(0., min(1., bubble.get('alpha', 1)))
        label = str(bubble.get('label', ''))
        if not label or alpha <= .01:
            continue
        x, y = bubble['x'], bubble['y']
        width = max(23., min(66., len(label) * 7.5 + 12))
        rect = QRectF(x - width / 2, y - 10, width, 21)
        p.setOpacity(alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 30))
        p.drawRoundedRect(rect.translated(0, 2), 6, 6)
        p.setBrush(QColor('#f3f4ec'))
        p.setPen(_pen(QColor(180, 188, 175, 160), .8))
        p.drawRoundedRect(rect, 5.5, 5.5)
        p.setPen(QColor('#40473e'))
        p.drawText(rect, Qt.AlignCenter, label)
    p.restore()


def draw_pet(painter, state, now):
    """Draw a frame into an already scaled, transparent painter."""
    p = painter
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    sleep = state.get('sleep', 0)
    transform = body_transform(state)
    _ellipse(p, QColor(0, 0, 0, 24), 190, 351, 164, 23)
    p.save()
    p.setTransform(transform, True)
    _tail(p, state, now)
    _body(p, state)
    p.restore()
    draw_keyboard(p, state)
    _mouse(p, state.get('mouse', MOUSE_HOME), state.get('mouse_down', False))
    shoulders = {side: transform.map(QPointF(*SHOULDERS[side])) for side in SHOULDERS}
    for ghost in state.get('ghosts', ()):
        _arm(p, ghost['side'], QPointF(ghost['x'], ghost['y']), shoulders[ghost['side']],
             state, min(.34, ghost.get('alpha', .2)), ghost=True)
    for side in ('left', 'right'):
        _arm(p, side, paw_endpoint(state, side, transform), shoulders[side], state)
    p.save()
    p.setTransform(transform, True)
    _face(p, state, now)
    p.restore()
    # Snacks are held in front of the muzzle, so show the raised food paw
    # over the lower face instead of hiding it like a keyboard reach.
    if state.get('play_action') == 'feed' and state.get('play_holding', False):
        _arm(p, 'right', paw_endpoint(state, 'right', transform), shoulders['right'], state)
    # Props reuse the public body/face transforms; keep this import after the
    # renderer module is initialized to avoid a module-level dependency cycle.
    from play_art import draw_play
    draw_play(p, state, now)
    _bubbles(p, state.get('bubbles', ()))
    if sleep > .85:
        p.save()
        p.setOpacity((sleep - .85) / .15 * .65)
        p.setPen(QColor(_skin(state)['eye']))
        font = QFont('Segoe UI')
        font.setPixelSize(15)
        p.setFont(font)
        phase = (now * .4) % 1
        p.drawText(QPointF(384 + phase * 12, 116 - phase * 28), 'z')
        p.setOpacity((sleep - .85) / .15 * .40)
        font.setPixelSize(11)
        p.setFont(font)
        p.drawText(QPointF(403, 83), 'z')
        p.restore()
    p.restore()


def make_icon(skin='black'):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.translate(32, 34)
    painter.scale(.278, .278)
    painter.translate(-FACE_CENTER[0], -FACE_CENTER[1])
    _face(painter, {'gaze_x': 0, 'gaze_y': 0, 'skin': skin}, 0)
    painter.end()
    return QIcon(pixmap)
