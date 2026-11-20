"""Deterministic combat. Collision, actions and damage use the movement clock."""
from collections import deque
from dataclasses import dataclass
from math import hypot

from .attacks import STRIKES
from .terrain import SURFACES, GROUND_Y

MAX_HP = 100
LIGHT_CHAIN = ("cut", "liftcut", "thrust")
BUFFER = 22
HITSTOP = {"light": 4, "heavy": 9, "hurt": 5}
FORK_HEIGHT = 9
FORK_REACH = 60
MELEE_SEGMENTS = {"hook": (46, 29), "ram": (29, 25), "fork": (FORK_REACH, FORK_HEIGHT)}


@dataclass(frozen=True)
class EnemySpec:
    title: str
    hp: int
    half_width: int
    height: int
    alert: int
    trigger: int
    windup: int
    active: int
    recovery: int
    damage: int


TYPES = {
    "hook": EnemySpec("捞渣钩手", 62, 12, 49, 155, 41, 43, 13, 49, 13),
    "rivet": EnemySpec("盐雾铆弩手", 48, 11, 46, 210, 210, 77, 10, 105, 12),
    "ram": EnemySpec("炉门重卫", 98, 19, 59, 182, 131, 65, 46, 80, 23),
    "fork": EnemySpec("探潮叉手", 56, 12, 46, 155, 58, 70, 14, 86, 16),
}


@dataclass
class Enemy:
    kind: str
    x: float
    y: float
    patrol: tuple
    facing: int = -1
    state: str = "idle"
    age: int = 0
    spent: bool = False
    aim: tuple = (-1.0, 0.0)
    knockback: float = 0.0
    pending_push: float = 0.0

    def __post_init__(self):
        self.hp = self.spec.hp

    @property
    def spec(self):
        return TYPES[self.kind]

    def enter(self, state):
        self.state, self.age = state, 0
        self.spent = False

    def move(self, dx):
        self.x = max(self.patrol[0], min(self.patrol[1], self.x + dx))

    @property
    def rect(self):
        return (
            self.x - self.spec.half_width,
            self.y,
            self.x + self.spec.half_width,
            self.y + self.spec.height,
        )


def segment_entry(a, b, rect):
    """Parameter of the first intersection of segment ab and an axis-aligned box."""
    t0, t1 = 0.0, 1.0
    for p, q, lo, hi in zip(a, b, rect[:2], rect[2:]):
        delta = q - p
        if abs(delta) < 1e-9:
            if p < lo or p > hi:
                return None
            continue
        first, last = sorted(((lo - p) / delta, (hi - p) / delta))
        t0, t1 = max(t0, first), min(t1, last)
        if t0 > t1:
            return None
    return t0


def wall_entry(a, b, surfaces=SURFACES):
    first = 2.0
    for s in surfaces:
        if not s.one_way:
            t = segment_entry(a, b, (s.left, s.bottom, s.right, s.top))
            if t is not None:
                first = min(first, t)
    return first


@dataclass
class Bolt:
    x: float
    y: float
    dx: float
    dy: float
    life: int = 180
    owner: Enemy | None = None


