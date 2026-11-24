"""A slow or failed sound driver must not block the caller or build a queue."""
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sound_player import PurrPlayer


def until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.002)
    return predicate()


class SoundPlayerTests(unittest.TestCase):
    def test_slow_start_does_not_block_setters_and_only_latest_intent_is_played(self):
        entered, release = threading.Event(), threading.Event()
        calls, threads = [], []

        def native(sound, flags):
            calls.append('start' if sound else 'stop')
            threads.append(threading.get_ident())
            if sound:
                entered.set()
                release.wait(2)

        player = PurrPlayer('purr.wav', play_sound=native)
        self.addCleanup(release.set)
        self.addCleanup(player.close)
        started = time.perf_counter()
        player.set_playing(True)
        self.assertLess(time.perf_counter() - started, .15)
        self.assertTrue(entered.wait(1))
        started = time.perf_counter()
        for _ in range(300):
            player.set_playing(False)
            player.set_playing(True)
        player.set_playing(False)
        self.assertLess(time.perf_counter() - started, .15)
        release.set()
        self.assertTrue(until(lambda: player.status == 'idle'))
        self.assertEqual(calls, ['start', 'stop'])
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.get_ident())

    def test_blocked_stop_and_close_do_not_wait_for_native_device(self):
        stop_entered, stop_release = threading.Event(), threading.Event()
        calls = []

        def native(sound, flags):
            calls.append('start' if sound else 'stop')
            if not sound:
                stop_entered.set()
                stop_release.wait(2)

        player = PurrPlayer('purr.wav', play_sound=native)
        self.addCleanup(stop_release.set)
        self.addCleanup(player.close)
        player.set_playing(True)
        self.assertTrue(until(lambda: player.playing))
        started = time.perf_counter()
        player.set_playing(False)
        self.assertLess(time.perf_counter() - started, .15)
        self.assertTrue(stop_entered.wait(1))
        started = time.perf_counter()
        player.close()
        player.set_playing(True)
        self.assertLess(time.perf_counter() - started, .15)
        stop_release.set()
        self.assertTrue(until(lambda: player.status == 'closed'))
        self.assertEqual(calls, ['start', 'stop'])

    def test_close_while_start_is_blocked_stops_after_initialization_finishes(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def native(sound, flags):
            calls.append('start' if sound else 'stop')
            if sound:
                entered.set()
                release.wait(2)

        player = PurrPlayer('purr.wav', play_sound=native)
        self.addCleanup(release.set)
        self.addCleanup(player.close)
        player.set_playing(True)
        self.assertTrue(entered.wait(1))
        started = time.perf_counter()
        player.close()
        self.assertLess(time.perf_counter() - started, .15)
        release.set()
        self.assertTrue(until(lambda: player.status == 'closed'))
        self.assertEqual(calls, ['start', 'stop'])

    def test_repeated_desired_state_does_not_repeat_native_calls(self):
        calls = []
        player = PurrPlayer('purr.wav', play_sound=lambda sound, flags: calls.append(bool(sound)))
        self.addCleanup(player.close)
        for _ in range(500):
            player.set_playing(True)
        self.assertTrue(until(lambda: player.status == 'playing'))
        self.assertEqual(calls, [True])
        for _ in range(500):
            player.set_playing(False)
        self.assertTrue(until(lambda: player.status == 'idle'))
        self.assertEqual(calls, [True, False])

    def test_device_failure_is_cached_until_desired_state_changes(self):
        calls = []

        def native(sound, flags):
            calls.append(bool(sound))
            if sound:
                raise RuntimeError('injected device failure')

        player = PurrPlayer('purr.wav', play_sound=native)
        self.addCleanup(player.close)
        player.set_playing(True)
        self.assertTrue(until(lambda: player.status == 'error'))
        for _ in range(500):
            player.set_playing(True)
        self.assertEqual(calls, [True])
        self.assertIn('injected device failure', player.error)
        player.set_playing(False)
        self.assertTrue(until(lambda: player.status == 'idle'))
        player.set_playing(True)
        self.assertTrue(until(lambda: player.status == 'error'))
        self.assertEqual(calls, [True, False, True])

    def test_unused_player_closes_without_audio_initialization(self):
        calls = []
        player = PurrPlayer('purr.wav', play_sound=lambda *args: calls.append(args))
        player.set_playing(False)
        player.close()
        player.close()
        player.set_playing(True)
        self.assertEqual(player.status, 'closed')
        self.assertFalse(calls)


if __name__ == '__main__':
    unittest.main()
