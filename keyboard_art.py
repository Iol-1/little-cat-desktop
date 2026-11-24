"""Small sculpted mechanical keyboard based on the supplied grey keycap photos.

The same projected cap centres drive rendering and paw contact.  Dimensions
are scene units, independent of the desktop widget's scale.
"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

NUMPAD_ENTER = 0x10D


def _project(u, v):
    return 168.0 + u * 13.8 + v * 1.6, 383.0 + v * 11.15 + u * .23


KEYS = []


def _add(vk, label, u, v, units=1.0, rows=1.0):
    rise = 4.7 - min(v, 5) * .10
    x, y = _project(u + units / 2, v + (rows - .12) / 2)
    KEYS.append({'vk': vk, 'label': label, 'x': x, 'y': y - rise,
                 'w': units * 13.8 - 3.1, 'h': rows * 11.15 - 3.0,
                 'u': u, 'v': v, 'units': units, 'rows': rows, 'rise': rise})


def _row(v, items):
    u = 0.0
    for vk, label, units in items:
        if vk is not None:
            _add(vk, label, u, v, units)
        u += units


_row(0, [(27, 'Esc', 1), (None, '', .65)]
     + [(112 + i, 'F' + str(i + 1), 1) for i in range(4)]
     + [(None, '', .45)]
     + [(116 + i, 'F' + str(i + 5), 1) for i in range(4)]
     + [(None, '', .45)]
     + [(120 + i, 'F' + str(i + 9), 1) for i in range(4)]
     + [(None, '', .85), (46, 'Del', 1), (45, 'Ins', 1), (33, 'PgUp', 1), (34, 'PgDn', 1)])
_row(1, [(192, '`', 1)] + [(49 + i, str(i + 1), 1) for i in range(9)]
     + [(48, '0', 1), (189, '-', 1), (187, '=', 1), (8, 'Back', 2)])
_row(2, [(9, 'Tab', 1.5)] + [(ord(k), k, 1) for k in 'QWERTYUIOP']
     + [(219, '[', 1), (221, ']', 1), (220, '\\', 1.5)])
_row(3, [(20, 'Caps', 1.75)] + [(ord(k), k, 1) for k in 'ASDFGHJKL']
     + [(186, ';', 1), (222, "'", 1), (13, 'Enter', 2.25)])
_row(4, [(160, 'Shift', 2.25)] + [(ord(k), k, 1) for k in 'ZXCVBNM']
     + [(188, ',', 1), (190, '.', 1), (191, '/', 1), (161, 'Shift', 1.75), (38, '↑', 1)])
_row(5, [(162, 'Ctrl', 1.25), (91, 'Win', 1.25), (164, 'Alt', 1.25),
         (32, 'Space', 5.25), (0, 'Fn', 1), (165, 'Alt', 1), (163, 'Ctrl', 1),
         (37, '←', 1), (40, '↓', 1), (39, '→', 1)])

# A real, separate four-column number pad, including tall + and Enter caps.
for vk, label, column in [(144, 'Num', 0), (111, '/', 1), (106, '*', 2), (109, '-', 3)]:
    _add(vk, label, 15.4 + column, 1)
for v, numbers in [(2, '789'), (3, '456'), (4, '123')]:
    for column, digit in enumerate(numbers):
        _add(96 + int(digit), digit, 15.4 + column, v)
_add(107, '+', 18.4, 2, rows=2)
_add(NUMPAD_ENTER, 'Enter', 18.4, 4, rows=2)
_add(96, '0', 15.4, 5, units=2)
_add(110, '.', 17.4, 5)

_KEY_MAP = {key['vk']: key for key in KEYS if key['vk']}
_ALIASES = {16: 160, 17: 162, 18: 164, 92: 91, 93: 163,
            36: 103, 35: 97, 44: 45, 19: 144, 145: 144}


def resolve_vk(vk):
    """Map generic modifiers/navigation fallbacks; numpad keys stay distinct."""
    return _ALIASES.get(vk, vk)


def key_target(vk):
    key = _KEY_MAP.get(resolve_vk(vk))
    return (key['x'], key['y']) if key else None


def _polygon(points):
    return QPolygonF([QPointF(*point) for point in points])


def _rounded_polygon(points, radius=.8):
    """Round the corners without losing the cap's projected trapezoid."""
    import math
    count = len(points)
    edges = []
    for i, point in enumerate(points):
        prev, following = points[(i - 1) % count], points[(i + 1) % count]
        dp = max(.001, math.dist(point, prev))
        dn = max(.001, math.dist(point, following))
        r = min(radius, dp * .25, dn * .25)
        before = (point[0] + (prev[0] - point[0]) * r / dp,
                  point[1] + (prev[1] - point[1]) * r / dp)
        after = (point[0] + (following[0] - point[0]) * r / dn,
                 point[1] + (following[1] - point[1]) * r / dn)
        edges.append((before, point, after))
    path = QPainterPath(QPointF(*edges[0][0]))
    for before, point, after in edges:
        path.lineTo(QPointF(*before))
        path.quadTo(QPointF(*point), QPointF(*after))
    path.closeSubpath()
    return path


