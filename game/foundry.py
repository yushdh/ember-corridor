"""Hand-built rooms and encounter rules for the drowned bell foundry."""
from dataclasses import dataclass
from .combat import Enemy, EnemySpec, Encounter, wall_entry
from .flame import FlameCut
from .gear import COOLDOWN, Loadout
from .terrain import FLOOR, Surface

ENTRY = (75, FLOOR.top)
BELL_SPAWN = (810, FLOOR.top)


def crate_point(room):
    return room.door[0] - 102, room.door[1]


@dataclass(frozen=True)
class Room:
    name: str
    goal: str
    surfaces: tuple
    guards: tuple
    door: tuple
    valve: tuple | None = None


def ledge(name, left, right, top):
    return Surface(name, left, right, top - 10, top, True)


def block(name, left, right, top):
    return Surface(name, left, right, FLOOR.top, top)


ROOMS = (
    Room(
        "退潮门廊",
        "穿过盐栈，清除岸防",
        (FLOOR, ledge("盐栈", 350, 498, 151), block("桥墩", 700, 824, 139)),
        (("hook", 430, 94, (220, 678)), ("hook", 970, 94, (850, 1150))),
        (1194, 94),
    ),
    Room(
        "铆雨泵房",
        "登泵台，逼近铆弩手",
        (
            FLOOR,
            block("西泵台", 340, 530, 147),
            ledge("索桥", 585, 700, 188),
            block("东泵台", 772, 977, 154),
        ),
        (("rivet", 462, 147, (365, 510)), ("rivet", 901, 154, (800, 953))),
        (1194, 94),
    ),
    Room(
        "沉闸水道",
        "穿过低闸，避开冲锋",
        (FLOOR, Surface("泄洪闸", 443, 552, 140, 163), ledge("栈道", 822, 962, 159)),
        (("hook", 328, 94, (158, 422)), ("ram", 879, 94, (608, 1090))),
        (1194, 94),
    ),
    Room(
        "司钟吊廊",
        "登上吊廊，扳动绞盘",
        (
            FLOOR,
            block("压舱座", 370, 530, 146),
            ledge("悬舱", 510, 737, 203),
            ledge("悬梯", 847, 1002, 155),
        ),
        (
            ("hook", 282, 94, (133, 350)),
            ("rivet", 665, 203, (548, 711)),
            ("ram", 1020, 94, (805, 1160)),
        ),
        (1200, 94),
        (705, 203),
    ),
    Room("潮钟熔庭", "击破守钟傀儡，敲响退潮钟", (FLOOR,), (), (1176, 94)),
)


