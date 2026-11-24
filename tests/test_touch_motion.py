"""Whole-body reaches and dwell-based petting must coexist with live input."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from animation import CatAnimation
from scene_layout import PAW_REST


class TouchMotionTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100.0
        self.targets = {65: (180.0, 410.0), 76: (365.0, 410.0)}
        self.cat = CatAnimation(self.targets.get, now=self.clock)
        self.state = self.cat.update(self.clock)

    def event(self, kind, **values):
        self.cat.handle(dict(type=kind, time=self.clock, **values))

    def advance(self, seconds):
        states = []
        end = self.clock + seconds
        while self.clock < end:
            self.clock = min(end, self.clock + 1 / 120)
            self.state = self.cat.update(self.clock)
            states.append(self.state)
        return states

    def touch(self, region):
        self.cat.set_touch(region, self.clock)

    def test_mouse_reach_moves_body_but_keeps_paw_on_mouse_then_settles(self):
        self.event('move', x=0, y=0)
        self.event('move', x=-160, y=80)
        self.event('button', button='left', down=True)
        self.advance(.35)
        self.assertLess(self.state['body_lean'], -.35)
        self.assertTrue(self.state['left_contact'])
        self.assertLess(math.dist(self.state['left_paw'], self.state['mouse']), 5)
        self.event('button', button='left', down=False)
        self.advance(2)
        for state in self.advance(.5):
            self.assertLess(abs(state['body_lean']), .001)
            self.assertLess(abs(state['body_twist']), .001)
            self.assertFalse(state['left_contact'])

    def test_keyboard_reach_shifts_weight_and_bobs_without_moving_key_target(self):
        self.event('key', vk=76, down=True)
        states = self.advance(.3)
        self.assertGreater(max(s['body_bob'] for s in states), 1)
        self.assertGreater(self.state['body_lean'], .25)
        self.assertGreater(self.state['body_twist'], .1)
        self.assertTrue(self.state['right_contact'])
        self.assertLess(math.dist(self.state['right_paw'], self.targets[76]), 5)
        self.advance(1)
        self.assertLess(abs(self.state['body_bob']), .001)
        self.assertTrue(self.state['right_contact'])

    def test_touch_requires_dwell_and_fades_out_when_pointer_leaves(self):
        self.touch('head')
        self.advance(.1)
        self.assertIsNone(self.state['touch_region'])
        self.assertEqual(self.state['touch_strength'], 0)
        self.touch(None)
        self.advance(.3)
        self.assertEqual(self.state['touch_strength'], 0)
        self.touch('head')
        self.advance(.6)
        strength = self.state['touch_strength']
        self.assertGreater(strength, .9)
        self.assertEqual(self.state['touch_region'], 'head')
        self.touch(None)
        self.advance(.08)
        self.assertGreater(self.state['touch_strength'], 0)
        self.assertLess(self.state['touch_strength'], strength)
        self.advance(.6)
        self.assertEqual(self.state['touch_strength'], 0)
        self.assertIsNone(self.state['touch_region'])

    def test_five_touch_regions_have_distinct_visible_reactions(self):
        results = {}
        histories = {}
        for region in ('head', 'cheek', 'belly', 'paw', 'tail'):
            self.setUp()
            self.touch(region)
            histories[region] = self.advance(.95)
            results[region] = self.state
        self.assertGreater(results['head']['blink'], .9)
        self.assertLess(results['head']['head_y'], -.65)
        self.assertLess(results['cheek']['head_x'], -.6)
        self.assertLess(results['cheek']['body_lean'], -.25)
        self.assertGreater(max(abs(s['body_twist']) for s in histories['belly']), .25)
        self.assertLess(results['belly']['left_paw'][1], PAW_REST['left'][1] - 15)
        self.assertLess(results['belly']['right_paw'][1], PAW_REST['right'][1] - 15)
        self.assertLess(results['paw']['right_paw'][1], PAW_REST['right'][1] - 40)
        self.assertFalse(results['paw']['right_contact'])
        self.assertGreater(results['tail']['head_x'], .75)
        self.assertGreater(results['tail']['body_twist'], .5)

    def test_touch_wakes_sleeping_cat_and_continues_without_restarting_phase(self):
        self.cat.force_sleep = True
        self.advance(2.5)
        self.assertGreater(self.state['sleep'], .98)
        self.touch('head')
        for _ in range(100):
            self.touch('head')
            self.advance(.01)
        self.assertFalse(self.cat.force_sleep)
        self.assertLess(self.state['sleep'], .01)
        self.assertGreater(self.state['touch_phase'], .8)
        self.assertGreater(self.state['touch_strength'], .99)

    def test_neck_scratch_lifts_chin_relaxes_eyes_and_preserves_typing(self):
        self.touch('neck')
        self.advance(.95)
        self.assertEqual(self.state['touch_region'], 'neck')
        self.assertGreater(self.state['blink'], .9)
        self.assertLess(self.state['head_y'], -.85)
        self.assertLess(abs(self.state['body_lean']), .15)
        self.assertLess(self.state['body_bob'], -1.5)
        self.event('key', vk=76, down=True)
        self.advance(.3)
        self.assertTrue(self.state['right_contact'])
        self.assertLess(math.dist(self.state['right_paw'], self.targets[76]), 5)
        self.touch(None)
        self.advance(.7)
        self.assertIsNone(self.state['touch_region'])

    def test_neck_tap_is_a_short_chin_lift_and_does_not_count_as_head_combo(self):
        for _ in range(3):
            self.assertTrue(self.cat.tap('neck', self.clock))
            self.advance(.18)
        self.assertEqual(self.state['play_action'], 'poke_neck')
        self.assertGreater(self.state['blink'], .9)
        self.assertFalse(self.cat.head_taps)
        self.advance(1.5)
        self.assertIsNone(self.state['play_action'])

    def test_keys_still_reach_keyboard_while_petting_retracts_mouse_paw(self):
        self.event('move', x=0, y=0)
        self.event('button', button='left', down=True)
        self.advance(.3)
        self.assertTrue(self.state['left_contact'])
        self.touch('belly')
        self.advance(.6)
        self.assertFalse(self.state['left_contact'])
        self.assertGreater(math.dist(self.state['left_paw'], self.state['mouse']), 65)
        self.event('move', x=100, y=80)
        self.event('key', vk=65, down=True)
        self.advance(.3)
        self.assertIn(65, self.state['pressed'])
        self.assertEqual(self.state['touch_region'], 'belly')
        self.assertTrue(self.state['left_contact'])
        self.assertFalse(self.state['right_contact'])
        self.assertLess(math.dist(self.state['left_paw'], self.targets[65]), 5)
        self.assertLess(self.state['right_paw'][1], PAW_REST['right'][1] - 15)
        self.assertEqual(self.state['key_flashes'][65], 1)

    def test_leaving_touch_resumes_mouse_without_waiting_for_reaction_to_fade(self):
        self.event('move', x=0, y=0)
        self.advance(.3)
        self.assertGreater(self.state['left_contact_weight'], .99)
        self.touch('belly')
        states = self.advance(.6)
        release = next(state for state in states if not state['left_contact'])
        self.assertGreater(release['left_contact_weight'], .8)
        self.assertFalse(self.state['left_contact'])
        self.assertLess(self.state['left_contact_weight'], .03)
        self.event('move', x=60, y=25)
        self.touch(None)
        self.advance(1 / 120)
        self.assertTrue(self.state['left_contact'])
        self.assertGreater(self.state['touch_strength'], .8)
        self.assertLess(self.state['left_contact_weight'], .5)
        self.advance(.3)
        self.assertLess(math.dist(self.state['left_paw'], self.state['mouse']), 5)
        self.assertGreater(self.state['left_contact_weight'], .99)

    def test_rendered_paw_space_changes_add_less_than_two_pixels_per_frame(self):
        from cat_renderer import paw_endpoint

        self.event('move', x=0, y=0)
        self.event('move', x=-160, y=120)
        self.event('button', button='left', down=True)
        history = self.advance(.5)
        self.touch('belly')
        history += self.advance(.8)
        self.touch(None)
        history += self.advance(.6)
        self.event('button', button='left', down=False)
        history += self.advance(.8)
        # Sample at 60 Hz. Holding the actual animated paw/body pose constant
        # isolates unwanted coordinate-space snapping from the intended reach.
        history = history[::2]
        extra_motion = []
        original_snap = []
        for previous, current in zip(history, history[1:]):
            for side in ('left', 'right'):
                field = side + '_contact_weight'
                prior_weight = dict(current, **{field: previous[field]})
                p = paw_endpoint(current, side)
                q = paw_endpoint(prior_weight, side)
                extra_motion.append(math.hypot(p.x() - q.x(), p.y() - q.y()))
                if previous[side + '_contact'] != current[side + '_contact']:
                    old_bool = dict(current, **{field: float(previous[side + '_contact'])})
                    new_bool = dict(current, **{field: float(current[side + '_contact'])})
                    a = paw_endpoint(old_bool, side)
                    b = paw_endpoint(new_bool, side)
                    original_snap.append(math.hypot(a.x() - b.x(), a.y() - b.y()))
        self.assertGreater(max(original_snap), 4)
        self.assertLess(max(extra_motion), 2)


if __name__ == '__main__':
    unittest.main()
