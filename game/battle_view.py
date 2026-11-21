"""Preloaded combat presentation. Input and hit stop never block the window."""
from dataclasses import dataclass, replace
import math
import random

import arcade
from PIL import Image, ImageDraw

from .attacks import STRIKES
from .combat import FORK_HEIGHT, FORK_REACH, MAX_HP, TYPES, wall_entry
from .resources import ASSETS, load_clips
from .ui import blit, panel, tag, label, draw_stamina, GOLD, PALE, FOAM


def position(sprite, frame, x, y, facing, scroll, lift):
    sprite.texture = frame.right if facing > 0 else frame.left
    ax, ay = frame.anchor
    sprite.position = (
        round(x) - scroll + facing * (sprite.texture.width // 2 - ax),
        round(y) - lift + ay - sprite.texture.height // 2,
    )


def effect_texture(kind, sector=0):
    if kind == "burst":
        im = Image.new("RGBA", (36, 32))
        d = ImageDraw.Draw(im)
        d.ellipse((11, 10, 24, 22), fill=(255, 170, 76, 56))
        d.polygon(
            [
                (5, 17),
                (13, 13),
                (11, 4),
                (18, 12),
                (24, 6),
                (23, 13),
                (31, 12),
                (23, 18),
                (27, 25),
                (20, 22),
                (18, 24),
                (15, 21),
                (7, 25),
                (12, 18),
            ],
            fill=(255, 224, 151, 220),
        )
        d.polygon(
            [(10, 17), (16, 14), (17, 9), (20, 15), (26, 15), (20, 18), (17, 23), (16, 18)],
            fill="#fff4cb",
        )
        return arcade.Texture(im)
    im = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(im)
    if kind == "spark":
        angle = sector * math.tau / 12

        def xy(u, v):
            return (
                round(8 + u * math.cos(angle) - v * math.sin(angle)),
                round(8 - u * math.sin(angle) - v * math.cos(angle)),
            )

        d.polygon([xy(-6, 0), xy(1, 1), xy(6, 0), xy(1, -1)], fill="#cd8452")
        d.line([xy(1, 0), xy(5, 0)], fill="#ffe3a4")
    elif kind == "chip":
        d.polygon([(5, 9), (7, 5), (11, 6), (9, 10)], fill="#686d75", outline="#29313f")
        d.line((7, 6, 9, 6), fill="#d6ae7e")
    elif kind == "mist":
        d.polygon([(1, 10), (4, 7), (7, 7), (9, 5), (12, 7), (14, 10), (7, 11)], fill="#a8bcaf")
    else:
        d.polygon([(0, 8), (7, 5), (15, 8), (8, 11)], fill="#91e0dc", outline="#344f5a")
        d.line((6, 8, 13, 8), fill="#e9fff2")
    return arcade.Texture(im)


@dataclass
class Particle:
    sprite: arcade.Sprite
    x: float
    y: float
    vx: float
    vy: float
    life: int
    maximum: int
    opacity: int
    animation: tuple = ()


def contact_frames(heavy):
    """A shearing nick opens into splinters; the hammer flattens a wider copper rim."""
    frames = []
    for phase in range(3):
        im = Image.new("RGBA", (48, 36))
        d = ImageDraw.Draw(im)
        x, y = 24, 18
        if heavy:
            # A flattened rim breaks along the forward face of the hammer.
            front = (5, 12, 18)[phase]
            height = (8, 13, 15)[phase]
            rim = [(x + front - 6, y - height), (x + front, y - height + 4),
                   (x + front + 2, y - 1), (x + front, y + 5),
                   (x + front - 5, y + height)]
            d.line(rim, fill=("#fff0bc", "#dfaa78", "#9d795f")[phase], width=2)
            d.line(rim[1:3], fill=("#e3f4dc", "#badcd2", "#8eaca7")[phase])
        for dx, dy in ((18, -7), (12, 8), (-7, -10)) if heavy else ((13, -13), (18, -3), (-7, 7)):
            size = (0.55, 0.86, 1.0)[phase]
            bx, by = x + round(dx * phase * 0.25), y + round(dy * phase * 0.25)
            d.polygon(
                [
                    (bx - 2, by + 1),
                    (bx, by - 2),
                    (x + round(dx * size), y + round(dy * size)),
                    (bx + 2, by + 2),
                ],
                fill=("#fff0b9", "#ffca80", "#d7915e")[phase],
            )
        if phase == 0:
            d.polygon(
                [
                    (x - 6, y),
                    (x - 1, y - 2),
                    (x, y - 8),
                    (x + 2, y - 1),
                    (x + 8, y),
                    (x + 1, y + 2),
                    (x - 1, y + 6),
                ],
                fill="#fff5d1",
            )
        frames.append(arcade.Texture(im))
    return {1: tuple(frames), -1: tuple(f.flip_left_right() for f in frames)}


def warning_marks(kind):
    ink = "#192530"
    edge = {"hook": "#edb079", "rivet": "#8fd9cd", "ram": "#f2aa76", "fork": "#b6e0ad"}[kind]
    icon = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(icon)
    d.polygon([(4, 0), (11, 0), (15, 4), (15, 9), (8, 15), (0, 10), (0, 4)], fill=ink, outline=edge)
    if kind == "hook":
        d.line((5, 7, 5, 9, 8, 10, 11, 7, 11, 3), fill=edge, width=2)
    elif kind == "fork":
        d.line((3, 9, 7, 9, 11, 5), fill=edge, width=2)
        d.line((7, 9, 12, 9), fill=edge, width=2)
    elif kind == "rivet":
        d.rectangle((5, 3, 10, 8), outline=edge)
        d.line((2, 6, 5, 6), fill=edge)
        d.line((10, 6, 13, 6), fill=edge)
        d.point((7, 6), fill="#fff1d1")
    else:
        for y in (3, 7):
            d.line((4, y, 8, y + 3, 12, y), fill=edge, width=2)
    dash = Image.new("RGBA", (10, 8))
    d = ImageDraw.Draw(dash)
    if kind == "ram":
        pts = [(1, 1), (5, 1), (9, 4), (5, 7), (1, 7), (5, 4)]
        d.polygon(pts, fill=edge, outline=ink)
    else:
        d.rectangle((1, 2, 7, 5), fill=ink)
        d.rectangle((2, 3, 6, 4 if kind == "hook" else 3), fill=edge)
    tex = arcade.Texture(dash)
    ready = icon.copy()
    accent = ImageDraw.Draw(ready)
    for x in (1, 11):
        accent.rectangle((x, 11, x + 3, 14), fill=ink)
        accent.line((x + 1, 12, x + 2, 13), fill="#ffefc3", width=2)
    return (arcade.Texture(icon), arcade.Texture(ready)), tex, tex.flip_left_right()


class BattleView:
    def __init__(self, movement, foes):
        self.clips = load_clips("combat")
        self.movement = movement
        self.levels = [2, 2, 2, 2]  # shake, flashes, volume, particles; 0..3
        self.flashes = {}
        for kind in TYPES:
            self.prepare_flash(kind)
        self.contacts = {heavy: contact_frames(heavy) for heavy in (False, True)}
        self.enemies = arcade.SpriteList()
        self.marks = {kind: warning_marks(kind) for kind in TYPES}
        self.warning_list = arcade.SpriteList()
        self.warning_count = 0
        self.warning_badges = []
        for enemy in foes:
            self.enemies.append(arcade.Sprite(self.clips[enemy.kind].frames[0].right))
        self.trail = arcade.Sprite(self.clips["trail_cut"].frames[3].right)
        self.trails = arcade.SpriteList()
        self.trails.append(self.trail)
        self.projectiles = arcade.SpriteList()
        self.particle_list = arcade.SpriteList()
        self.particles = []
        self.effects = {k: effect_texture(k) for k in ("chip", "mist", "bolt", "burst")}
        self.sparks = [effect_texture("spark", i) for i in range(12)]
        self.rng = random.Random(19)
        self.weapon_names = {"light": "余烬短刃", "heavy": "潮砧重锤"}
        self.plates = {k: panel((184, 48), [(40, 0, "耐力", 11, PALE),
                                             (40, 24, "生命", 11, FOAM)], style="hud",
                                fill="#12212de6", emblem=k) for k in self.weapon_names}
        self.tags = {k: tag(spec.title, 108) for k, spec in TYPES.items()}
        self.status_weapon = None
        self.weapon_until = 0
        self.echo_hp = MAX_HP
        self.previous_hp = MAX_HP
        self.hp_delay = 0
        self.notices = {"dead": tag("炉火熄灭    R  重新交锋", 171, GOLD),
                        "clear": tag("岸线已清理    R  重新交锋", 180)}
        self.sounds = {
            p.stem: arcade.load_sound(p) for p in sorted((ASSETS / "combat/audio").glob("*.wav"))
        }
        priorities = {**dict.fromkeys(("hit", "crush", "fire_hit", "hurt"), 1), "ignite": 2,
                      **dict.fromkeys((*TYPES, "sweep", "vent", "phase"), 3)}
        self.voice_priority = {sound: priorities.get(name, 0) for name, sound in self.sounds.items()}
        self.players = []
        self.last_event = 0
        self.shake = 0
        self.shake_size = 0
        self.fire_impacts = {}
        self.last_impact = None
        self.kick_direction = 1
        self.flash = {}
        self.focus = None

    def prepare_flash(self, kind):
        variants = []
        for strength in (42, 132):
            frames = []
            for frame in self.clips[kind].frames:
                base = frame.right.image.convert("RGBA")
                # Edge highlights take the heat; keep the deeper folds of armour visible.
                mask = base.convert("L").point(lambda v: round(strength * min(1, max(0, (v - 48) / 108)) ** 1.35))
                lit = Image.composite(Image.new("RGBA", base.size, (255, 217, 155)), base, mask)
                lit.putalpha(base.getchannel("A"))
                tex = arcade.Texture(lit)
                frames.append(replace(frame, right=tex, left=tex.flip_left_right()))
            variants.append(frames)
        self.flashes[kind] = variants

    def reset(self):
        for sound, player in self.players:
            sound.stop(player)
        self.players.clear()
        self.particles.clear()
        self.particle_list.clear()
        self.projectiles.clear()
        self.weapon_until = 0
        self.last_event = self.shake = 0
        self.last_impact = None
        self.flash.clear()
        self.focus = None

    def sound(self, name):
        self.players = [(s, p) for s, p in self.players if s.is_playing(p)]
        if not self.levels[2]:
            return
        cue = self.sounds[name]
        if len(self.players) >= 6:
            lowest = min(self.players, key=lambda voice: self.voice_priority[voice[0]])
            if self.voice_priority[cue] <= self.voice_priority[lowest[0]]:
                return
            lowest[0].stop(lowest[1])
            self.players.remove(lowest)
        gain = {"sabre": 0.75, "maul": 0.85, "land": 0.66, "roll": 0.75, "crush": 1.12}.get(
            name, 1
        )
        self.players.append((cue, cue.play(volume=0.155 * self.levels[2] * gain)))

    def particle(self, tex, x, y, vx, vy, life, alpha=255, animation=()):
        if len(self.particles) >= 16 * self.levels[3]:
            return
        sprite = arcade.Sprite(tex)
        self.particle_list.append(sprite)
        self.particles.append(Particle(sprite, x, y, vx, vy, life, life, alpha, animation))

    def tick(self, c, w, old_action):
        if self.status_weapon != c.weapon:
            self.weapon_until = c.tick + 195 if self.status_weapon is not None else 0
            self.status_weapon = c.weapon
        if self.previous_hp != c.hp:
            self.echo_hp = self.previous_hp
            self.previous_hp = c.hp
            self.hp_delay = 28
        if self.hp_delay:
            self.hp_delay -= 1
        else:
            self.echo_hp += min(0.45, max(-0.45, c.hp - self.echo_hp))
        self.shake = max(0, self.shake - 1)
        self.flash = {k: n - 1 for k, n in self.flash.items() if n > 1}
        for p in self.particles[:]:
            p.life -= 1
            if p.life <= 0:
                p.sprite.remove_from_sprite_lists()
                self.particles.remove(p)
            else:
                if p.animation:
                    p.sprite.texture = p.animation[
                        (p.maximum - p.life) * len(p.animation) // p.maximum
                    ]
                p.x += p.vx
                p.y += p.vy
                if p.vx:
                    p.vy -= 0.025
        fresh = []
        for ev in reversed(c.events):
            if ev["id"] <= self.last_event:
                break
            fresh.append(ev)
        for ev in reversed(fresh):
            self.event(ev)
        self.last_event = c.sequence
        if w.action != old_action and w.action in ("land", "roll") and c.hp:
            self.sound(w.action)
            for j in range(4):
                self.particle(
                    self.effects["mist"],
                    w.x,
                    w.y + 1,
                    self.rng.uniform(-0.7, 0.7),
                    0.2,
                    11 + j,
                    140,
                )
        if (
            w.action == "roll"
            and not c.freeze
            and (w.roll_age == 8 or (self.levels[3] == 3 and w.roll_age == 24))
        ):
            clip = self.clips["hammer_roll"] if c.weapon == "heavy" else self.movement["roll"]
            f = clip.frame(w.age)
            tex = f.right if w.facing > 0 else f.left
            self.particle(
                tex,
                w.x,
                w.y + f.anchor[1] - tex.height // 2,
                0,
                0,
                6,
                63 if w.roll_age == 8 else 31,
            )

    def event(self, ev):
        k = ev["kind"]
        if k in ("seal", "sweep", "vent", "phase", "gate", "ignite", "firecut"):
            self.sound(k)
        elif k == "warn":
            self.sound(ev["enemy"])
        elif k == "shot":
            self.sound("shot")
        elif k == "swing":
            self.sound("maul" if ev["action"] == "breaker" else "sabre")
        elif k in ("hit", "hurt", "death", "evade"):
            fire = ev.get("action") == "firecut"
            heavy = fire or ev.get("action") == "breaker"
            facing = ev.get("facing", 1)
            if k != "evade":
                if k == "hit":
                    instance = (ev["action"], ev.get("attack_id", ev["tick"]))
                    if instance != self.last_impact:
                        self.sound("fire_hit" if fire else "crush" if heavy else "hit")
                        self.last_impact = instance
                else:
                    self.sound("hurt")
                self.shake, self.shake_size = (18, 4) if fire else (16, 3) if heavy else (11, 1)
                self.kick_direction = facing
                if k == "hit":
                    self.flash[ev["target"]] = 3 * self.levels[1]
                if fire and self.levels[1] and facing in self.fire_impacts:
                    frames = self.fire_impacts[facing]
                    self.particle(
                        frames[0],
                        ev["x"] + 8 * facing,
                        ev["y"] + 2,
                        0,
                        0,
                        12,
                        140 + 36 * self.levels[1],
                        frames,
                    )
                elif k == "hit" and self.levels[1]:
                    frames = self.contacts[heavy][facing]
                    self.particle(frames[0], ev["x"], ev["y"], 0, 0, 9, 235, frames)
                elif self.levels[1]:
                    self.particle(
                        self.effects["burst"], ev["x"], ev["y"], 0, 0, 5 + self.levels[1], 210
                    )
            for i in range((3 if heavy else 2) * self.levels[3]):
                chip = heavy and i % 3 == 2
                angle = self.rng.uniform(0.35, 1.36) if chip else self.rng.uniform(-0.32, 0.77)
                if i % 5 == 4 and ev.get("action") != "thrust":
                    angle = math.pi - angle
                elif not chip:
                    angle += {"liftcut": 0.55, "breaker": -0.42, "thrust": -0.14}.get(
                        ev.get("action"), 0
                    )
                speed = self.rng.uniform(0.45, 1.05) if chip else self.rng.uniform(1.25, 2.55)
                vx, vy = facing * speed * math.cos(angle), speed * math.sin(angle)
                sector = round(math.atan2(vy, vx) * 12 / math.tau) % 12
                self.particle(
                    self.effects["chip"] if chip else self.sparks[sector],
                    ev["x"],
                    ev["y"],
                    vx,
                    vy,
                    10 if chip else 5 + i % 4,
                )

    def offset(self):
        if not self.shake or not self.levels[0]:
            return 0, 0
        duration = {4: 18, 3: 16}.get(self.shake_size, 11)
        age = duration - self.shake
        size = self.shake_size * self.levels[0] / 2 * (self.shake / duration) ** 1.4
        return (
            round(-self.kick_direction * size * math.cos(age * 0.75)),
            round(size * 0.46 * math.sin(age * 0.7)),
        )

    def actor_frame(self, c, w):
        if not c.hp:
            return self.clips["death"].frame(c.death_age / 120)
        if c.hurt:
            return self.clips["hurt"].frame((23 - c.hurt) / 120)
        if c.attack:
            return self.clips[c.attack].frames[STRIKES[c.attack].frame(c.age)]
        if c.weapon == "heavy":
            if w.action == "tuck":
                return self.clips["hammer_roll"].frames[0]
            return self.clips["hammer_" + w.action].frame(w.age)
        return None

    def sync(self, c, w, scroll, lift):
        self.trail.visible = False
        if c.attack:
            i = STRIKES[c.attack].frame(c.age)
            if STRIKES[c.attack].active(i):
                position(
                    self.trail,
                    self.clips["trail_" + c.attack].frames[i],
                    w.x,
                    w.y,
                    w.facing,
                    scroll,
                    lift,
                )
                self.trail.visible = True
        for target_index, (e, sp) in enumerate(zip(c.foes, self.enemies)):
            if e.kind == "bell":
                i = e.pose_index()
            elif e.state == "warn":
                i = 4 + int(e.age >= e.spec.windup // 2)
            elif e.state == "walk":
                i = 2 + (e.age // 11) % 2
            else:
                i = {"active": 6, "recover": 7, "hurt": 8, "dead": 9}.get(
                    e.state, (e.age // 34) % 2
                )
            frames = (
                self.flashes[e.kind][int(self.flash[target_index] > self.levels[1])]
                if self.flash.get(target_index, 0) > 0 and e.kind in self.flashes
                else self.clips[e.kind].frames
            )
            position(sp, frames[i], e.x, e.y, e.facing, scroll, lift)
            sp.visible = e.hp > 0 or e.age < 45
            sp.alpha = max(0, 255 - e.age * 6) if not e.hp else 255
        while len(self.projectiles) < len(c.bolts):
            self.projectiles.append(arcade.Sprite(self.effects["bolt"]))
        for i, sp in enumerate(self.projectiles):
            sp.visible = i < len(c.bolts)
            if sp.visible:
                b = c.bolts[i]
                sp.position = round(b.x) - scroll, round(b.y) - lift
        for p in self.particles:
            p.sprite.position = round(p.x) - scroll, round(p.y) - lift
            p.sprite.alpha = round(p.opacity * p.life / p.maximum)
        self.focus = min(
            (e for e in c.foes if e.hp and abs(e.x - w.x) < 190),
            key=lambda e: abs(e.x - w.x),
            default=None,
        )

    def warnings(self, c, scroll, lift, walker=None):
        self.warning_count = 0
        placed = []
        self.warning_badges.clear()
        for e in c.foes:
            if e.state != "warn" or e.kind == "bell":
                continue
            x, y = round(e.x) - scroll, round(e.y) - lift
            icons, right, left = self.marks[e.kind]
            icon = icons[int(e.age * 3 >= e.spec.windup * 2)]
            dash = right if e.facing > 0 else left
            top = y + e.spec.height + 12
            while any(abs(x - px) < 17 and abs(top - py) < 17 for px, py in placed):
                top += 17
            placed.append((x, top))
            self.warning_badges.append((icon, x, top))
            if e.kind == "rivet":
                muzzle = (e.x + e.facing * 21, e.y + 30)
                end = (muzzle[0] + 190 * e.aim[0], muzzle[1] + 190 * e.aim[1])
                distance = min(1, wall_entry(muzzle, end, c.surfaces)) * 190
                for n in range(12, round(distance), 10):
                    px = x + e.facing * 21 + round(e.aim[0] * n)
                    py = y + 30 + round(e.aim[1] * n)
                    if walker is not None and walker.action != "roll":
                        face_x = round(walker.x) - scroll + 5 * walker.facing
                        face_y = round(walker.y) - lift + 50
                        if abs(px - face_x) < 16 and abs(py - face_y) < 12:
                            continue
                    self.place_warning(dash, px, py)
            elif e.kind == "fork":
                origin = (e.x, e.y + FORK_HEIGHT)
                tip = (e.x + e.facing * FORK_REACH, origin[1])
                reach = FORK_REACH * min(1, wall_entry(origin, tip, c.surfaces))
                for n in range(22, round(reach) - 2, 11):
                    self.place_warning(dash, x + n * e.facing, y + FORK_HEIGHT)
            elif e.kind == "ram":
                room = e.patrol[1] - e.x if e.facing > 0 else e.x - e.patrol[0]
                for n in range(26, min(130, round(room) + 29), 16):
                    px = x + n * e.facing
                    self.place_warning(dash, px, y + 4)
            else:
                for n in (19, 30, 41):
                    self.place_warning(dash, x + n * e.facing, y + 27)
        for index in range(self.warning_count, len(self.warning_list)):
            self.warning_list[index].visible = False
        self.warning_list.draw(pixelated=True)

    def draw_badges(self):
        for icon, x, y in self.warning_badges:
            arcade.draw_texture_rect(icon, arcade.LBWH(x - 8, y - 8, 16, 16), pixelated=True)

    def place_warning(self, texture, x, y):
        if self.warning_count == len(self.warning_list):
            self.warning_list.append(arcade.Sprite(texture))
        sprite = self.warning_list[self.warning_count]
        sprite.texture = texture
        sprite.position = x, y
        sprite.visible = True
        self.warning_count += 1

    def draw_hud(self, c, stamina, show_result=True):
        blit(self.plates[c.weapon], 10, 301)
        box = arcade.draw_lbwh_rectangle_filled
        draw_stamina(stamina)
        box(80, 312, 96, 5, (52, 66, 72))
        hp = round(96*c.hp/MAX_HP)
        echo = round(96*self.echo_hp/MAX_HP)
        if echo > hp:
            box(80+hp, 312, echo-hp, 5, (240, 187, 132))
        if hp:
            box(80, 312, hp, 5, (187, 109, 85))
        if hp > echo:
            box(80+echo, 312, hp-echo, 5, (178, 216, 178))
        if self.weapon_until > c.tick:
            blit(label(self.weapon_names[c.weapon], 10, 73, GOLD), 81, 334,
                 min(255, (self.weapon_until-c.tick)*7))
        if self.focus and c.hp and self.focus.kind in self.tags:
            e = self.focus
            blit(self.tags[e.kind], 523, 328)
            box(530, 328, 86, 3, (43, 48, 54))
            box(530, 328, max(1, round(86*e.hp/e.spec.hp)), 3, (216, 147, 107))
        if show_result and not c.hp and c.death_age > 40:
            blit(self.notices["dead"], 236, 172)
        elif show_result and c.cleared:
            blit(self.notices["clear"], 232, 172)
