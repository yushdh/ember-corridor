"""Furnace cut. Art and collision use the same right-facing grip, angle and edge length."""
from bisect import bisect_right
from itertools import accumulate
from math import cos, radians, sin

from .combat import segment_entry, wall_entry

FULL_CHARGE = 54
DAMAGE = 54
HITSTOP = 10
# Wrist relative to the sole, blade angle and luminous edge length in logical pixels.
BLADE = (
    (8, 30, 34, 32),
    (3, 36, 77, 36),
    (-1, 43, 117, 40),
    (-2, 44, 119, 94),
    (-2, 45, 121, 92),
    (-1, 44, 119, 96),
    (5, 43, 78, 103),
    (13, 39, 35, 114),
    (20, 32, 4, 112),
    (21, 27, -13, 103),
    (20, 25, -15, 74),
    (17, 25, -18, 49),
    (13, 26, -11, 35),
    (9, 29, 4, 32),
)
DURATIONS = (16, 18, 20, 6, 6, 6, 3, 4, 4, 4, 6, 7, 8, 7)
RELEASE_FRAME = 6
RECOVERY_FRAME = 10
SWING_ENDS = tuple(accumulate(DURATIONS[RELEASE_FRAME:]))


def ray(frame, fraction):
    """A ray inside this frame's swept sector, interpolating both wrist and tip."""
    previous = BLADE[frame - 1]
    gx, gy, angle, length = (a + (b - a) * fraction for a, b in zip(previous, BLADE[frame]))
    angle = radians(angle)
    return (gx, gy), (gx + length * cos(angle), gy + length * sin(angle))


class FlameCut:
    def __init__(self):
        self.charge = self.swing = -1
        self.victims = set()

    @property
    def busy(self):
        return self.charge >= 0 or self.swing >= 0

    @property
    def frame(self):
        if self.swing >= 0:
            return RELEASE_FRAME + bisect_right(SWING_ENDS, self.swing)
        if self.charge >= FULL_CHARGE:
            return 3 + ((self.charge - FULL_CHARGE) // 6) % 3
        return bisect_right((16, 34), self.charge)

    def reset(self):
        self.charge = self.swing = -1
        self.victims.clear()

    def update(self, c, w, axis, pressed, held):
        if self.swing >= 0:
            self.swing += 1
            if self.swing >= SWING_ENDS[-1]:
                self.reset()
        elif self.charge >= 0:
            if held:
                self.charge += 1
                if self.charge == FULL_CHARGE:
                    c.emit("ignite", w.x, w.y + 40)
            elif self.charge >= FULL_CHARGE:
                self.charge, self.swing = -1, 0
                w.move_x(w.facing * 8, c.surfaces)
                c.serial += 1
                c.emit("firecut", w.x, w.y + 36, facing=w.facing, attack_id=c.serial)
            else:
                self.reset()
        elif (
            pressed
            and held
            and c.weapon == "light"
            and w.support
            and not (c.attack or c.hurt or w.tucked or c.cast_age >= 0)
        ):
            self.charge = 0
            c.buffer = 0
            if axis:
                w.facing = 1 if axis > 0 else -1

        if self.swing >= 0 and self.frame < RECOVERY_FRAME:
            self.strike(c, w)

    def strike(self, c, w):
        # Sweep a fan rather than the large bounding rectangle of the visual arc.
        for j in range(13):
            start, end = ray(self.frame, j / 12)
            a = (w.x + w.facing * start[0], w.y + start[1])
            b = (w.x + w.facing * end[0], w.y + end[1])
            if wall_entry((w.x, w.y + 32), a, c.surfaces) <= 1:
                continue
            wall = wall_entry(a, b, c.surfaces)
            for target_index, enemy in enumerate(c.foes):
                if not enemy.hp or id(enemy) in self.victims:
                    continue
                hit = segment_entry(a, b, enemy.rect)
                if hit is None or hit >= wall:
                    continue
                self.victims.add(id(enemy))
                enemy.hp = max(0, enemy.hp - c.melee_damage(DAMAGE))
                if not enemy.hp:
                    enemy.enter("dead")
                elif enemy.kind != "bell":
                    enemy.enter("hurt")
                if enemy.kind != "bell":
                    enemy.knockback = w.facing * (2.1 if enemy.kind == "ram" else 4.2)
                c.emit(
                    "hit",
                    a[0] + hit * (b[0] - a[0]),
                    a[1] + hit * (b[1] - a[1]),
                    enemy=enemy.kind,
                    target=target_index,
                    action="firecut",
                    hp=enemy.hp,
                    facing=w.facing,
                    attack_id=c.serial,
                    frame=self.frame,
                )
                c.freeze = HITSTOP
