"""The five-room run, its entrance, room interactions and ending."""
from functools import lru_cache

import arcade
from PIL import Image, ImageDraw, ImageFont

from .battle_view import interface, position
from .foundry import Bellkeeper, COOLDOWN, FoundryEncounter, RELEASE, ROOMS
from .motion import Walker
from .resources import ASSETS, font_face, load_clips
from .window import QuayWindow


def panel(size, lines, *, border="#9a896e"):
    im = Image.new("RGBA", size)
    d = ImageDraw.Draw(im)
    width, height = size
    d.polygon(
        [(0, 7), (7, 0), (width - 8, 0), (width - 1, 7), (width - 1, height - 1), (0, height - 1)],
        fill=(22, 34, 43, 244),
        outline=border,
    )
    for x, y, text, point, color in lines:
        d.text((x, y), text, font=ImageFont.truetype(font_face(), point), fill=color)
    return arcade.Texture(im)


GOLD = "#e1b679"
FOAM = "#9fcec2"
PALE = "#eee4ca"


def tag(text, width, color=PALE):
    return panel((width, 21), [(7, 1, text, 12, color)])


def blit(texture, x, y):
    arcade.draw_texture_rect(
        texture, arcade.LBWH(x, y, texture.width, texture.height), pixelated=True
    )