def _mix(a, b, amount):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() * (1 - amount) + b.red() * amount),
                  round(a.green() * (1 - amount) + b.green() * amount),
                  round(a.blue() * (1 - amount) + b.blue() * amount))


_ROW_COLORS = ('#d3d1c7', '#d1cfc5', '#bfc1b9', '#a6adaa', '#879396', '#65777c')


def _draw_cap(p, key, active, flash):
    u, v, units, rows = key['u'], key['v'], key['units'], key['rows']
    depth = rows - .12
    down = 2.2 if active else 0.0
    rise = key['rise'] - down
    base = [_project(u + .045, v + .025), _project(u + units - .045, v + .025),
            _project(u + units - .045, v + depth), _project(u + .045, v + depth)]
    top = [_project(u + .15, v + .12), _project(u + units - .15, v + .12),
           _project(u + units - .13, v + depth - .11), _project(u + .13, v + depth - .11)]
    top = [(x, y - rise) for x, y in top]
    color = QColor(_ROW_COLORS[min(int(v), 5)])
    f = min(1., max(0., flash))
    if active or f > .01:
        color = _mix(color, '#bbd995', .76 if active else f * .60)
    p.setPen(Qt.NoPen)
    # Contact shadow under each raised cap, followed by sculpted side walls.
    p.setBrush(QColor(0, 0, 0, 75))
    p.drawPolygon(_polygon([(x + .5, y + 1.0) for x, y in base]))
    p.setBrush(color.darker(144))
    p.drawPolygon(_polygon([top[0], top[3], base[3], base[0]]))
    p.setBrush(color.darker(161))
    p.drawPolygon(_polygon([top[1], top[2], base[2], base[1]]))
    front = QLinearGradient(top[3][0], top[3][1], base[3][0], base[3][1])
    front.setColorAt(0, color.darker(123))
    front.setColorAt(1, color.darker(151))
    p.setBrush(front)
    p.drawPolygon(_polygon([top[3], top[2], base[2], base[3]]))
    # Rounded, slightly dished top. The lower edge is a thin bevel, not a grid.
    gradient = QLinearGradient(top[0][0], top[0][1], top[3][0], top[3][1])
    gradient.setColorAt(0, color.lighter(109))
    gradient.setColorAt(.65, color)
    gradient.setColorAt(1, color.lighter(103))
    p.setBrush(gradient)
    p.setPen(QPen(QColor(236, 239, 233, 48), .45))
    p.drawPath(_rounded_polygon(top, 1.0))
    p.setPen(QPen(QColor(239, 244, 234, 82), .6))
    p.drawLine(QPointF(top[3][0] + 1.1, top[3][1]), QPointF(top[2][0] - 1.1, top[2][1]))
    # The reference keyboard uses subdued front-side legends. At small desktop
    # scale these become texture; hovering bubbles provide the readable label.
    label = '' if key['vk'] == 32 else key['label']
    if label:
        font = QFont('Segoe UI')
        font.setPixelSize(4 if len(label) > 2 else 5)
        p.setFont(font)
        p.setPen(QColor('#61747d') if v < 3 else QColor('#b1bdbe'))
        cx = (top[2][0] + top[3][0]) * .5
        cy = (top[2][1] + top[3][1]) * .5
        p.drawText(QRectF(cx - key['w'] / 2, cy - .8, key['w'], 5.5), Qt.AlignCenter, label)