class Bellkeeper(Enemy):
    spec = EnemySpec("守钟人 · 铜潮", 296, 25, 99, 430, 118, 76, 16, 89, 21)

    def __init__(self):
        super().__init__("bell", *BELL_SPAWN, (246, 1098))
        self.phase = 1
        self.move_name = "sweep"
        self.turn = 0
        self.targets = ()

    @property
    def windup(self):
        return (82 if self.move_name == "sweep" else 108) - (18 if self.phase == 2 else 0)

    def zones(self):
        if self.move_name == "vent":
            return [(x - 23, self.y, x + 23, self.y + 112) for x in self.targets]
        reach = self.x + self.facing * (111 if self.phase == 1 else 134)
        return [(min(self.x, reach), self.y, max(self.x, reach), self.y + 29)]

    def pose_index(self):
        if self.state == "dead":
            return min(15, 13 + self.age // 12)
        if self.state == "phase":
            return 12
        if self.state in ("walk", "idle"):
            return (2 if self.state == "walk" else 0) + (self.age // 15) % 2
        start = 4 if self.move_name == "sweep" else 8
        if self.state == "warn":
            return start + int(self.age >= self.windup // 2)
        return start + (2 if self.state == "active" else 3)

    def advance(self, c, w):
        self.age += 1
        if not self.hp:
            return
        if self.phase == 1 and self.hp <= self.spec.hp // 2:
            self.phase = 2
            self.enter("phase")
            c.emit("phase", self.x, self.y)
            return
        if self.state in ("recover", "phase"):
            if self.age >= (80 if self.state == "phase" else 89 if self.phase == 1 else 67):
                self.enter("idle")
            return
        if self.state == "warn":
            if self.age < self.windup:
                return
            self.enter("active")
            c.emit("bell_release", self.x, self.y, move=self.move_name)
        if self.state == "active":
            if not self.spent and any(
                l <= w.x + 10 and w.x - 10 <= r and b <= w.y + w.height and w.y < t
                for l, b, r, t in self.zones()
            ):
                self.spent = True
                c.damage_player(w, self, w.x, w.y + 24)
            if self.age >= 18:
                self.enter("recover")
            return
        dx = w.x - self.x
        if abs(dx) > self.spec.alert:
            return
        self.facing = 1 if dx >= 0 else -1
        self.move_name = "sweep" if self.turn % 2 == 0 else "vent"
        if self.move_name == "sweep" and abs(dx) > 112:
            self.state = "walk"
            self.move(self.facing * (0.91 if self.phase == 2 else 0.71))
            return
        self.turn += 1
        self.targets = (w.x,) if self.phase == 1 else (w.x, w.x + self.facing * 65)
        self.enter("warn")
        c.emit(self.move_name, self.x, self.y, phase=self.phase)


CAST_TICKS = (5, 6, 5, 5, 7, 8)
RELEASE = sum(CAST_TICKS[:2])


class FoundryEncounter(Encounter):
    def __init__(self, room, last=None, *, shell_known=False):
        guards = [Enemy(*config) for config in room.guards] if room.guards else [Bellkeeper()]
        super().__init__(guards, room.surfaces)
        self.room = room
        self.valve_open = room.valve is None
        self.cast_age = -1
        self.flame = FlameCut()
        self.cooldown = 0
        self.wave_length = 0
        self.loadout = last.loadout if last else Loadout(shell_known)
        self.crate_taken = False
        if last:
            self.hp = min(100, last.hp + 18)
            self.weapon = last.weapon
            self.cooldown = last.cooldown

    @property
    def seal_period(self):
        return self.loadout.seal_period

    def melee_damage(self, base):
        return self.loadout.melee_damage(base)

    def incoming_damage(self, base):
        return max(1, base - self.loadout.damage_reduction)

    @property
    def crate(self):
        if self.room.guards and self.cleared and not self.crate_taken:
            return crate_point(self.room)
        return None

    def claim(self, w, item):
        if self.crate is None or not self.hp or not self.near(w, self.crate):
            return False
        self.loadout.fit(item)
        self.cooldown = min(self.cooldown, self.seal_period)
        self.crate_taken = True
        self.emit("fit", w.x, w.y, item=item, rank=self.loadout.rank(item))
        return True

    def step_enemy(self, w, e):
        if isinstance(e, Bellkeeper):
            e.advance(self, w)
        else:
            if e.knockback:
                e.move(e.knockback)
                e.knockback *= 0.78
                if abs(e.knockback) < 0.12:
                    e.knockback = 0.0
            super().step_enemy(w, e)

    def pulse(self, w):
        origin = (w.x, w.y + 32)
        self.wave_origin = origin
        self.wave_facing = w.facing
        reach = 142
        self.wave_length = round(
            reach * min(1, wall_entry(origin, (w.x + w.facing * reach, origin[1]), self.surfaces))
        )
        l, r = sorted((w.x, w.x + w.facing * self.wave_length))
        self.emit("seal", w.x, w.y + 32, facing=w.facing)
        for target_index, e in enumerate(self.foes):
            a, b, z, t = e.rect
            if not e.hp or z < l or a > r or t < origin[1] - 15 or b > origin[1] + 15:
                continue
            target = (max(a, min(z, w.x)), max(b, min(t, origin[1])))
            if wall_entry(origin, target, self.surfaces) <= 1:
                continue
            e.hp = max(0, e.hp - 32)
            if not e.hp:
                e.enter("dead")
            elif e.kind != "bell":
                e.enter("hurt")
            self.emit(
                "hit",
                *target,
                enemy=e.kind,
                target=target_index,
                action="seal",
                hp=e.hp,
                facing=w.facing
            )
        self.bolts[:] = [
            b for b in self.bolts if not (l <= b.x <= r and abs(b.y - origin[1]) <= 15)
        ]

    def step(self, w, axis, *, skill=False, flame_press=False, flame_hold=False, **moves):
        if self.hp and not self.freeze:
            self.flame.update(self, w, axis, flame_press, flame_hold)
            self.cooldown = max(0, self.cooldown - 1)
            if self.cast_age >= 0:
                self.cast_age += 1
                if self.cast_age >= sum(CAST_TICKS):
                    self.cast_age = -1
            elif skill and not (
                self.flame.busy or self.cooldown or self.hurt or self.attack or w.tucked
            ):
                if axis:
                    w.facing = 1 if axis > 0 else -1
                self.cast_age, self.cooldown = 0, self.seal_period
                self.buffer = 0
            if self.cast_age == RELEASE:
                self.pulse(w)
        if self.cast_age >= 0 or self.flame.busy:
            axis = 0
            moves.update(attack=False, jump=False, roll=False, slot=None, drop=False)
        super().step(w, axis, **moves)
        if self.hurt or not self.hp:
            self.cast_age = -1
            self.flame.reset()

    def near(self, w, point):
        return abs(w.x - point[0]) <= 42 and abs(w.y - point[1]) <= 24

    def interact(self, w):
        if not self.hp or self.hurt or self.cast_age >= 0 or self.attack or self.flame.busy:
            return
        if self.crate and self.near(w, self.crate):
            return "crate"
        if not self.valve_open and self.near(w, self.room.valve):
            self.valve_open = True
            self.emit("gate", w.x, w.y)
            return "valve"
        if self.cleared and self.valve_open and self.near(w, self.room.door):
            return "exit"
