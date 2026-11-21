"""Seeded tide-line routes and movement certificates for their hand-built rooms."""
from dataclasses import dataclass, replace
from functools import lru_cache
from random import Random

from .foundry import BELL_SPAWN, ENTRY, ROOMS, Room, block, crate_point, ledge
from .motion import BODY_HALF_WIDTH, STAND_HEIGHT, TUCK_HEIGHT, Walker
from .terrain import FLOOR, Surface, WORLD_WIDTH

VERSION = 3
ATTEMPTS = 4


@dataclass(frozen=True)
class Template:
    key: str
    theme: int
    room: Room
    label: str
    steps: tuple = ()  # Intermediate landings used to reach the next raised objective.


CLASSIC = tuple(
    Template(key, i, room, label, ((479, 146),) if i == 3 else ())
    for i, (key, room, label) in enumerate(
        zip(
            ("gate", "pump", "sluice", "gallery", "bell"),
            ROOMS,
            ("盐栈", "东西泵台", "泄洪闸", "悬舱绞盘", "退潮大钟"),
        )
    )
)
ALTERNATES = (
    Template(
        "pump-steps",
        1,
        replace(
            ROOMS[1],
            surfaces=(
                FLOOR,
                ledge("引水板", 188, 308, 139),
                block("短泵座", 408, 566, 158),
                ledge("检修桥", 554, 735, 201),
                block("东基座", 851, 1000, 136),
            ),
            guards=(("rivet", 648, 201, (589, 701)), ("rivet", 931, 136, (875, 973))),
        ),
        "高架检修桥",
        ((511, 158),),
    ),
    Template(
        "sluice-twins",
        2,
        replace(
            ROOMS[2],
            surfaces=(
                FLOOR,
                Surface("泄洪闸", 386, 460, 140, 163),
                ledge("中继栈", 518, 654, 147),
                Surface("泄洪闸", 720, 809, 141, 166),
            ),
            guards=(("fork", 267, 94, (155, 357)), ("ram", 977, 94, (831, 1140))),
        ),
        "双闸涵洞",
    ),
    Template(
        "gallery-west",
        3,
        replace(
            ROOMS[3],
            surfaces=(
                FLOOR,
                block("西阶座", 229, 401, 143),
                ledge("绞盘吊台", 378, 584, 197),
                ledge("横渡板", 649, 807, 162),
                block("东压舱座", 899, 1041, 145),
            ),
            guards=(
                ("chain", 145, 94, (105, 205)),
                ("rivet", 493, 197, (420, 551)),
                ("ram", 966, 145, (928, 1015)),
            ),
            valve=(543, 197),
        ),
        "西侧绞盘",
        ((340, 143),),
    ),
)


def objectives(template):
    room = template.room
    points = [(x, y) for _, x, y, _ in room.guards] or [BELL_SPAWN]
    points.extend(template.steps)
    if room.valve:
        points.append(room.valve)
    if room.guards:
        points.append(crate_point(room))
    return (*sorted(points), room.door)


def supported(room, x, y):
    return (
        BODY_HALF_WIDTH <= x <= WORLD_WIDTH - BODY_HALF_WIDTH
        and any(s.left <= x < s.right and s.top == y for s in room.surfaces)
        and not any(
            not s.one_way
            and x + BODY_HALF_WIDTH > s.left
            and x - BODY_HALF_WIDTH < s.right
            and y < s.top
            and y + STAND_HEIGHT > s.bottom
            for s in room.surfaces
        )
    )


@lru_cache(maxsize=64)
def walk_template(template):
    """Advance one continuous Walker from spawn to the exit using normal inputs."""
    room = template.room
    points = objectives(template)
    if not all(supported(room, x, y) for x, y in (ENTRY, *points)):
        return False
    for _, spawn, y, (left, right) in room.guards:
        if not left <= spawn <= right or not all(
            supported(room, x, y) for x in range(left, right + 1)
        ):
            return False
    w = Walker(x=ENTRY[0], y=ENTRY[1])
    for tx, ty in points:
        for _ in range(1400):
            if abs(w.x - tx) <= 5 and w.support and w.y == ty:
                break
            axis = 1 if tx > w.x + 2 else -1 if tx < w.x - 2 else 0
            jump = roll = drop = False
            if w.support:
                for s in room.surfaces:
                    gap = (
                        s.left - w.x - BODY_HALF_WIDTH
                        if axis > 0
                        else w.x - BODY_HALF_WIDTH - s.right
                    )
                    if not s.one_way and s.top > w.y and -1 <= gap <= 30 and axis:
                        clearance = s.bottom - w.y
                        if TUCK_HEIGHT <= clearance < STAND_HEIGHT and ty < s.top:
                            roll = not w.recharge
                        elif clearance < STAND_HEIGHT:
                            jump = True
                    if s.one_way and ty == s.top and w.y < ty and s.left - 18 < w.x < s.right + 18:
                        jump = True
                drop = w.support.one_way and w.y > ty and w.support.left <= tx < w.support.right
            w.step(axis, jump=jump or drop, held=True, drop=drop, roll=roll, surfaces=room.surfaces)
        else:
            return False
    return True


@dataclass(frozen=True)
class TideRoute:
    seed: int | None
    rooms: tuple
    attempts: int
    fallback: bool = False

    def record(self):
        return dict(
            version=VERSION,
            seed=self.seed,
            attempts=self.attempts,
            fallback=self.fallback,
            templates=[t.key for t in self.rooms],
        )


def connected(rooms):
    # Gates advance exactly one room. The entrance and final bell bookend all three workshops.
    return (
        len(rooms) == 5
        and rooms[0] == CLASSIC[0]
        and rooms[-1] == CLASSIC[-1]
        and {t.theme for t in rooms[1:-1]} == {1, 2, 3}
        and all(walk_template(t) for t in rooms)
    )


def candidate(rng):
    middle = [
        rng.choice((original, alternate)) for original, alternate in zip(CLASSIC[1:-1], ALTERNATES)
    ]
    rng.shuffle(middle)
    return (CLASSIC[0], *middle, CLASSIC[-1])


def generate(seed):
    if seed is not None:
        if not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("种子范围为 0 到 4294967295")
        rng = Random(seed)
        for attempt in range(1, ATTEMPTS + 1):
            rooms = candidate(rng)
            if connected(rooms):
                return TideRoute(seed, rooms, attempt)
    if not connected(CLASSIC):
        raise RuntimeError("手工备用路线未通过行者移动检查")
    return TideRoute(seed, CLASSIC, ATTEMPTS if seed is not None else 0, seed is not None)
