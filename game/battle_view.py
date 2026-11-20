"""Preloaded combat presentation. Input and hit stop never block the window."""
from dataclasses import dataclass, replace
import math
import random

import arcade
from PIL import Image, ImageDraw, ImageFont

from .attacks import STRIKES
from .combat import MAX_HP, TYPES, wall_entry
from .resources import ASSETS, font_face, load_clips


def position(sprite, frame, x, y, facing, scroll, lift):
    sprite.texture = frame.right if facing > 0 else frame.left
    ax, ay = frame.anchor
    sprite.position = (
        round(x) - scroll + facing * (sprite.texture.width // 2 - ax),
        round(y) - lift + ay - sprite.texture.height // 2,
    )


def interface(weapon=None, foe=None, notice=None, campaign=False):
    im = Image.new("RGBA", (640, 360))
    d = ImageDraw.Draw(im)
    face = font_face()

    def word(x, y, value, size, color):
        d.text((x, y), value, font=ImageFont.truetype(face, size), fill=color)

    pale, muted, gold = "#ede2c9", "#adbfbb", "#d9aa6a"
    if weapon:
        d.polygon(
            [(10, 10), (163, 10), (171, 18), (171, 52), (10, 52)],
            fill=(24, 37, 46, 242),
            outline="#70817d",
        )
        d.line((12, 13, 12, 49), fill=gold, width=2)
        d.polygon([(19, 29), (30, 16), (42, 29), (30, 43)], fill="#263e4a", outline="#c59b66")
        if weapon == "light":
            d.polygon([(24, 36), (27, 28), (38, 19), (33, 29)], fill="#f6cb82")
        else:
            d.line((24, 37, 35, 23), fill="#d1a879", width=2)
            d.polygon([(28, 21), (33, 17), (40, 23), (37, 29)], fill="#b7d7d0", outline="#789197")
        word(49, 12, "遗迹行者" if campaign else "盐炉渡口", 13, pale)
        word(108, 15, "余烬弯刃" if weapon == "light" else "潮砧重锤", 10, gold)
        word(49, 32, "体力", 10, muted)
        d.rectangle((76, 36, 159, 42), fill="#182730", outline="#72847f")
        labels = (
            ("A/D", "移动"),
            ("Space", "跳"),
            ("S+Space", "下穿"),
            ("J", "攻击"),
            ("K", "翻滚"),
            ("1/2", "换武器"),
            ("Esc", "暂停"),
        )
        x = 12
        for key, label in labels + ((("Q", "潮印"), ("E", "交互")) if campaign else ()):
            f = ImageFont.truetype(face, 11)
            width = round(d.textlength(key, font=f)) + 8
            d.rectangle((x, 332, x + width, 348), fill="#253944", outline="#82918b")
            word(x + 4, 332, key, 11, pale)
            x += width + 4
            d.text((x, 331), label, font=f, fill=pale, stroke_width=1, stroke_fill="#25333f")
            x += round(d.textlength(label, font=f)) + 12
    if foe:
        d.polygon(
            [(515, 11), (628, 11), (628, 41), (508, 41), (508, 18)],
            fill=(29, 40, 46, 236),
            outline="#887e70",
        )
        word(520, 14, TYPES[foe].title, 12, pale)
        d.rectangle((521, 33, 617, 36), fill="#393c42")
    if notice:
        if notice == "pause":
            d.rectangle((208, 94, 432, 248), fill=(22, 35, 44, 249), outline="#ac9475")
            word(223, 102, "渡口暂停", 18, pale)
            word(346, 110, "Esc 继续", 11, muted)
            for i, label in enumerate(("F1   镜头震动", "F2   命中闪光", "F3   音量", "F4   粒子密度")):
                word(225, 140 + i * 24, label, 13, pale)
        elif notice == "dead":
            d.rectangle((213, 121, 427, 198), fill=(25, 34, 42, 247), outline="#b49370")
            word(276, 132, "炉火熄灭", 21, pale)
            word(252, 170, "按 R 回到盐炉渡口", 13, gold)
        else:
            d.rectangle((435, 12, 628, 41), fill=(25, 42, 49, 245), outline="#8b9b89")
            word(445, 17, "岸线已清理   R 重新交锋", 13, pale)
    return arcade.Texture(im)


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


def warning_marks(kind):
    ink = "#192530"
    edge = {"hook": "#edb079", "rivet": "#8fd9cd", "ram": "#f2aa76"}[kind]
    icon = Image.new("RGBA", (16, 16))
    d = ImageDraw.Draw(icon)
    d.polygon([(4, 0), (11, 0), (15, 4), (15, 9), (8, 15), (0, 10), (0, 4)], fill=ink, outline=edge)
    if kind == "hook":
        d.line((5, 7, 5, 9, 8, 10, 11, 7, 11, 3), fill=edge, width=2)
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
    return arcade.Texture(icon), tex, tex.flip_left_right()


class BattleView:
    def __init__(self, movement):
        self.clips = load_clips("combat")
        self.movement = movement
        self.levels = [2, 2, 2, 2]  # shake, flashes, volume, particles; 0..3
        self.flashes = {}
        for kind in TYPES:
            variants = []
            for frame in self.clips[kind].frames:
                base = frame.right.image.convert("RGBA")
                # Keep the ink outline, visor slit and deep folds during a contact flash.
                mask = base.convert("L").point(lambda value: max(0, min(145, (value - 36) * 2)))
                lit = Image.composite(
                    Image.new("RGBA", base.size, (255, 225, 162, 255)), base, mask
                )
                lit.putalpha(base.getchannel("A"))
                tex = arcade.Texture(lit)
                variants.append(replace(frame, right=tex, left=tex.flip_left_right()))
            self.flashes[kind] = variants
        self.enemies = arcade.SpriteList()
        self.marks = {kind: warning_marks(kind) for kind in TYPES}
        self.warning_list = arcade.SpriteList()
        self.warning_count = 0
        self.warning_badges = []
        for kind in TYPES:
            self.enemies.append(arcade.Sprite(self.clips[kind].frames[0].right))
        self.trail = arcade.Sprite(self.clips["trail_cut"].frames[3].right)
        self.trails = arcade.SpriteList()
        self.trails.append(self.trail)
        self.projectiles = arcade.SpriteList()
        self.particle_list = arcade.SpriteList()
        self.particles = []
        self.effects = {k: effect_texture(k) for k in ("chip", "mist", "bolt", "burst")}
        self.sparks = [effect_texture("spark", i) for i in range(12)]
        self.rng = random.Random(19)
        self.plates = {k: interface(weapon=k) for k in ("light", "heavy")}
        self.tags = {k: interface(foe=k) for k in TYPES}
        self.notices = {k: interface(notice=k) for k in ("dead", "clear", "pause")}
        self.sounds = {
            p.stem: arcade.load_sound(p) for p in sorted((ASSETS / "combat/audio").glob("*.wav"))
        }
        self.players = []
        self.last_event = 0
        self.shake = 0
        self.shake_size = 0
        self.kick_direction = 1
        self.flash = {}
        self.focus = None

    def reset(self):
        for sound, player in self.players:
            sound.stop(player)
        self.players.clear()
        self.particles.clear()
        self.particle_list.clear()
        self.projectiles.clear()
        self.last_event = self.shake = 0
        self.flash.clear()
        self.focus = None

    def sound(self, name):
        self.players = [(s, p) for s, p in self.players if s.is_playing(p)]
        # Reserve a voice for a telegraph when movement and impacts coincide.
        warnings = (*TYPES, "sweep", "vent", "phase")
        if len(self.players) >= 6 and name in warnings:
            for index, (sound, player) in enumerate(self.players):
                if sound not in (self.sounds.get(k) for k in warnings):
                    sound.stop(player)
                    self.players.pop(index)
                    break
        if len(self.players) < 6 and self.levels[2]:
            cue = self.sounds[name]
            gain = {"sabre": 0.75, "maul": 0.85, "land": 0.66, "roll": 0.75, "crush": 1.12}.get(
                name, 1
            )
            self.players.append((cue, cue.play(volume=0.155 * self.levels[2] * gain)))

    def particle(self, tex, x, y, vx, vy, life, alpha=255):
        if len(self.particles) >= 16 * self.levels[3]:
            return
        sprite = arcade.Sprite(tex)
        self.particle_list.append(sprite)
        self.particles.append(Particle(sprite, x, y, vx, vy, life, life, alpha))

    def tick(self, c, w, old_action):
        self.shake = max(0, self.shake - 1)
        self.flash = {k: n - 1 for k, n in self.flash.items() if n > 1}
        for p in self.particles[:]:
            p.life -= 1
            if p.life <= 0:
                p.sprite.remove_from_sprite_lists()
                self.particles.remove(p)
            else:
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
        if w.action == "roll" and w.roll_age in (6, 23) and not c.freeze:
            clip = self.clips["hammer_roll"] if c.weapon == "heavy" else self.movement["roll"]
            f = clip.frame(w.age)
            tex = f.right if w.facing > 0 else f.left
            self.particle(tex, w.x, w.y + f.anchor[1] - tex.height // 2, 0, 0, 9, 62)

    def event(self, ev):
        k = ev["kind"]
        if k in ("seal", "sweep", "vent", "phase", "gate"):
            self.sound(k)
        elif k == "warn":
            self.sound(ev["enemy"])
        elif k == "shot":
            self.sound("shot")
        elif k == "swing":
            self.sound("maul" if ev["action"] == "breaker" else "sabre")
        elif k in ("hit", "hurt", "death", "evade"):
            heavy = ev.get("action") == "breaker"
            facing = ev.get("facing", 1)
            if k != "evade":
                self.sound(("crush" if heavy else "hit") if k == "hit" else "hurt")
                self.shake, self.shake_size = (16, 3) if heavy else (11, 1)
                self.kick_direction = facing
                if k == "hit":
                    self.flash[ev["enemy"]] = 3 * self.levels[1]
                if self.levels[1]:
                    self.particle(
                        self.effects["burst"], ev["x"], ev["y"], 0, 0, 5 + self.levels[1], 210
                    )
            for i in range((4 if heavy else 2) * self.levels[3]):
                chip = heavy and i % 3 == 2
                angle = self.rng.uniform(0.35, 1.36) if chip else self.rng.uniform(-0.32, 0.77)
                if i % 5 == 4:
                    angle = math.pi - angle
                speed = self.rng.uniform(0.45, 1.05) if chip else self.rng.uniform(1.25, 2.55)
                vx, vy = facing * speed * math.cos(angle), speed * math.sin(angle)
                sector = round(math.atan2(vy, vx) * 12 / math.tau) % 12
                self.particle(
                    self.effects["chip"] if chip else self.sparks[sector],
                    ev["x"] + vx,
                    ev["y"] + vy,
                    vx,
                    vy,
                    14 if chip else 8 + i % 6,
                )

    def offset(self):
        if not self.shake or not self.levels[0]:
            return 0, 0
        duration = 16 if self.shake_size == 3 else 11
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
        for e, sp in zip(c.foes, self.enemies):
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
                self.flashes[e.kind]
                if self.flash.get(e.kind, 0) > 0 and e.kind in self.flashes
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

    def warnings(self, c, scroll, lift):
        self.warning_count = 0
        placed = []
        self.warning_badges.clear()
        for e in c.foes:
            if e.state != "warn" or e.kind == "bell":
                continue
            x, y = round(e.x) - scroll, round(e.y) - lift
            icon, right, left = self.marks[e.kind]
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
                    self.place_warning(
                        dash,
                        x + e.facing * 21 + round(e.aim[0] * n),
                        y + 30 + round(e.aim[1] * n),
                    )
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

    def draw_hud(self, c, show_result=True):
        rect = arcade.LBWH(0, 0, 640, 360)
        arcade.draw_texture_rect(self.plates[c.weapon], rect, pixelated=True)
        bar = arcade.draw_lbwh_rectangle_filled
        if c.hp:
            bar(77, 318, max(1, round(82 * c.hp / MAX_HP)), 4, (220, 159, 95))
        if self.focus and c.hp and self.focus.kind in self.tags:
            e = self.focus
            arcade.draw_texture_rect(self.tags[e.kind], rect, pixelated=True)
            bar(522, 324, max(1, round(95 * e.hp / e.spec.hp)), 2, (219, 153, 123))
        if not show_result:
            return
        if not c.hp and c.death_age > 40:
            arcade.draw_texture_rect(self.notices["dead"], rect, pixelated=True)
        elif c.cleared:
            arcade.draw_texture_rect(self.notices["clear"], rect, pixelated=True)

    def draw_pause(self):
        arcade.draw_texture_rect(self.notices["pause"], arcade.LBWH(0, 0, 640, 360), pixelated=True)
        for row, level in enumerate(self.levels):
            for i in range(3):
                color = (219, 174, 109) if i < level else (61, 78, 82)
                arcade.draw_lbwh_rectangle_filled(360 + 13 * i, 207 - row * 24, 9, 5, color)
