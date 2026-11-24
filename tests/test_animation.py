"""Behavior checks for simultaneous input, bounded trails, and waking."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from animation import CatAnimation


class CatAnimationTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100.0
        self.targets = {65: (180.0, 410.0), 76: (365.0, 410.0),
                        83: (205.0, 410.0), 68: (235.0, 410.0),
                        70: (275.0, 410.0), 74: (325.0, 410.0)}
        self.cat = CatAnimation(self.targets.get, now=self.clock)
        self.state = self.cat.update(self.clock)
        self.rest_state = dict(self.state)

    def event(self, kind, **values):
        self.cat.handle(dict(type=kind, time=self.clock, **values))

    def key(self, vk, down=True):
        self.event('key', vk=vk, down=down)

    def advance(self, seconds):
        end = self.clock + seconds
        while self.clock < end:
            self.clock = min(end, self.clock + 1 / 120)
            self.state = self.cat.update(self.clock)
        return self.state

    def assertNear(self, actual, expected, tolerance=7.0):
        self.assertLess(math.dist(actual, expected), tolerance,
                        msg=f'{actual} is not near {expected}')

    def type_burst(self, count=12):
        keys = list(self.targets)
        for i in range(count):
            vk = keys[i % len(keys)]
            self.key(vk)
            self.advance(.045)
            self.key(vk, False)

    def test_distinct_keys_reach_distinct_keyboard_locations_and_release(self):
        self.key(65)
        state = self.advance(.22)
        self.assertNear(state['left_paw'], self.targets[65])
        self.assertIn(65, state['pressed'])
        self.key(76)
        state = self.advance(.22)
        self.assertNear(state['right_paw'], self.targets[76])
        self.assertEqual(state['pressed'], {65, 76})
        self.key(65, False)
        self.key(76, False)
        state = self.advance(.5)
        self.assertFalse(state['pressed'])
        self.assertNear(state['left_paw'], self.rest_state['left_paw'])
        self.assertNear(state['right_paw'], self.rest_state['right_paw'])

    def test_fast_typing_makes_multiple_fading_paw_afterimages(self):
        self.type_burst()
        state = self.advance(.01)
        self.assertTrue(state['frantic'])
        self.assertGreaterEqual(len(state['ghosts']), 2)
        self.assertTrue(all(0 < g['alpha'] < 1 for g in state['ghosts']))
        self.assertTrue(all(math.isfinite(g['x']) and math.isfinite(g['y'])
                            for g in state['ghosts']))
        state = self.advance(.8)
        self.assertFalse(state['ghosts'])
        self.assertFalse(state['frantic'])

    def test_mouse_drag_and_keyboard_use_both_paws_at_once(self):
        self.event('move', x=100, y=100)
        self.event('move', x=260, y=160)
        self.event('button', button='left', down=True)
        self.cat.set_gaze(.8, -.6)
        self.key(65)
        state = self.advance(.3)
        self.assertNear(state['left_paw'], state['mouse'])
        self.assertNear(state['right_paw'], self.targets[65])
        self.assertTrue(state['mouse_down'])
        self.assertGreater(state['gaze_x'], .5)
        self.assertLess(state['gaze_y'], -.3)
        self.assertLess(math.dist(state['mouse'], (125, 363)), 18)
        self.assertLess(math.dist(state['left_paw'], (207, 263)), 160)
        self.event('button', button='left', down=False)
        self.key(65, False)
        self.assertFalse(self.advance(.02)['mouse_down'])

    def test_mouse_reaches_stay_close_to_the_cat_at_all_motion_extremes(self):
        self.event('move', x=0, y=0)
        self.event('button', button='left', down=True)
        for x, y in [(-10000, -10000), (10000, -10000),
                     (10000, 10000), (-10000, 10000)]:
            self.event('move', x=x, y=y)
            state = self.advance(.35)
            self.assertGreaterEqual(state['mouse'][0], 111)
            self.assertLessEqual(state['mouse'][0], 139)
            self.assertGreaterEqual(state['mouse'][1], 353)
            self.assertLessEqual(state['mouse'][1], 373)
            self.assertNear(state['left_paw'], state['mouse'])
            self.assertLess(math.dist(state['left_paw'], (207, 263)), 160,
                            'Mouse operation must not recreate the stretched arm.')

    def test_idle_sleep_and_key_wake_are_smooth_and_prompt(self):
        self.cat.sleep_after = .2
        state = self.advance(2.5)
        self.assertGreater(state['sleep'], .98)
        self.assertGreater(state['blink'], .98)
        self.key(65)
        state = self.advance(.35)
        self.assertLess(state['sleep'], .05)
        self.assertIn(65, state['pressed'])

    def test_first_mouse_motion_wakes_a_cat_that_has_not_seen_mouse_input(self):
        self.cat.sleep_after = .2
        self.advance(2.5)
        self.cat.sleep_after = 45
        self.cat.force_sleep = True
        self.advance(.1)
        self.event('move', x=500, y=300)
        state = self.advance(.4)
        self.assertLess(state['sleep'], .05,
                        'The first observed mouse movement must cancel sleep.')

    def test_dense_input_finishes_without_animation_backlog(self):
        keys = list(self.targets)
        for i in range(240):
            vk = keys[i % len(keys)]
            self.key(vk)
            self.advance(.004)
            self.key(vk, False)
        state = self.advance(.9)
        self.assertFalse(state['pressed'])
        self.assertFalse(state['ghosts'])
        self.assertFalse(state['bubbles'])
        self.assertFalse(state['key_flashes'])
        self.assertNear(state['left_paw'], self.rest_state['left_paw'], tolerance=1)
        self.assertNear(state['right_paw'], self.rest_state['right_paw'], tolerance=1)

    def test_held_key_prevents_sleep_and_key_up_clears_pressed_state(self):
        self.cat.sleep_after = .2
        self.key(65)
        state = self.advance(2)
        self.assertLess(state['sleep'], .01)
        self.assertIn(65, state['pressed'])
        self.assertEqual(state['key_flashes'][65], 1.0)
        self.key(65, False)
        self.assertNotIn(65, self.advance(.01)['pressed'])
        self.assertGreater(self.advance(2.5)['sleep'], .98)

    def test_afterimages_can_be_disabled_without_disabling_typing(self):
        self.cat.trails_enabled = False
        self.type_burst()
        state = self.advance(.01)
        self.assertTrue(state['frantic'])
        self.assertFalse(state['ghosts'])
        self.assertTrue(state['bubbles'])
        self.assertTrue(state['key_flashes'])
        self.assertGreater(state['right_paw'][1], 350)


if __name__ == '__main__':
    unittest.main()
