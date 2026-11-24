"""Short games must end cleanly and preserve actual keyboard contacts."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from animation import CatAnimation
from scene_layout import PAW_REST


class PlayAnimationTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100.0
        self.targets = {65: (180., 410.), 76: (365., 410.)}
        self.cat = CatAnimation(self.targets.get, now=self.clock)
        self.state = self.cat.update(self.clock)

    def advance(self, seconds):
        end = self.clock + seconds
        states = []
        while self.clock < end:
            self.clock = min(end, self.clock + 1 / 120)
            self.state = self.cat.update(self.clock)
            states.append(self.state)
        return states

    def event(self, kind, **values):
        self.cat.handle(dict(type=kind, time=self.clock, **values))

    def test_feed_raises_food_paw_chews_then_returns_to_rest(self):
        self.assertTrue(self.cat.start_play('feed', self.clock))
        states = self.advance(.8)
        self.assertEqual(self.state['play_action'], 'feed')
        self.assertTrue(self.state['play_holding'])
        self.assertLess(math.dist(self.state['right_paw'], (286, 223)), 6)
        self.assertTrue(self.state['right_contact'])
        self.assertGreater(max(s['play_mouth'] for s in states), .7)
        self.advance(2.3)
        self.assertIsNone(self.state['play_action'])
        self.assertEqual(self.state['play_strength'], 0)
        self.advance(.6)
        self.assertLess(math.dist(self.state['right_paw'], PAW_REST['right']), .1)
        self.assertLess(abs(self.state['body_lean']), .01)

    def test_toy_moves_in_bounds_and_cat_bats_toward_it(self):
        self.cat.start_play('toy', self.clock)
        states = self.advance(3.9)
        targets = [s['play_target'] for s in states if s['play_target']]
        self.assertGreater(max(t[0] for t in targets) - min(t[0] for t in targets), 40)
        self.assertGreater(max(t[1] for t in targets) - min(t[1] for t in targets), 45)
        for x, y in targets:
            self.assertTrue(360 <= x <= 410 and 230 <= y <= 290)
        sample = states[110]
        self.assertLess(math.dist(sample['right_paw'], sample['play_target']), 50)
        self.assertGreater(sample['head_x'], .8)
        self.advance(.2)
        self.assertIsNone(self.state['play_action'])
        self.assertIsNone(self.state['play_target'])

    def test_play_wakes_sleep_and_hover_does_not_hide_the_activity(self):
        self.cat.force_sleep = True
        self.advance(2.5)
        self.assertGreater(self.state['sleep'], .98)
        self.cat.set_touch('head', self.clock)
        self.cat.start_play('feed', self.clock)
        self.cat.sleep_after = .1
        self.advance(.7)
        self.assertFalse(self.cat.force_sleep)
        self.assertLess(self.state['sleep'], .01)
        self.assertEqual(self.state['touch_strength'], 0)
        self.assertEqual(self.state['play_action'], 'feed')
        self.assertGreater(self.state['head_y'], .4)
        self.advance(2.6)
        self.assertIsNone(self.state['play_action'])
        self.assertGreater(self.state['touch_strength'], .9)

    def test_keyboard_has_priority_over_food_and_toy_and_does_not_queue(self):
        for action in ('feed', 'toy'):
            with self.subTest(action=action):
                self.setUp()
                self.cat.start_play(action, self.clock)
                self.advance(.4)
                self.event('move', x=400, y=300)
                self.event('button', button='left', down=True)
                self.event('key', vk=76, down=True)
                self.advance(.3)
                self.assertIn(76, self.state['pressed'])
                self.assertLess(math.dist(self.state['right_paw'], self.targets[76]), 5)
                self.assertFalse(self.state['play_holding'])
                self.assertFalse(self.state['left_contact'])
                self.assertEqual(self.state['play_action'], action)
                self.event('key', vk=76, down=False)
                self.advance(.5)
                self.assertLess(self.state['right_paw'][1], 320)

    def test_three_quick_head_clicks_trigger_one_bounded_dizzy_reaction(self):
        for _ in range(3):
            self.assertTrue(self.cat.tap('head', self.clock))
            self.advance(.18)
        self.assertEqual(self.state['play_action'], 'dizzy')
        started = self.cat.play_started
        for _ in range(30):
            self.assertFalse(self.cat.tap('head', self.clock))
            self.advance(.02)
        self.assertEqual(self.cat.play_started, started)
        self.assertLessEqual(len(self.cat.head_taps), 3)
        self.advance(2)
        self.assertIsNone(self.state['play_action'])
        # Widely separated clicks do not accidentally accumulate a combo.
        for _ in range(3):
            self.cat.tap('head', self.clock)
            self.advance(1.3)
        self.assertNotEqual(self.state['play_action'], 'dizzy')

    def test_click_regions_and_paw_sides_produce_distinct_reactions(self):
        results = {}
        histories = {}
        for region in ('head', 'cheek', 'belly', 'paw', 'tail'):
            self.setUp()
            self.cat.tap(region, self.clock, side='left')
            histories[region] = self.advance(.45)
            results[region] = histories[region][-1]
            self.assertEqual(self.state['play_action'], 'poke_' + region)
        self.assertEqual(results['head']['play_face'], 'surprised')
        self.assertGreater(results['cheek']['blink'], .8)
        self.assertGreater(max(abs(s['body_twist']) for s in histories['belly']), .3)
        self.assertLess(results['paw']['left_paw'][1], PAW_REST['left'][1] - 50)
        self.assertLess(math.dist(results['paw']['right_paw'], PAW_REST['right']), .1)
        self.assertGreater(results['tail']['head_x'], .8)
        self.setUp()
        self.cat.tap('paw', self.clock, side='right')
        self.advance(.45)
        self.assertLess(self.state['right_paw'][1], PAW_REST['right'][1] - 50)
        self.assertLess(math.dist(self.state['left_paw'], PAW_REST['left']), .1)

    def test_cancel_play_clears_combo_but_preserves_live_input(self):
        self.event('key', vk=65, down=True)
        self.event('button', button='left', down=True)
        self.cat.tap('head', self.clock)
        self.advance(.1)
        self.cat.cancel_play()
        self.advance(.2)
        self.assertIsNone(self.state['play_action'])
        self.assertEqual(self.state['play_strength'], 0)
        self.assertEqual(len(self.cat.head_taps), 0)
        self.assertIn(65, self.state['pressed'])
        self.assertTrue(self.state['mouse_down'])

    def test_replacement_is_bounded_and_every_pose_has_finite_coordinates(self):
        self.assertFalse(self.cat.start_play('unknown', self.clock))
        self.assertFalse(self.cat.tap(None, self.clock))
        for i in range(200):
            self.cat.start_play('feed' if i % 2 else 'toy', self.clock)
            self.advance(.005)
            for field in ('body_lean', 'body_twist', 'body_bob', 'head_x', 'head_y', 'play_strength'):
                self.assertTrue(math.isfinite(self.state[field]))
            for field in ('left_paw', 'right_paw'):
                self.assertTrue(all(math.isfinite(value) for value in self.state[field]))
        self.advance(4.5)
        self.assertIsNone(self.state['play_action'])
        self.assertFalse(self.state['ghosts'])


if __name__ == '__main__':
    unittest.main()
