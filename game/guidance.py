"""Gameplay bindings and the four contextual lessons. Times are in seconds."""
import math

# Portable key names in save files. The order is also the pause-menu order.
ACTIONS = (
    ("left", "向左移动", "A"),
    ("right", "向右移动", "D"),
    ("jump", "跳跃", "SPACE"),
    ("drop", "下穿配合跳跃", "S"),
    ("attack", "攻击", "J"),
    ("roll", "翻滚", "K"),
    ("skill", "潮印", "Q"),
    ("flame", "蓄焰斩 · 按住后松开", "L"),
    ("use", "操作机关或开匣", "E"),
    ("light", "装备弯刃", "KEY_1"),
    ("heavy", "装备重锤", "KEY_2"),
)
DEFAULT_KEYS = tuple(row[2] for row in ACTIONS)
KEY_NAMES = (
    tuple("ABCDEFGHIJKLMNOPQSTUVWXYZ")
    + tuple("KEY_" + str(i) for i in range(10))
    + ("SPACE", "LEFT", "RIGHT", "UP", "DOWN")
)
LESSONS = {"move": "移动", "jump": "跳上台阶", "attack": "攻击", "roll": "翻滚闪避"}
LIFETIME, FADE = 2.75, 0.16


def key_label(name):
    return {"SPACE": "Space", "LEFT": "←", "RIGHT": "→", "UP": "↑", "DOWN": "↓"}.get(
        name, name.removeprefix("KEY_")
    )


class Guidance:
    def __init__(self, learned=()):
        self.reset(learned)

    def reset(self, learned):
        self.known = set(learned)
        self.shown = set()
        self.first_control = True
        self.clear()

    def clear(self):
        self.active = None
        self.age = 0.0
        self.remaining = 0.0

    def advance(self, dt):
        if self.active:
            self.age += dt
            self.remaining -= dt
            if self.remaining <= 1e-7:
                self.clear()

    @property
    def opacity(self):
        return round(255 * max(0, min(1, self.remaining / FADE)))

    @property
    def key_opacity(self):
        # Two smooth dips; the label and panel do not pulse.
        pulse = math.sin(math.pi * self.age / 0.64) ** 2 if self.age < 1.28 else 0
        return round(self.opacity * (1 - 0.34 * pulse))

    def observe(self, candidates, completed):
        if not self.first_control and self.active != "move" and "move" in candidates:
            candidates = [name for name in candidates if name != "move"]
        self.first_control = False
        fresh = set(completed) - self.known
        self.known.update(fresh)
        if self.active in fresh:
            self.remaining = min(self.remaining, FADE)
        if self.active and self.active not in self.known and self.active not in candidates:
            self.clear()
        for name in candidates:  # Ordered by urgency.
            if name == self.active:
                break
            if name not in self.shown and name not in self.known:
                self.active, self.age, self.remaining = name, 0.0, LIFETIME
                self.shown.add(name)
                break
        return fresh


def opportunities(w, c, surfaces):
    result = []
    foes = [e for e in c.foes if e.hp] if c else []
    if any(
        e.state == "warn" and abs(e.x - w.x) <= e.spec.trigger + 65 and abs(e.y - w.y) <= 80
        for e in foes
    ):
        result.append("roll")
    if any(abs(e.x - w.x) <= 64 + e.spec.half_width and abs(e.y - w.y) < 38 for e in foes):
        result.append("attack")
    if w.support and not any(abs(e.x - w.x) < 105 and abs(e.y - w.y) < 65 for e in foes):
        for s in surfaces:
            gap = s.left - w.x if w.facing > 0 else w.x - s.right
            if (s.one_way or s.bottom <= w.y) and 0 < s.top - w.y <= 76 and 0 < gap <= 106:
                result.append("jump")
                break
    if not result:
        result.append("move")
    return result
