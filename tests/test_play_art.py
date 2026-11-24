"""Transient props stay local, follow their anchors, and restore QPainter state."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPen
from PyQt5.QtWidgets import QApplication

from play_art import draw_play


class PlayArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def state(self, action, **changes):
        result = {'play_action': action, 'play_progress': .3, 'play_phase': .9,
                  'play_strength': 1., 'play_side': 'right', 'play_target': (400, 250),
                  'play_holding': True, 'right_paw': (286, 223),
                  'right_contact': True, 'right_contact_weight': 1.,
                  'body_lean': .4, 'body_twist': .3, 'head_x': .2}
        result.update(changes)
        return result

    def render(self, state):
        image = QImage(540, 520, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        draw_play(painter, state, 100)
        painter.end()
        return image

    def test_inactive_play_leaves_the_scene_untouched(self):
        for state in ({}, self.state(None), self.state('toy', play_strength=0)):
            image = self.render(state)
            self.assertTrue(all(image.pixelColor(x, y).alpha() == 0
                                for x in range(0, 540, 5) for y in range(0, 520, 5)))

    def test_every_effect_preserves_painter_and_state_and_stays_inside_canvas(self):
        for action in ('feed', 'toy', 'poke_head', 'poke_cheek', 'poke_belly',
                       'poke_paw', 'poke_tail', 'dizzy'):
            with self.subTest(action=action):
                state = self.state(action)
                original = deepcopy(state)
                image = QImage(540, 520, QImage.Format_ARGB32_Premultiplied)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                painter.setOpacity(.7)
                painter.setPen(QPen(QColor('#ff0000'), 3))
                before_transform = painter.transform()
                before_pen = painter.pen()
                draw_play(painter, state, 100)
                self.assertEqual(painter.transform(), before_transform)
                self.assertEqual(painter.pen(), before_pen)
                self.assertAlmostEqual(painter.opacity(), .7)
                self.assertFalse(painter.hasClipping())
                painter.end()
                self.assertEqual(state, original)
                visible = sum(image.pixelColor(x, y).alpha() > 0
                              for x in range(0, 520, 2) for y in range(0, 500, 2))
                self.assertGreater(visible, 3)
                self.assertLess(visible, 900)
                self.assertTrue(all(image.pixelColor(x, y).alpha() == 0
                                    for x in range(520, 540) for y in range(520)))
                self.assertTrue(all(image.pixelColor(x, y).alpha() == 0
                                    for x in range(540) for y in range(500, 520)))

    def test_toy_tracks_scene_target_and_food_disappears_when_paw_is_typing(self):
        for target in ((380, 230), (430, 295)):
            image = self.render(self.state('toy', play_target=target))
            self.assertGreater(image.pixelColor(*target).alpha(), 240)
        image = self.render(self.state('feed', play_holding=False))
        self.assertEqual(image.pixelColor(273, 206).alpha(), 0)

    def test_food_is_eaten_in_visible_bites(self):
        amounts = []
        for progress in (.25, .49, .65):
            image = self.render(self.state('feed', play_progress=progress))
            amounts.append(sum(image.pixelColor(x, y).alpha() > 100
                               for x in range(245, 310) for y in range(185, 235)))
        self.assertGreater(amounts[0], amounts[1])
        self.assertGreater(amounts[1], amounts[2])


if __name__ == '__main__':
    unittest.main()