class CampaignWindow(QuayWindow):
    skirmish_result = False

    def __init__(self):
        self.mode = "title"
        super().__init__()
        self.extra = load_clips("foundry")
        impact = self.extra["fire-impact"].frames
        self.battle_view.fire_impacts = {
            1: tuple(f.right for f in impact),
            -1: tuple(f.left for f in impact),
        }
        self.fx = []
        with Image.open(ASSETS / "foundry/effects.png") as sheet:
            for row, (width, height) in enumerate(((143, 31), (111, 30), (134, 30), (46, 112))):
                self.fx.append(
                    [
                        arcade.Texture(
                            sheet.crop((i * 144, row * 112, i * 144 + width, row * 112 + height))
                        )
                        for i in range(6)
                    ]
                )
        self.battle_view.clips["bell"] = self.extra["bell"]
        self.battle_view.plates = {
            k: interface(weapon=k, campaign=True) for k in ("light", "heavy")
        }
        self.room_images = [
            arcade.load_texture(ASSETS / "foundry" / f"room-{n+1}.png") for n in range(len(ROOMS))
        ]
        self.room_tags = [
            panel(
                (231, 44),
                [
                    (9, 2, f"潮钟线   {i+1} / {len(ROOMS)}", 10, FOAM),
                    (9, 15, r.name, 16, PALE),
                    (92, 19, r.goal, 10, GOLD),
                ],
            )
            for i, r in enumerate(ROOMS)
        ]
        self.title = panel(
            (356, 154),
            [
                (22, 13, "盐炉渡口   /   潮钟线", 13, FOAM),
                (20, 33, "余烬回廊", 33, PALE),
                (22, 85, "潮水即将倒灌。穿过四道厂门，在熔庭敲响退潮钟。", 12, GOLD),
                (22, 119, "Enter  开始行走", 15, PALE),
                (166, 122, "Q  施放潮印     E  操作机关", 11, FOAM),
            ],
        )
        self.hints = {
            key: tag(label, width)
            for key, label, width in (
                ("open", "E  开门过境    ·    恢复 18 体力", 187),
                ("locked", "门锁未解    ·    清除本室守卫", 179),
                ("valve", "E  扳动绞盘", 88),
                ("need_valve", "绞盘未开    ·    登上吊廊", 161),
                ("valve_open", "绞盘已开启", 85),
                ("ring", "E  敲响退潮钟", 103),
                ("forward", "守卫已清除   ·   前往东门 →", 165),
                ("climb", "前往上层绞盘   ·   E 操作", 157),
            )
        }
        self.seal_tag = tag("潮印  Q", 91, FOAM)
        self.flame_tag = tag("弯刃  ·  按住 L 蓄焰，松开斩击", 181, GOLD)
        self.boss_tags = [
            tag("守钟人 · 铜潮     一阶" if i == 0 else "守钟人 · 铜潮     二阶", 161, GOLD) for i in range(2)
        ]
        self.death_panel = panel(
            (226, 76), [(17, 7, "潮声吞没了脚步", 20, PALE), (17, 42, "R  从退潮门廊重新出发", 13, GOLD)]
        )
        self.start_room(0)

    def start_room(self, index, last=None):
        self.index = index
        self.combat = FoundryEncounter(ROOMS[index], last)
        self.walker = Walker(x=75)
        self.scroll = self.lift = 0
        self.battle_view.reset()
        self.battle_view.enemies.clear()
        for e in self.combat.foes:
            self.battle_view.enemies.append(
                arcade.Sprite(self.battle_view.clips[e.kind].frames[0].right)
            )
        self.structure_layer.texture = self.room_images[index]
        self.clear_input()
        self.paused = False
        if last is None:
            self.elapsed_ticks = 0
            self.kills = 0
        self.sync_pose()

    def on_key_press(self, key, modifiers):
        if self.mode == "title":
            if key in (arcade.key.ENTER, arcade.key.RETURN):
                self.mode = "play"
                self.clear_input()
            return
        if self.mode == "won" or (not self.combat.hp and key == arcade.key.R):
            if key == arcade.key.R:
                self.mode = "play"
                self.start_room(0)
            return
        if key == arcade.key.R:
            return
        if key == arcade.key.E and not self.paused and key not in self.keys:
            result = self.combat.interact(self.walker)
            if result == "exit":
                self.kills += len(self.combat.foes)
                if self.index == len(ROOMS) - 1:
                    seconds = self.elapsed_ticks // 120
                    self.result = panel(
                        (302, 140),
                        [
                            (19, 11, "潮钟线  /  胜利结算", 13, FOAM),
                            (17, 35, "退潮钟已鸣", 28, PALE),
                            (
                                19,
                                82,
                                f"五室贯通    击破 {self.kills}    行程 {seconds//60}:{seconds%60:02}",
                                13,
                                GOLD,
                            ),
                            (19, 110, "R  再走一次潮钟线", 13, PALE),
                        ],
                    )
                    self.mode = "won"
                    self.clear_input()
                else:
                    self.start_room(self.index + 1, self.combat)
                self.battle_view.sound("gate")
                return
        super().on_key_press(key, modifiers)

    def on_update(self, dt):
        if self.mode == "play":
            super().on_update(dt)

    def clear_input(self):
        super().clear_input()
        if (
            isinstance(getattr(self, "combat", None), FoundryEncounter)
            and self.combat.flame.charge >= 0
        ):
            self.combat.flame.reset()

    def step_encounter(self, axis, moves, slot):
        self.combat.step(
            self.walker,
            axis,
            **moves,
            attack=arcade.key.J in self.edges,
            skill=arcade.key.Q in self.edges,
            flame_press=arcade.key.L in self.edges,
            flame_hold=arcade.key.L in self.keys,
            slot=slot,
        )
        if self.combat.hp:
            self.elapsed_ticks += 1

    def sync_pose(self):
        super().sync_pose()
        if not isinstance(self.combat, FoundryEncounter):
            return
        if self.combat.flame.busy:
            frame = self.extra["firecut"].frames[self.combat.flame.frame]
        elif self.combat.cast_age >= 0:
            frame = self.extra["cast"].frame(self.combat.cast_age / 120)
        else:
            return
        dx, dy = self.battle_view.offset()
        w = self.walker
        position(
            self.actor, frame, w.x, w.y, w.facing, round(self.scroll) - dx, round(self.lift) - dy
        )

    def draw_weapon_glow(self, scroll, lift):
        flame = self.combat.flame
        if not flame.busy:
            return
        frame = self.extra["firelight"].frames[flame.frame]
        w = self.walker
        tex = frame.right if w.facing > 0 else frame.left
        ax, ay = frame.anchor
        x = round(w.x) - (ax if w.facing > 0 else tex.width - ax)
        y = round(w.y) + ay - tex.height
        rect = arcade.LBWH(x - scroll, y - lift, tex.width, tex.height)
        # Slice the native-pixel glow at solid faces. A raised platform only
        # masks the band it occupies, leaving flames above its top visible.
        solids = [
            s
            for s in self.combat.surfaces
            if not s.one_way
            and s.top > w.y
            and s.left < x + tex.width
            and x < s.right
            and s.bottom < y + tex.height
        ]
        if not solids:
            arcade.draw_texture_rect(tex, rect, pixelated=True)
            return
        levels = sorted(
            {y, y + tex.height}
            | {max(y, min(y + tex.height, v)) for s in solids for v in (s.top, s.bottom)}
        )
        vx, vy, vw, vh = self.camera.viewport.lbwh_int
        scale = vw // 640
        old = self.ctx.scissor
        try:
            for low, high in zip(levels, levels[1:]):
                left, right = x, x + tex.width
                for s in solids:
                    if s.top <= low or high <= s.bottom:
                        continue
                    if w.x <= s.left:
                        right = min(right, s.left)
                    elif w.x >= s.right:
                        left = max(left, s.right)
                    else:
                        right = left
                left, right = max(0, left - scroll), min(640, right - scroll)
                bottom, top = max(0, low - lift), min(360, high - lift)
                if left < right and bottom < top:
                    self.ctx.scissor = (
                        vx + left * scale,
                        vy + bottom * scale,
                        (right - left) * scale,
                        (top - bottom) * scale,
                    )
                    arcade.draw_texture_rect(tex, rect, pixelated=True)
        finally:
            self.ctx.scissor = old

    def draw_world_effects(self, scroll, lift):
        c = self.combat
        box = arcade.draw_lbwh_rectangle_filled
        if c.cleared and c.valve_open:
            # Uncover the gate slats, with a narrow lit jamb that reads at normal zoom.
            door_x, door_y = c.room.door
            x, y = door_x - scroll, door_y - lift
            box(x - 17, y, 34, 49, (24, 37, 44))
            box(x + 12, y + 2, 3, 43, (114, 171, 158))
            box(x - 15, y + 1, 30, 2, (190, 186, 145))
        for e in c.foes:
            if not isinstance(e, Bellkeeper) or e.state not in ("warn", "active"):
                continue
            for l, b, r, t in e.zones():
                x, y = round(l) - scroll, round(b) - lift
                width, height = round(r - l), round(t - b)
                if e.state == "warn":
                    # A horizontal serrated strip for a sweep, upright brackets for locked vents.
                    box(x, y, width, 3, (45, 29, 34))
                    box(x, y + 1, max(1, round(width * e.age / e.windup)), 2, (250, 176, 96))
                    for px in range(x, x + width, 12):
                        box(px, y + 3, 3, 3, (234, 171, 106))
                    if e.move_name == "vent":
                        for off in (0, width - 2):
                            for n in range(6, height, 13):
                                box(x + off, y + n, 2, 5, (225, 164, 105))
                else:
                    row = e.phase if e.move_name == "sweep" else 3
                    tex = self.fx[row][min(5, e.age // 3)]
                    blit(tex if e.facing > 0 else tex.flip_left_right(), x, y)
        if RELEASE <= c.cast_age < RELEASE + 12 and c.wave_length > 0:
            x, y = c.wave_origin
            x, y = round(x) - scroll, round(y) - lift
            reach = c.wave_length * c.wave_facing
            alpha = 235 - 13 * (c.cast_age - RELEASE)
            tex = self.wave_texture((c.cast_age - RELEASE) // 2, c.wave_length, c.wave_facing)
            arcade.draw_texture_rect(
                tex,
                arcade.LBWH(min(x, x + reach), y - 15, tex.width, 31),
                alpha=alpha,
                pixelated=True,
            )

    @lru_cache(maxsize=64)
    def wave_texture(self, frame, length, facing):
        tex = self.fx[0][frame].crop(0, 0, length + 1, 31)
        return tex if facing > 0 else tex.flip_left_right()

    def on_draw(self):
        super().on_draw()
        c = self.combat
        if self.mode == "title":
            blit(self.title, 177, 134)
            return
        if self.paused:
            return
        blit(self.room_tags[self.index], 184, 306)
        blit(self.seal_tag, 11, 281)
        if c.weapon == "light" and c.hp:
            blit(self.flame_tag, 11, 257)
        arcade.draw_lbwh_rectangle_filled(
            64,
            288,
            max(1, round(29 * (1 - c.cooldown / COOLDOWN))),
            4,
            (131, 208, 187) if not c.cooldown else (139, 133, 114),
        )
        w = self.walker
        boss = next((e for e in c.foes if isinstance(e, Bellkeeper)), None)
        if boss and boss.hp and abs(boss.x - w.x) < 475:
            blit(self.boss_tags[boss.phase - 1], 465, 310)
            arcade.draw_lbwh_rectangle_filled(467, 306, 156, 4, (47, 37, 42))
            arcade.draw_lbwh_rectangle_filled(
                467, 306, max(1, round(156 * boss.hp / boss.spec.hp)), 4, (220, 155, 90)
            )
        hint = None
        if c.room.valve and c.near(w, c.room.valve):
            hint = "valve_open" if c.valve_open else "valve"
        elif c.near(w, c.room.door):
            hint = (
                "locked"
                if not c.cleared
                else "need_valve"
                if not c.valve_open
                else "ring"
                if self.index == len(ROOMS) - 1
                else "open"
            )
        if hint and c.hp and self.mode == "play":
            texture = self.hints[hint]
            blit(
                texture,
                min(630 - texture.width, max(10, round(w.x - self.scroll) - texture.width // 2)),
                64,
            )
        elif c.cleared and c.hp and self.mode == "play":
            blit(self.hints["forward" if c.valve_open else "climb"], 184, 282)
        if self.mode == "won":
            blit(self.result, 163, 110)
        elif not c.hp and c.death_age > 40:
            blit(self.death_panel, 207, 159)
