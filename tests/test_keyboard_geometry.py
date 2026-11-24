"""Contact checks for the compact keyboard and its independent number pad."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keyboard_art import KEYS, NUMPAD_ENTER, key_target, resolve_vk


class KeyboardGeometryTests(unittest.TestCase):
    def test_key_contacts_are_finite_and_inside_the_visible_keyboard(self):
        key_codes = [key['vk'] for key in KEYS if key['vk']]
        self.assertEqual(len(key_codes), len(set(key_codes)))
        for key in KEYS:
            if not key['vk']:
                continue  # Fn is a visible hardware key, not a Windows key code.
            with self.subTest(key=key['label'], vk=key['vk']):
                target = key_target(key['vk'])
                self.assertIsNotNone(target)
                x, y = target
                self.assertTrue(math.isfinite(x) and math.isfinite(y))
                self.assertGreaterEqual(x, 164)
                self.assertLessEqual(x, 448)
                self.assertGreaterEqual(y, 375)
                self.assertLessEqual(y, 461)

    def test_number_pad_digits_have_their_own_contacts(self):
        for digit in range(10):
            with self.subTest(digit=digit):
                main = key_target(48 + digit)
                pad = key_target(96 + digit)
                self.assertIsNotNone(main)
                self.assertIsNotNone(pad)
                self.assertNotEqual(resolve_vk(48 + digit), resolve_vk(96 + digit))
                self.assertGreater(pad[0], main[0] + 30)

    def test_number_pad_enter_is_separate_from_the_main_enter(self):
        main = key_target(13)
        pad = key_target(NUMPAD_ENTER)
        self.assertIsNotNone(main)
        self.assertIsNotNone(pad)
        self.assertGreater(pad[0], main[0] + 30)
        self.assertGreater(math.dist(main, pad), 40)


if __name__ == '__main__':
    unittest.main()
