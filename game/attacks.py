"""Strike timing in 120-Hz ticks; points are measured from the sole, facing right."""
from dataclasses import dataclass
from math import cos, sin, radians


@dataclass(frozen=True)
class Strike:
    ticks: tuple
    grips: tuple
    angles: tuple
    length: int
    damage: int
    cancel_tick: int
    advance: int

    @property
    def duration(self):
        return sum(self.ticks)

    def frame(self, tick):
        for index, span in enumerate(self.ticks):
            if tick < span:
                return index
            tick -= span
        return len(self.ticks) - 1

    def blade(self, frame):
        x, y = self.grips[frame]
        angle = radians(self.angles[frame])
        return (x, y), (round(x + self.length * cos(angle)), round(y + self.length * sin(angle)))

    def active(self, frame):
        return frame in (3, 4)


# Frames 0–2 prepare, frames 3–4 deal damage, frames 5–6 recover.
STRIKES = {
    "cut": Strike(
        (4, 4, 3, 4, 4, 7, 8),
        ((5, 31), (-5, 39), (-12, 45), (15, 36), (18, 27), (15, 24), (8, 27)),
        (-12, 83, 132, 22, -15, -38, -12),
        34,
        16,
        23,
        4,
    ),
    "liftcut": Strike(
        (3, 4, 3, 5, 5, 7, 9),
        ((6, 25), (4, 19), (5, 17), (16, 23), (17, 35), (11, 42), (6, 33)),
        (-36, -65, -72, -12, 39, 81, 38),
        37,
        19,
        25,
        5,
    ),
    "thrust": Strike(
        (5, 5, 5, 5, 6, 10, 12),
        ((6, 33), (0, 34), (-2, 34), (19, 35), (23, 34), (17, 31), (8, 27)),
        (39, 20, 9, 5, 2, -8, -19),
        42,
        30,
        34,
        9,
    ),
    "breaker": Strike(
        (10, 12, 14, 6, 7, 14, 17),
        ((6, 29), (0, 43), (-3, 48), (13, 39), (18, 20), (14, 17), (8, 27)),
        (58, 100, 132, 32, -13, -24, 55),
        43,
        43,
        63,
        6,
    ),
}