class Encounter:
    def __init__(self, foes=None, surfaces=SURFACES):
        self.surfaces = surfaces
        self.foes = (
            foes
            if foes is not None
            else [
                Enemy("hook", 452, GROUND_Y, (260, 519)),
                Enemy("rivet", 588, 141, (550, 640)),
                Enemy("ram", 956, GROUND_Y, (828, 1007)),
            ]
        )
        self.hp = MAX_HP
        self.weapon = "light"
        self.attack = None
        self.age = 0
        self.serial = 0
        self.victims = set()
        self.buffer = 0
        self.hurt = 0
        self.immune = 0
        self.freeze = 0
        self.death_age = 0
        self.bolts = []
        self.tick = 0
        self.events = deque(maxlen=256)
        self.sequence = 0

    def emit(self, kind, x, y, **detail):
        self.sequence += 1
        self.events.append(
            dict(
                id=self.sequence, tick=self.tick, kind=kind, x=round(x, 2), y=round(y, 2), **detail
            )
        )

    @property
    def cleared(self):
        return all(e.hp == 0 for e in self.foes)

    def interrupt(self):
        self.attack = None
        self.buffer = 0
        self.victims.clear()

    def pause(self):
        self.buffer = 0
        self.immune = 0

    def start_attack(self, w, name):
        self.attack, self.age = name, 0
        self.serial += 1
        self.victims.clear()
        self.buffer = 0
        self.emit("windup", w.x, w.y + 32, action=name, attack_id=self.serial)

    def player_strike(self, w):
        name = self.attack
        rule = STRIKES[name]
        frame = rule.frame(self.age)
        if not rule.active(frame):
            return
        if self.age == sum(rule.ticks[:3]):
            w.move_x(w.facing * rule.advance, self.surfaces)
            self.emit("swing", w.x, w.y + 30, action=name, attack_id=self.serial)
        grip, tip = rule.blade(frame)
        a = (w.x + grip[0] * w.facing, w.y + grip[1])
        b = (w.x + tip[0] * w.facing, w.y + tip[1])
        if wall_entry((w.x, w.y + 30), a, self.surfaces) <= 1:
            return
        solid = wall_entry(a, b, self.surfaces)
        for target_index, e in enumerate(self.foes):
            if e.hp <= 0 or id(e) in self.victims:
                continue
            l, bot, r, top = e.rect
            margin = 2 if name == "breaker" else 3
            contact = segment_entry(a, b, (l - margin, bot - margin, r + margin, top + margin))
            if name == "breaker":
                # The wide contact belongs to the forged head, not the wooden haft.
                head = (a[0] + 0.73 * (b[0] - a[0]), a[1] + 0.73 * (b[1] - a[1]))
                head_t = segment_entry(head, b, (l - 8, bot - 8, r + 8, top + 8))
                if head_t is not None:
                    contact = min(contact if contact is not None else 2, 0.73 + 0.27 * head_t)
            if contact is None or contact >= solid:
                continue
            self.victims.add(id(e))
            e.hp = max(0, e.hp - self.melee_damage(rule.damage))
            # Heavy armor resists a light stagger during the committed charge.
            if not e.hp:
                e.enter("dead")
            elif e.kind != "bell" and (
                e.kind != "ram" or e.state not in ("warn", "active") or name == "breaker"
            ):
                e.enter("hurt")
            # The segment includes weapon thickness. Place the impact at the target
            # surface rather than on the expanded collision envelope beside it.
            x = min(r, max(l, a[0] + contact * (b[0] - a[0])))
            y = min(top, max(bot, a[1] + contact * (b[1] - a[1])))
            self.emit(
                "hit",
                x,
                y,
                enemy=e.kind,
                target=target_index,
                action=name,
                attack_id=self.serial,
                hp=e.hp,
                frame=frame,
                facing=w.facing,
            )
            if e.state in ("hurt", "dead"):
                e.pending_push = w.facing * (10 if name == "breaker" else 3)
            self.freeze = HITSTOP[self.weapon]

    def melee_damage(self, base):
        return base

    def incoming_damage(self, base):
        return base

    def damage_player(self, w, e, x, y):
        if self.hp <= 0:
            return
        if w.invulnerable or self.immune:
            self.emit("evade" if w.invulnerable else "guarded", x, y, enemy=e.kind)
            return
        self.hp = max(0, self.hp - self.incoming_damage(e.spec.damage))
        self.interrupt()
        w.clear_transients(self.surfaces)
        self.hurt = 23 if self.hp else 0
        self.immune = 66 if self.hp else 0
        self.freeze = HITSTOP["hurt"]
        self.emit("hurt" if self.hp else "death", x, y, enemy=e.kind, hp=self.hp)
        if not self.hp:
            self.bolts.clear()

    def step_enemy(self, w, e):
        s = e.spec
        dx = w.x - e.x
        height_delta = abs((w.y + w.height / 2) - (e.y + s.height / 2))
        e.age += 1
        if e.state == "dead":
            return
        if e.state == "hurt":
            if e.age >= 24:
                e.enter("recover")
            return
        if e.state == "recover":
            if e.age >= s.recovery:
                e.enter("idle")
            return
        if e.state == "warn" and e.age >= s.windup:
            e.enter("active")
            if e.kind == "rivet":
                self.bolts.append(
                    Bolt(e.x + e.facing * 21, e.y + 30, e.aim[0] * 2.6, e.aim[1] * 2.6, owner=e)
                )
                self.emit("shot", e.x, e.y + 30, enemy=e.kind)
        if e.state == "active":
            if e.age >= s.active:
                e.enter("recover")
                return
            if e.kind == "rivet":
                return
            if e.kind == "ram":
                e.move(e.facing * 2.35)
            reach, height = MELEE_SEGMENTS[e.kind]
            a = (e.x, e.y + height)
            b = (e.x + e.facing * reach, a[1])
            t = segment_entry(a, b, (w.x - 11, w.y, w.x + 11, w.y + w.height))
            if not e.spent and t is not None and t < wall_entry(a, b, self.surfaces):
                e.spent = True
                self.damage_player(w, e, a[0] + t * (b[0] - a[0]), a[1])
            return
        if (
            e.state == "warn"
            or abs(dx) > s.alert
            or height_delta > (145 if e.kind == "rivet" else 45)
        ):
            if e.state == "walk":
                e.enter("idle")
            return
        e.facing = 1 if dx >= 0 else -1
        if abs(dx) > s.trigger:
            e.move(e.facing * (0.76 if e.kind == "hook" else 0.43))
            e.state = "walk"
            return
        muzzle = (e.x + e.facing * 21, e.y + 30)
        target = (w.x, w.y + w.height * 0.55)
        if wall_entry(muzzle, target, self.surfaces) <= 1:
            return
        aimx, aimy = target[0] - muzzle[0], target[1] - muzzle[1]
        length = hypot(aimx, aimy) or 1
        e.aim = (aimx / length, aimy / length)
        e.enter("warn")
        self.emit("warn", e.x, e.y + s.height, enemy=e.kind)

    def step_bolts(self, w):
        for bolt in self.bolts[:]:
            a = (bolt.x, bolt.y)
            b = (bolt.x + bolt.dx, bolt.y + bolt.dy)
            solid = wall_entry(a, b, self.surfaces)
            t = segment_entry(a, b, (w.x - 12, w.y - 1, w.x + 12, w.y + w.height + 1))
            bolt.life -= 1
            if t is not None and t < solid:
                self.bolts.remove(bolt)
                self.damage_player(w, bolt.owner or self.foes[1], w.x, b[1])
                if not self.hp:
                    break
            elif solid <= 1 or bolt.life <= 0:
                self.bolts.remove(bolt)
            else:
                bolt.x, bolt.y = b

    def step(
        self, w, axis, *, jump=False, held=False, drop=False, roll=False, attack=False, slot=None
    ):
        self.tick += 1
        if not self.hp:
            self.death_age += 1
            w.step(0, surfaces=self.surfaces)
            return
        if attack:
            self.buffer = BUFFER
        if self.freeze:
            self.freeze -= 1
            return
        # Hold the victim at the contact point until both combatants resume.
        for enemy in self.foes:
            if enemy.pending_push:
                enemy.move(enemy.pending_push)
                enemy.pending_push = 0
        self.immune = max(0, self.immune - 1)
        self.hurt = max(0, self.hurt - 1)
        if self.attack:
            rule = STRIKES[self.attack]
            self.age += 1
            if self.age >= rule.cancel_tick:
                if roll and w.support and not w.recharge:
                    self.interrupt()
                elif self.buffer and self.attack in LIGHT_CHAIN[:2]:
                    self.start_attack(w, LIGHT_CHAIN[LIGHT_CHAIN.index(self.attack) + 1])
            if self.attack and self.age >= STRIKES[self.attack].duration:
                self.attack = None
        if not self.attack and not self.hurt and not w.tucked and w.roll_age < 0:
            if slot:
                self.weapon = slot
            if self.buffer and not roll:
                if axis:
                    w.facing = axis
                self.start_attack(w, "cut" if self.weapon == "light" else "breaker")
        locked = bool(self.attack or self.hurt)
        w.step(
            0 if locked else axis,
            surfaces=self.surfaces,
            jump=jump and not locked,
            held=held,
            drop=drop,
            roll=roll and not locked,
        )
        self.buffer = max(0, self.buffer - 1)
        if self.attack:
            self.player_strike(w)
        for e in self.foes:
            if self.hp:
                self.step_enemy(w, e)
        if self.hp:
            self.step_bolts(w)
