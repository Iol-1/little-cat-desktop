"""Input-driven animation. No input text is retained or written to disk."""
from collections import deque
import math
import random
import time
from scene_layout import FACE_CENTER, MOUSE_HOME, MOUSE_TRAVEL, PAW_REST


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def smooth(current, target, speed, dt):
    return current + (target - current) * (1.0 - math.exp(-speed * dt))


class CatAnimation:
    def __init__(self, key_target, key_labels=None, now=None):
        self.key_target = key_target
        self.key_labels = key_labels or {}
        self.now = time.monotonic() if now is None else now
        self.last_activity = self.now
        self.last_mouse = -1e9
        self.mouse_screen = None
        self.mouse_offset = [0.0, 0.0]
        self.mouse = list(MOUSE_HOME)
        self.mouse_buttons = set()
        self.pressed = set()
        self.flashes = {}
        self.strokes = {'left': None, 'right': None}
        self.paws = {side: list(point) for side, point in PAW_REST.items()}
        self.contact_weights = {'left': 0.0, 'right': 0.0}
        self.gaze = [0.0, 0.0]
        self.head = [0.0, 0.0]
        self.gaze_target = [0.0, 0.0]
        self.ghosts = deque(maxlen=24)
        self.bubbles = deque(maxlen=9)
        self.recent_keys = deque(maxlen=40)
        self.last_repeat = {}
        self.last_ghost = -1e9
        self.next_blink = self.now + 3.3
        self.blink_started = -1e9
        self.sleep = 0.0
        self.sleep_after = 45.0
        self.force_sleep = False
        self.paused = False
        self.last_side = 'right'
        self.trails_enabled = True
        self.body = [0.0, 0.0, 0.0]
        self.touch_candidate = None
        self.touch_since = self.now
        self.touch_region = None
        self.touch_strength = 0.0
        self.touch_started = self.now
        self.play_action = None
        self.play_started = self.now
        self.play_duration = 0.0
        self.play_side = 'right'
        self.head_taps = deque(maxlen=3)

    def set_gaze(self, x, y):
        self.gaze_target[:] = [clamp(x, -1, 1), clamp(y, -1, 1)]

    def _begin_play(self, action, duration, now, side='right'):
        self.play_action = action
        self.play_started = now
        self.play_duration = duration
        self.play_side = side
        self.last_activity = now
        self.force_sleep = False
        return True

    def start_play(self, action, now=None):
        """Start one short activity; repeated selections replace rather than queue."""
        durations = {'feed': 3.0, 'toy': 4.0}
        if action not in durations:
            return False
        self.head_taps.clear()
        return self._begin_play(action, durations[action], self.now if now is None else now)

    def tap(self, region, now=None, side=None):
        """Respond to a deliberate click, separately from sustained hovering."""
        durations = {'head': 1.05, 'cheek': 1.3, 'neck': 1.3,
                     'belly': 1.5, 'paw': 1.25, 'tail': 1.4}
        if region not in durations:
            return False
        now = self.now if now is None else now
        side = side if side in ('left', 'right') else 'right'
        if region == 'head':
            # Let the little dizzy animation finish even if the user keeps tapping.
            if self.play_action == 'dizzy' and self._playing_at(now):
                return False
            while self.head_taps and now - self.head_taps[0] > 1.2:
                self.head_taps.popleft()
            self.head_taps.append(now)
            if len(self.head_taps) >= 3:
                self.head_taps.clear()
                return self._begin_play('dizzy', 2.0, now, side)
        else:
            self.head_taps.clear()
        return self._begin_play('poke_' + region, durations[region], now, side)

    def cancel_play(self):
        """Cancel a game for pause/nap without modifying keyboard or mouse state."""
        self.play_action = None
        self.play_duration = 0.0
        self.head_taps.clear()

    def _playing_at(self, now):
        return self.play_action is not None and now < self.play_started + self.play_duration

    def _play_pose(self, now):
        action = self.play_action
        if action is not None and not self._playing_at(now):
            self.play_action = action = None
        pose = {'action': action, 'phase': 0.0, 'progress': 0.0, 'strength': 0.0,
                'gaze': (0.0, 0.0), 'body': (0.0, 0.0, 0.0), 'paws': {},
                'target': None, 'blink': 0.0, 'mouth': 0.0, 'face': None}
        if action is None:
            return pose
        phase = max(0.0, now - self.play_started)
        progress = clamp(phase / self.play_duration, 0.0, 1.0)
        ramp = min(clamp(phase / .16, 0.0, 1.0),
                   clamp((self.play_duration - phase) / .38, 0.0, 1.0))
        strength = ramp * ramp * (3 - 2 * ramp)
        pose.update(phase=phase, progress=progress, strength=strength)
        self.last_activity = now
        self.force_sleep = False
        sign = -1 if self.play_side == 'left' else 1
        if action == 'feed':
            chew = .5 + .5 * math.sin(phase * 17)
            pose.update(gaze=(.18, .7), body=(.05, .08, -2 + chew),
                        blink=.30, mouth=.25 + .6 * chew, face='happy', target=(286., 223.))
            pose['paws']['right'] = ((286., 223. + 2 * math.sin(phase * 8)), True)
        elif action == 'toy':
            target = (385 + 25 * math.sin(phase * 3.4), 260 + 30 * math.sin(phase * 4.6))
            batting = .5 + .5 * math.sin(phase * 7)
            pose.update(gaze=(.95, -.15 + .4 * math.sin(phase * 4.6)),
                        body=(.35 + .12 * batting, .22 + .2 * batting, -3 * batting),
                        mouth=.15, face='surprised', target=target)
            pose['paws']['right'] = ((target[0] - 12 * (1 - batting),
                                      target[1] + 6 + 25 * (1 - batting)), True)
        elif action == 'poke_head':
            pose.update(gaze=(-sign * .65, -.55), body=(-sign * .22, -sign * .2, -4),
                        mouth=.7, face='surprised')
        elif action == 'poke_cheek':
            pose.update(gaze=(sign * .75, -.35), body=(sign * .28, sign * .25, -2),
                        blink=.82, mouth=.2, face='happy')
        elif action == 'poke_neck':
            pose.update(gaze=(sign * .18, -.96), body=(sign * .10, sign * .10, -1.8),
                        blink=.96, face='happy')
        elif action == 'poke_belly':
            wiggle = math.sin(phase * 16)
            pose.update(gaze=(wiggle * .35, .4), body=(wiggle * .38, wiggle * .85, -4),
                        blink=.75, mouth=.55 + .25 * abs(wiggle), face='happy')
            for side, rest in PAW_REST.items():
                pose['paws'][side] = ((rest[0] + (-10 if side == 'left' else 10),
                                       rest[1] - 28 - 5 * abs(wiggle)), False)
        elif action == 'poke_paw':
            rest = PAW_REST[self.play_side]
            pose.update(gaze=(sign * .45, .7), body=(-sign * .22, -sign * .2, -2),
                        mouth=.45, face='surprised')
            pose['paws'][self.play_side] = ((rest[0] + sign * 8, rest[1] - 59), False)
        elif action == 'poke_tail':
            pose.update(gaze=(1., -.25), body=(.42, .8, -2), mouth=.65, face='surprised')
        elif action == 'dizzy':
            wobble = math.sin(phase * 9)
            pose.update(gaze=(wobble * .85, .25 * math.cos(phase * 7)),
                        body=(wobble * .5, -.45 * wobble, -2),
                        blink=.2, mouth=.5, face='surprised')
        return pose

    def set_touch(self, region, now=None):
        """Set the hovered body part; a brief crossing does not count as petting."""
        if region not in (None, 'head', 'cheek', 'neck', 'belly', 'paw', 'tail'):
            raise ValueError(f'Unknown touch region: {region!r}')
        if region != self.touch_candidate:
            self.touch_candidate = region
            self.touch_since = self.now if now is None else now

    def _update_touch(self, now, dt):
        ready = self.touch_candidate is not None and now - self.touch_since >= .15
        if ready:
            self.last_activity = now
            self.force_sleep = False
        wanted = self.touch_candidate if ready else None
        # Fade the old reaction before changing parts, so crossing an outline
        # cannot instantly teleport a raised paw or flip the head.
        if wanted != self.touch_region and self.touch_strength < .025:
            self.touch_region = wanted
            self.touch_started = now
        target = 1.0 if wanted is not None and wanted == self.touch_region else 0.0
        self.touch_strength = smooth(self.touch_strength, target, 7.5 if target else 11, dt)
        if target == 0 and self.touch_strength < .005:
            self.touch_strength = 0.0
            self.touch_region = None
        # Once the pointer leaves, resume mouse work immediately while the
        # face/body finish their release; otherwise a short cursor move would
        # expire before the nuzzle has faded and cause an aborted mouse reach.
        return ready or (self.touch_candidate is not None and self.touch_strength > .04)

    def handle(self, event):
        t = event.get('time', self.now)
        kind = event['type']
        if kind == 'wheel':
            self.last_activity = t
            self.last_mouse = t
            self.force_sleep = False
            return
        if kind == 'move':
            x, y = event['x'], event['y']
            old = self.mouse_screen
            self.mouse_screen = (x, y)
            if old is None:
                self.last_activity = t
                self.last_mouse = t
                self.force_sleep = False
                return
            dx, dy = x - old[0], y - old[1]
            if dx or dy:
                self.last_activity = t
                self.last_mouse = t
                self.force_sleep = False
                self.mouse_offset[0] = clamp(self.mouse_offset[0] + dx * .08, -MOUSE_TRAVEL[0], MOUSE_TRAVEL[0])
                self.mouse_offset[1] = clamp(self.mouse_offset[1] + dy * .07, -MOUSE_TRAVEL[1], MOUSE_TRAVEL[1])
            return
        if kind == 'button':
            self.last_activity = t
            self.last_mouse = t
            self.force_sleep = False
            button = event.get('button', 'left')
            if event.get('down'):
                self.mouse_buttons.add(button)
            else:
                self.mouse_buttons.discard(button)
            return
        if kind != 'key':
            return
        vk = event['vk']
        self.last_activity = t
        self.force_sleep = False
        if not event['down']:
            self.pressed.discard(vk)
            self.last_repeat.pop(vk, None)
            return
        repeat = vk in self.pressed
        self.pressed.add(vk)
        if repeat and t - self.last_repeat.get(vk, -1e9) < .055:
            return
        self.last_repeat[vk] = t
        self.flashes[vk] = t
        target = self.key_target(vk)
        if target is None:
            return
        self.recent_keys.append(t)
        mouse_busy = ((t - self.last_mouse < .45) or bool(self.mouse_buttons)) and not (
            self.touch_candidate is not None and self.touch_strength > .04) and not self._playing_at(t)
        if mouse_busy:
            side = 'right'
        elif target[0] < FACE_CENTER[0]:
            side = 'left'
        else:
            side = 'right'
        # Very fast bursts alternate paws when both are available.
        recent = sum(t - ts < .24 for ts in self.recent_keys)
        if recent >= 3 and not mouse_busy:
            side = 'left' if self.last_side == 'right' else 'right'
        self.last_side = side
        self.strokes[side] = {'time': t, 'target': target, 'vk': vk}
        label = self.key_labels.get(vk, chr(vk) if 48 <= vk <= 90 else '')
        if label:
            self.bubbles.append({'label': label, 'time': t,
                                 'x': target[0], 'y': target[1] - 48})

    def update(self, now=None):
        now = time.monotonic() if now is None else now
        dt = clamp(now - self.now, .001, .08)
        self.now = now
        touching = self._update_touch(now, dt)
        play = self._play_pose(now)
        playing = play['action'] is not None
        play_strength = play['strength']
        touch = 0.0 if playing else self.touch_strength
        touch_phase = max(0.0, now - self.touch_started)
        region = self.touch_region
        idle = max(0, now - self.last_activity)
        sleeping = self.force_sleep or (idle >= self.sleep_after and not self.pressed and not self.mouse_buttons)
        self.sleep = smooth(self.sleep, 1.0 if sleeping else 0.0, 2.4 if sleeping else 10.0, dt)
        mouse_busy = (now - self.last_mouse < .45 or bool(self.mouse_buttons)) and not touching and not playing
        typing = now - max(self.flashes.values(), default=-1e9) < .40
        gx, gy = self.gaze_target
        if typing and not mouse_busy:
            gx = (self.paws[self.last_side][0] - FACE_CENTER[0]) / 180
            gy = .8
        # The reactions have distinct silhouettes, with no perpetual idle
        # swaying. A slow nuzzle comes from the duration of this touch only.
        nuzzle = math.sin(touch_phase * 4.0)
        tickle = math.sin(touch_phase * 13.0)
        touch_head = {
            'head': (.12 * nuzzle, -.85),
            'cheek': (-.8 + .12 * nuzzle, -.32),
            'neck': (.18 * nuzzle, -.96),
            'belly': (.24 * tickle, .45),
            'paw': (.35, .68),
            'tail': (.95, -.12),
        }.get(region, (0.0, 0.0))
        gx = gx * (1 - touch) + touch_head[0] * touch
        gy = gy * (1 - touch) + touch_head[1] * touch
        gx = gx * (1 - play_strength) + play['gaze'][0] * play_strength
        gy = gy * (1 - play_strength) + play['gaze'][1] * play_strength
        self.gaze[0] = smooth(self.gaze[0], gx * (1 - self.sleep), 23, dt)
        self.gaze[1] = smooth(self.gaze[1], gy * (1 - self.sleep), 23, dt)
        self.head[0] = smooth(self.head[0], self.gaze[0], 7.0, dt)
        self.head[1] = smooth(self.head[1], self.gaze[1] + self.sleep * .6, 6.0, dt)
        if not mouse_busy:
            self.mouse_offset[0] = smooth(self.mouse_offset[0], 0, 2.4, dt)
            self.mouse_offset[1] = smooth(self.mouse_offset[1], 0, 2.4, dt)
        self.mouse[0] = smooth(self.mouse[0], MOUSE_HOME[0] + self.mouse_offset[0], 26, dt)
        self.mouse[1] = smooth(self.mouse[1], MOUSE_HOME[1] + self.mouse_offset[1], 26, dt)
        frantic = sum(now - t < .45 for t in self.recent_keys) >= 4
        contacts = {'left': False, 'right': False}
        key_contacts = {'left': False, 'right': False}
        reaches = []
        strike_bob = 0.0
        for side in ('left', 'right'):
            rest = PAW_REST[side]
            target = rest
            if region == 'belly':
                target = (rest[0] + (-7 if side == 'left' else 7) * touch,
                          rest[1] - (24 + 5 * tickle) * touch)
            elif region == 'paw' and side == 'right':
                target = (rest[0] + 7 * touch, rest[1] - (49 + 4 * nuzzle) * touch)
            elif region == 'head':
                target = (rest[0], rest[1] - 7 * touch)
            if side in play['paws']:
                play_target, scene_contact = play['paws'][side]
                target = (target[0] * (1 - play_strength) + play_target[0] * play_strength,
                          target[1] * (1 - play_strength) + play_target[1] * play_strength)
                contacts[side] = scene_contact and play_strength > .02
            stroke = self.strokes[side]
            if stroke:
                age = now - stroke['time']
                held = stroke['vk'] in self.pressed
                if age < .17 or held:
                    tx, ty = stroke['target']
                    lift = -math.sin(clamp(age / .095, 0, 1) * math.pi) * 38
                    target = (tx, ty + lift + (2 if held else 0))
                    contacts[side] = True
                    key_contacts[side] = True
                    reaches.append(clamp((tx - FACE_CENTER[0]) / 145, -1, 1))
                    if age < .27:
                        strike_bob += math.sin(clamp(age / .27, 0, 1) * math.pi) * 3.5
                else:
                    self.strokes[side] = None
            if side == 'left' and mouse_busy:
                target = (self.mouse[0], self.mouse[1] - 4 + (3 if self.mouse_buttons else 0))
                contacts[side] = True
            if self.sleep > .35 and not contacts[side] and not touching and not playing:
                target = (rest[0], rest[1] - self.sleep * 13)
            if frantic and self.trails_enabled and now - self.last_ghost > .027:
                x, y = self.paws[side]
                if math.hypot(x - target[0], y - target[1]) > 5:
                    self.ghosts.append({'side': side, 'x': x, 'y': y, 'time': now})
            speed = 34 if frantic else 25
            self.paws[side][0] = smooth(self.paws[side][0], target[0], speed, dt)
            self.paws[side][1] = smooth(self.paws[side][1], target[1], speed, dt)
            # A paw cannot switch instantaneously between scene space and
            # torso space. Blend both endpoints while entering/leaving contact.
            self.contact_weights[side] = smooth(
                self.contact_weights[side], 1.0 if contacts[side] else 0.0,
                20 if contacts[side] else 9, dt)
        # Plant the working paw in scene coordinates while the chest and
        # shoulder move toward it; the renderer carries resting paws with the
        # torso. This makes reaching a whole-body action instead of arm growth.
        lean = (sum(reaches) / len(reaches) * .58) if reaches else 0.0
        twist = (1 if self.last_side == 'right' else -1) * .22 if reaches else 0.0
        if mouse_busy:
            lean = lean * .45 - .55 + self.mouse_offset[0] / 90
            twist -= .15
        bob = min(strike_bob, 5.5)
        touch_body = {
            'head': (.08 * nuzzle, .08 * nuzzle, -3.0),
            'cheek': (-.38 + .08 * nuzzle, -.18, -1.5),
            'neck': (.12 * nuzzle, .12 * nuzzle, -1.8),
            'belly': (.25 * tickle, .65 * tickle, -4 + 1.5 * math.cos(touch_phase * 13)),
            'paw': (.16, .22, -2.0),
            'tail': (.32, .62, -1.0),
        }.get(region, (0.0, 0.0, 0.0))
        lean += touch_body[0] * touch
        twist += touch_body[1] * touch
        bob += touch_body[2] * touch
        lean += play['body'][0] * play_strength
        twist += play['body'][1] * play_strength
        bob += play['body'][2] * play_strength
        self.body[0] = smooth(self.body[0], clamp(lean, -1, 1), 8.5, dt)
        self.body[1] = smooth(self.body[1], clamp(twist, -1, 1), 10, dt)
        self.body[2] = smooth(self.body[2], bob, 13, dt)
        if frantic and now - self.last_ghost > .027:
            self.last_ghost = now
        while self.ghosts and now - self.ghosts[0]['time'] > .23:
            self.ghosts.popleft()
        while self.bubbles and now - self.bubbles[0]['time'] > .70:
            self.bubbles.popleft()
        self.flashes = {k: t for k, t in self.flashes.items() if now - t < .45 or k in self.pressed}
        if now >= self.next_blink:
            self.blink_started = now
            self.next_blink = now + random.uniform(2.6, 5.4)
        phase = (now - self.blink_started) / .18
        blink = math.sin(phase * math.pi) if 0 <= phase <= 1 else 0.0
        return {
            'gaze_x': self.gaze[0], 'gaze_y': self.gaze[1],
            'head_x': self.head[0], 'head_y': self.head[1],
            'blink': max(blink, self.sleep, play['blink'] * play_strength, touch * {
                'head': .96, 'cheek': .87, 'neck': .96, 'belly': .55, 'paw': .1,
            }.get(region, 0.0)), 'sleep': self.sleep,
            'body_lean': self.body[0], 'body_twist': self.body[1], 'body_bob': self.body[2],
            'touch_region': region, 'touch_strength': touch, 'touch_phase': touch_phase,
            'play_action': play['action'], 'play_progress': play['progress'],
            'play_phase': play['phase'], 'play_strength': play_strength, 'play_side': self.play_side,
            'play_target': play['target'], 'play_mouth': play['mouth'] * play_strength,
            'play_face': play['face'],
            'play_holding': play['action'] == 'feed' and not key_contacts['right'],
            'left_contact': contacts['left'], 'right_contact': contacts['right'],
            'left_contact_weight': self.contact_weights['left'],
            'right_contact_weight': self.contact_weights['right'],
            'breathing': math.sin(now * (2.2 if sleeping else 1.8)),
            'left_paw': tuple(self.paws['left']), 'right_paw': tuple(self.paws['right']),
            'mouse': tuple(self.mouse), 'pressed': set(self.pressed),
            'key_flashes': {k: 1.0 if k in self.pressed else clamp(1 - (now - t) / .45, 0, 1)
                            for k, t in self.flashes.items()},
            'ghosts': [dict(g, alpha=.35 * (1 - (now - g['time']) / .23)**1.3)
                       for g in self.ghosts] if self.trails_enabled else [],
            'bubbles': [dict(b, y=b['y'] - (now - b['time']) * 75,
                             alpha=clamp(1 - (now - b['time']) / .70, 0, 1))
                        for b in self.bubbles],
            'mouse_down': bool(self.mouse_buttons), 'frantic': frantic,
        }