def _draw_keyboard(painter, state):
    """Draw all caps and their case into the pet's already-scaled painter."""
    p = painter
    p.save()
    # Case follows the key matrix, with a visible bevel and substantial front.
    tl = _project(-.30, -.31)
    tr = _project(19.7, -.31)
    br = _project(19.7, 6.12)
    bl = _project(-.30, 6.12)
    drop = 6.3
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 28))
    p.drawRoundedRect(QRectF(bl[0] - 1.5, bl[1] + 3, br[0] - bl[0] + 4, 8), 5, 5)
    p.setBrush(QColor('#151a1e'))
    p.drawPolygon(_polygon([tl, tr, (br[0] + .5, br[1] + drop), (bl[0] - .8, bl[1] + drop)]))
    front = QLinearGradient(bl[0], bl[1], bl[0], bl[1] + drop)
    front.setColorAt(0, QColor('#41494b'))
    front.setColorAt(.24, QColor('#282f32'))
    front.setColorAt(1, QColor('#161c20'))
    p.setBrush(front)
    p.drawPolygon(_polygon([bl, br, (br[0] + .5, br[1] + drop), (bl[0] - .8, bl[1] + drop)]))
    p.setBrush(QColor('#151b1e'))
    p.drawPolygon(_polygon([tr, br, (br[0] + .5, br[1] + drop), (tr[0] + .5, tr[1] + drop)]))
    deck = QLinearGradient(tl[0], tl[1], bl[0], bl[1])
    deck.setColorAt(0, QColor('#393f41'))
    deck.setColorAt(.4, QColor('#2b3235'))
    deck.setColorAt(1, QColor('#242b2e'))
    p.setBrush(deck)
    p.setPen(QPen(QColor('#51595b'), .85))
    p.drawPath(_rounded_polygon([tl, tr, br, bl], 2.5))
    p.setPen(QPen(QColor(161, 173, 173, 70), .65))
    p.drawLine(QPointF(bl[0] + 2, bl[1] + 1.5), QPointF(br[0] - 2, br[1] + 1.5))
    pressed = {resolve_vk(vk) for vk in state.get('pressed', ())}
    flashes = {}
    for vk, strength in state.get('key_flashes', {}).items():
        vk = resolve_vk(vk)
        flashes[vk] = max(strength, flashes.get(vk, 0))
    for key in sorted(KEYS, key=lambda k: (k['v'] + k['rows'], k['u'])):
        _draw_cap(p, key, key['vk'] in pressed, flashes.get(key['vk'], 0))
    # Narrow cool-white status lights separate the main keys and number pad.
    p.setPen(Qt.NoPen)
    for i in range(4):
        x, y = _project(15.16, 2.0 + i * .75)
        p.setBrush(QColor('#bcd9dc') if i == 0 else QColor('#657d83'))
        p.drawRoundedRect(QRectF(x - .65, y - .7, 1.3, 2.2), .4, .4)
    p.restore()


_REST_IMAGE = None
_REST_RECT = QRectF(160, 372, 296, 98)


def draw_keyboard(painter, state):
    """Cache the detailed unpressed keyboard; animate pressed caps at full detail."""
    global _REST_IMAGE
    if state.get('pressed') or state.get('key_flashes'):
        _draw_keyboard(painter, state)
        return
    if _REST_IMAGE is None:
        # Three pixels per scene unit preserve bevels when the pet is enlarged.
        _REST_IMAGE = QImage(888, 294, QImage.Format_ARGB32_Premultiplied)
        _REST_IMAGE.fill(Qt.transparent)
        cached = QPainter(_REST_IMAGE)
        cached.setRenderHint(QPainter.Antialiasing)
        cached.setRenderHint(QPainter.TextAntialiasing)
        cached.scale(3, 3)
        cached.translate(-_REST_RECT.x(), -_REST_RECT.y())
        _draw_keyboard(cached, {})
        cached.end()
    painter.save()
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawImage(_REST_RECT, _REST_IMAGE)
    painter.restore()
