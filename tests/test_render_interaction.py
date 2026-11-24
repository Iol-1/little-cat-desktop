"""Render on transparent images without showing windows or sending OS input."""
from itertools import combinations
from collections import deque
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from animation import CatAnimation
from cat_renderer import (body_transform, draw_pet, face_transform, hit_test,
                          key_target, paw_endpoint)
from scene_layout import CANVAS_H, CANVAS_W
from skins import SKINS


class RenderInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep the normal Qt platform/font database, but never create a window.
        cls.app = QApplication.instance() or QApplication([])

    def state(self, **changes):
        state = CatAnimation(key_target, now=100).update(100)
        state.update(breathing=0, blink=0, sleep=0, body_lean=0,
                     body_twist=0, body_bob=0, touch_region=None,
                     touch_strength=0, skin='black')
        state.update(changes)
        for side in ('left', 'right'):
            if f'{side}_contact' in changes and f'{side}_contact_weight' not in changes:
                state[f'{side}_contact_weight'] = float(changes[f'{side}_contact'])
        return state

    def render(self, state):
        image = QImage(CANVAS_W * 2, CANVAS_H * 2,
                       QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(2, 2)
        draw_pet(painter, state, 100)
        painter.end()
        return image

    def alpha_at(self, image, point):
        return image.pixelColor(round(point.x() * 2),
                                round(point.y() * 2)).alpha()

    def region_at(self, point, state):
        return hit_test((point.x(), point.y()), state, 100)

    def test_all_twelve_skins_render_with_distinct_coat_patterns(self):
        self.assertTrue({'black', 'calico', 'ragdoll'} <= set(SKINS))
        self.assertGreaterEqual(len(SKINS), 12)
        images = {skin: self.render(self.state(skin=skin))
                  for skin in SKINS}
        # Sample the coat across the head and torso, not only the eye color.
        coat_points = [(x, y) for x in range(185, 350, 5)
                       for y in range(90, 340, 5)
                       if y < 135 or y > 200]
        for first, second in combinations(images, 2):
            with self.subTest(first=first, second=second):
                changed = sum(images[first].pixelColor(x * 2, y * 2).rgba()
                              != images[second].pixelColor(x * 2, y * 2).rgba()
                              for x, y in coat_points)
                self.assertGreater(changed, len(coat_points) * .3)
        for skin, image in images.items():
            with self.subTest(skin=skin):
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                self.assertEqual(self.alpha_at(image, QPointF(265, 280)), 255)

    def test_touch_regions_follow_the_leaning_body_and_rotating_head(self):
        for lean in (-.85, .85):
            state = self.state(body_lean=lean, body_twist=lean * .7,
                               body_bob=3, head_x=-lean, head_y=.5,
                               left_contact=False, right_contact=False)
            transform = body_transform(state)
            face = face_transform(state)
            image = self.render(state)
            # Interior landmarks: crown, lower cheek, neck, belly and resting paws.
            points = [('head', transform.map(face.map(QPointF(0, -40)))),
                      ('cheek', transform.map(face.map(QPointF(61, 37)))),
                      ('neck', transform.map(QPointF(265, 251))),
                      ('belly', transform.map(QPointF(265, 293))),
                      ('paw', paw_endpoint(state, 'left')),
                      ('paw', paw_endpoint(state, 'right'))]
            for region, point in points:
                with self.subTest(lean=lean, region=region):
                    self.assertEqual(self.region_at(point, state), region)
                    self.assertEqual(self.alpha_at(image, point), 255)
            crown = transform.map(QPointF(265, 110))
            self.assertGreater(abs(crown.x() - 265), 10,
                               'A lean must move the torso/head, not just arms.')

    def test_neck_region_keeps_face_priority_and_stays_on_visible_body(self):
        for lean in (-.8, 0, .8):
            for head_y in (-1., 1.):
                state = self.state(body_lean=lean, head_x=lean, head_y=head_y,
                                   touch_region='neck', touch_strength=1.)
                transform = body_transform(state)
                face = face_transform(state)
                image = self.render(state)
                neck = transform.map(QPointF(265, 251))
                self.assertEqual(self.region_at(neck, state), 'neck')
                self.assertEqual(self.alpha_at(image, neck), 255)
                # Even where the moving chin overlaps the neck ellipse, it
                # belongs to the face. Lower torso remains a belly target.
                chin = transform.map(face.map(QPointF(0, 78)))
                self.assertEqual(self.region_at(chin, state), 'head')
                self.assertEqual(self.region_at(transform.map(QPointF(265, 280)), state), 'belly')

    def test_stationary_neck_pointer_survives_the_scratch_animation(self):
        cat = CatAnimation(key_target, now=100)
        state = cat.update(100)
        now = 100.
        point = (265., 251.)
        for _ in range(180):
            now += 1 / 60
            self.assertEqual(hit_test(point, state, now), 'neck')
            cat.set_touch('neck', now)
            state = cat.update(now)
        self.assertGreater(state['touch_strength'], .99)

    def test_contact_paws_stay_on_keyboard_while_body_moves(self):
        target = key_target(ord('J'))
        for lean in (-.8, .8):
            state = self.state(body_lean=lean, body_twist=lean,
                               right_paw=target, right_contact=True)
            point = paw_endpoint(state, 'right')
            with self.subTest(lean=lean):
                self.assertAlmostEqual(point.x(), target[0])
                self.assertAlmostEqual(point.y(), target[1])
                self.assertEqual(self.region_at(point, state), 'paw')

    def test_rear_feet_are_opaque_inside_their_outline_in_every_skin(self):
        # These points are inside the rear toe contours, below the torso fill.
        # In v3 they had alpha 24 (only the shadow): the foot was an open line.
        foot_points = (QPointF(206, 362), QPointF(330, 362))
        for skin in SKINS:
            for lean in (0, -.7, .7):
                state = self.state(skin=skin, body_lean=lean,
                                   body_twist=lean * .5,
                                   left_paw=(125, 357), right_paw=(385, 420),
                                   left_contact=True, right_contact=True)
                image = self.render(state)
                transform = body_transform(state)
                for index, point in enumerate(foot_points):
                    with self.subTest(skin=skin, lean=lean, foot=index):
                        self.assertEqual(self.alpha_at(image, transform.map(point)),
                                         255, 'The inside of a foot must be filled.')

    def test_suspended_front_paws_have_no_enclosed_transparent_gaps(self):
        # Suspend both paws over empty canvas so keyboard/mouse pixels cannot
        # hide a gap. The old fill and the wider white outline enclosed holes.
        for skin in SKINS:
            state = self.state(skin=skin, left_paw=(125, 280),
                               right_paw=(405, 280),
                               left_contact=True, right_contact=True)
            image = self.render(state)
            for center_x in (125, 405):
                x0, x1 = (center_x - 24) * 2, (center_x + 25) * 2
                y0, y1 = 256 * 2, 305 * 2
                empty = {(x, y) for x in range(x0, x1)
                         for y in range(y0, y1)
                         if image.pixelColor(x, y).alpha() == 0}
                outside = {point for point in empty
                           if point[0] in (x0, x1 - 1)
                           or point[1] in (y0, y1 - 1)}
                pending = deque(outside)
                while pending:
                    x, y = pending.popleft()
                    for point in ((x - 1, y), (x + 1, y),
                                  (x, y - 1), (x, y + 1)):
                        if point in empty and point not in outside:
                            outside.add(point)
                            pending.append(point)
                with self.subTest(skin=skin, paw=center_x):
                    self.assertFalse(empty - outside,
                                     'Transparent holes are trapped inside the paw outline.')
                    self.assertEqual(self.alpha_at(image, QPointF(center_x, 290)), 255)

    def test_coat_patches_remain_inside_cat_when_twisting_or_being_tickled(self):
        poses = [self.state(body_lean=1, body_twist=-1, body_bob=-4),
                 self.state(body_lean=-.25, body_twist=.65, body_bob=-5,
                            touch_region='belly', touch_strength=1,
                            touch_phase=.7, left_paw=(224, 320),
                            right_paw=(314, 320), left_contact=False,
                            right_contact=False)]
        for pose_index, state in enumerate(poses):
            black = self.render(state)
            for skin in SKINS.keys() - {'black'}:
                image = self.render(dict(state, skin=skin))
                leaks = []
                # A one-pixel allowance accounts for different antialiased
                # border colors; a pattern must not add new exterior paint.
                for y in range(50, 770, 2):
                    for x in range(120, 950, 2):
                        if image.pixelColor(x, y).alpha() < 20 or black.pixelColor(x, y).alpha():
                            continue
                        if not any(black.pixelColor(x + dx, y + dy).alpha()
                                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                            leaks.append((x, y))
                with self.subTest(pose=pose_index, skin=skin):
                    self.assertFalse(leaks, f'Coat paint escaped silhouette at {leaks[:5]}.')

    def test_keyboard_mouse_and_transparent_margin_do_not_trigger_petting(self):
        for lean in (-.8, 0, .8):
            state = self.state(body_lean=lean, left_contact=False,
                               right_contact=False)
            for point in ((430, 441), (220, 434), (125, 363),
                          (10, 10), (490, 280), (265, 470)):
                with self.subTest(lean=lean, point=point):
                    self.assertIsNone(hit_test(point, state, 100))


if __name__ == '__main__':
    unittest.main()
