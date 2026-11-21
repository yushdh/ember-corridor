"""The five-room run, its entrance, room interactions and ending."""
from functools import lru_cache
import json
from secrets import randbits

import arcade
from PIL import Image

from .attacks import STRIKES
from .battle_view import flame_coverage, position
from .foundry import Bellkeeper, ENTRY, FoundryEncounter, RELEASE, ROOMS
from .gear import INSERTS
from .motion import STEP, Walker
from .profile import atomic_write
from .routes import ALTERNATES, CLASSIC, generate
from .resources import ASSETS, load_clips
from .window import QuayWindow, save_notice


from .ui import panel, tag, blit, label, GOLD, FOAM, PALE


class CampaignWindow(QuayWindow):
    skirmish_result = False

    def __init__(self, *, save_dir=None, seed=None, classic=False):
        self.mode = "title"
        self.fixed_seed = seed
        self.classic = classic
        super().__init__(save_dir=save_dir)
        with Image.open(ASSETS / "foundry/inserts.png") as sheet:
            self.inserts = {
                key: arcade.Texture(sheet.crop((32 * i, 0, 32 * i + 32, 32)))
                for i, key in enumerate((*INSERTS, "crate"))
            }
        self.gear_badge = None
        self.recipe_tag = tag("永久炉谱   /   覆炉甲片已解锁", 179, GOLD)
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
        self.battle_view.prepare_flash("bell")
        self.room_images = [
            arcade.load_texture(ASSETS / "foundry" / f"room-{n+1}.png") for n in range(len(ROOMS))
        ]
        self.fronts = {t.key: texture for t, texture in zip(CLASSIC, self.room_fronts)}
        with Image.open(ASSETS / "foundry/route-fronts.png") as sheet:
            for i, template in enumerate(ALTERNATES):
                self.fronts[template.key] = arcade.Texture(sheet.crop((0, i*360, 1280, (i+1)*360)))
        self.controls.open_menu("title")
        self.hints = {
            key: tag(label, width)
            for key, label, width in (
                ("open", "E  开门过境    ·    恢复 18 生命", 187),
                ("locked", "门锁未解    ·    清除本室守卫", 179),
                ("valve", "E  扳动绞盘", 88),
                ("need_valve", "← 回到西侧台座，再跳上绞盘吊台", 203),
                ("valve_open", "绞盘已开启", 85),
                ("ring", "E  敲响退潮钟", 103),
                ("forward", "守卫已清除   ·   前往东门 →", 165),
                ("climb", "前往上层绞盘", 101),
                ("crate", "E  打开炉料匣", 99),
                ("salvage", "东门料槽已落匣   →", 132),
            )
        }
        self.seal_tag = label("潮印", 10, 30, FOAM)
        self.boss_tags = [
            tag("守钟人 · 铜潮     一阶" if i == 0 else "守钟人 · 铜潮     二阶", 161, GOLD) for i in range(2)
        ]
        self.death_panel = panel(
            (226, 76), [(17, 7, "潮声吞没了脚步", 20, PALE), (17, 42, "R  从退潮门廊重新出发", 13, GOLD)]
        )
        self.prepare_run()

    def prepare_run(self):
        seed = None if self.classic else self.fixed_seed
        if seed is None and not self.classic:
            seed = randbits(32)
        self.guidance.reset(self.store.data.learned)
        self.route = generate(seed)
        label = "手工潮钟线" if seed is None else f"潮图种子  {seed}"
        if self.route.fallback:
            label += "   ·   备用航线"
        self.seed_tag = tag(label, 220, FOAM)
        self.route_notice = ""
        self.seed_text = label
        self.visited_regions = set()
        self.battle_view.status_weapon = None
        self.battle_view.echo_hp = self.battle_view.previous_hp = 100
        self.battle_view.hp_delay = 0
        self.start_room(0)

    def record_run(self):
        try:
            atomic_write(self.store.directory / "last-route.json",
                         json.dumps(self.route.record(), indent=2).encode("utf8"))
        except OSError:
            self.route_notice = "潮图记录写入失败，可在暂停页抄下种子"

    def start_room(self, index, last=None):
        self.guidance.clear()
        self.index = index
        template = self.route.rooms[index]
        self.combat = FoundryEncounter(template.room, last, shell_known=self.store.data.shell_known)
        old_walker = self.walker
        self.walker = Walker(x=ENTRY[0], y=ENTRY[1])
        if last is not None:
            self.walker.stamina, self.walker.winded = old_walker.stamina, old_walker.winded
        region = template.room.name
        self.region_age = 0.0 if region not in self.visited_regions else 3.0
        self.visited_regions.add(region)
        self.region_title = panel((196, 43), [(98, 5, region, 23, PALE)], style="chapter", fill="#101f29be")
        self.objective_text = self.objective()
        self.entering_objective = True
        self.objective_age = 0.0
        self.scroll = self.lift = 0
        self.battle_view.reset()
        self.battle_view.enemies.clear()
        for e in self.combat.foes:
            self.battle_view.enemies.append(
                arcade.Sprite(self.battle_view.clips[e.kind].frames[0].right)
            )
        self.structure_layer.texture = self.room_images[template.theme]
        self.room_front.texture = self.fronts[template.key]
        for i, sprites in enumerate(self.room_decor):
            for sprite in sprites:
                sprite.visible = i == template.theme
        self.clear_input()
        self.paused = False
        if last is None:
            self.elapsed_ticks = 0
            self.kills = 0
            self.gear_badge = None
            self.gear_until = 0
            self.recipe_until = 0
        self.sync_pose()

    def press_game(self, key, modifiers):
        if self.mode == "forge":
            options = self.combat.loadout.options
            buttons = (arcade.key.KEY_1, arcade.key.KEY_2, arcade.key.KEY_3)[: len(options)]
            if key in (arcade.key.UP, arcade.key.DOWN):
                self.forge_focus = (self.forge_focus + (1 if key == arcade.key.DOWN else -1)) % len(options)
                return
            if key in (arcade.key.ENTER, arcade.key.RETURN):
                key = buttons[self.forge_focus]
            if key == arcade.key.ESCAPE:
                self.mode = "play"
            elif key in buttons:
                item = options[buttons.index(key)]
                if self.combat.claim(self.walker, item):
                    self.gear_badge = tag(
                        f"{INSERTS[item].name}   /   {self.combat.loadout.rank(item)} 阶", 108, GOLD
                    )
                    self.gear_until = self.elapsed_ticks + 240
                    if not self.store.data.shell_known:
                        self.store.update(unlock=True)
                        self.recipe_until = self.elapsed_ticks + 360
                    self.battle_view.sound("gate")
                self.mode = "play"
            else:
                return
            self.clear_input()
            return
        if self.mode == "title":
            if key in (arcade.key.ENTER, arcade.key.RETURN):
                self.mode = "play"
                self.record_run()
                self.clear_input()
            return
        if self.mode == "won" or (not self.combat.hp and key == arcade.key.R):
            if key == arcade.key.R:
                self.mode = "play"
                self.prepare_run()
                self.record_run()
            return
        if key == arcade.key.R:
            return
        if key == arcade.key.E and not self.paused and key not in self.keys:
            result = self.combat.interact(self.walker)
            if result == "crate":
                self.open_forge()
                return
            if result == "exit":
                self.kills += len(self.combat.foes)
                if self.index == len(self.route.rooms) - 1:
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
                    self.guidance.clear()
                    self.clear_input()
                else:
                    self.start_room(self.index + 1, self.combat)
                self.battle_view.sound("gate")
                return
        super().press_game(key, modifiers)

    def open_forge(self):
        self.forge_focus = 0
        build = self.combat.loadout
        self.forge_current = self.forge_stats(build)
        self.forge_offers = {item: self.forge_stats(build.after_fit(item)) for item in build.options}
        self.forge_note = "换下的炉件保留本局阶数"
        if not build.shell_known:
            self.forge_note = ("甲片炉谱已收录，下次出发可用" if self.store.data.shell_known
                               else "首次装配解锁甲片炉谱，下次出发可用")
        self.guidance.clear()
        self.mode = "forge"
        self.clear_input()

    def forge_stats(self, build):
        strike = STRIKES["cut" if self.combat.weapon == "light" else "breaker"]
        return build.melee_damage(strike.damage), build.seal_period, build.damage_reduction

    def on_update(self, dt):
        if self.mode == "play" and not self.paused and not self.closed:
            super().on_update(dt)
            if self.combat.hp:
                self.region_age += dt
                current = self.objective()
                if current != self.objective_text:
                    self.objective_text, self.objective_age = current, 0.0
                    self.entering_objective = False
                elif self.region_age >= 2.8:
                    self.objective_age += dt

    def objective(self):
        c = self.combat
        alive = sum(e.hp > 0 for e in c.foes)
        if alive:
            if c.room.valve:
                valve = "绞盘已开启" if c.valve_open else "扳动上层绞盘"
                return f"{valve}   ·   守卫 {len(c.foes)-alive}/{len(c.foes)}"
            return f"{c.room.goal}   {len(c.foes)-alive}/{len(c.foes)}"
        if not c.valve_open:
            return "从西侧台座跳上吊台，扳动绞盘"
        if self.index == len(self.route.rooms) - 1:
            return "敲响退潮钟"
        return "前往东门" if c.crate_taken else "领取炉料或前往东门"

    def draw_menu(self, root):
        c = self.combat
        build = c.loadout
        item = build.equipped
        self.controls.draw_menu(root, self.battle_view.levels,
            location=f"{c.room.name}   ·   {self.index+1}/{len(self.route.rooms)}",
            objective=self.objective(), seed=self.seed_text, hp=c.hp, stamina=self.walker.stamina,
            weapon=self.battle_view.weapon_names[c.weapon],
            equipment=f"{INSERTS[item].name}  {build.rank(item)} 阶" if item else "",
            recipe=self.store.data.shell_known)

    def clear_input(self):
        super().clear_input()
        if isinstance(getattr(self, "combat", None), FoundryEncounter):
            self.combat.flame_roll_direction = 0
            if self.combat.flame.charge >= 0:
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
        self.battle_view.flame_mask = None
        if not flame.busy:
            return
        clip, index = flame.light_pose(self.battle_view.levels[1])
        frame = self.extra[clip].frames[index]
        w = self.walker
        tex = frame.right if w.facing > 0 else frame.left
        ax, ay = frame.anchor
        x = round(w.x) - (ax if w.facing > 0 else tex.width - ax)
        y = round(w.y) + ay - tex.height
        self.battle_view.flame_mask = (flame_coverage(frame.right), x-scroll, y+tex.height-lift, w.facing)
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
        if c.crate:
            x, y = c.crate
            blit(self.inserts["crate"], x - scroll - 16, y - lift - 2)
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
        notice = self.store.notice or self.route_notice
        message = save_notice(notice) if notice else None
        if self.mode == "title":
            self.draw_menu("title")
            if message:
                blit(message, 123, 62)
            return
        if self.mode == "forge":
            build = c.loadout
            blit(panel((398, 360), style="scrim", fill="#101c27fa"), 0, 0)
            blit(label("东门料槽", 12, 120, GOLD), 28, 324)
            blit(label("装配炉芯", 25, 170), 26, 289)
            equipped = (f"{INSERTS[build.equipped].name}  {build.rank(build.equipped)} 阶"
                        if build.equipped else "空槽")
            blit(label(f"当前炉件   {equipped}", 12, 270, FOAM), 29, 264)
            for i, item in enumerate(build.options):
                y = 230 - i*33
                selected = i == self.forge_focus
                if selected:
                    blit(panel((310, 30), style="focus", fill="#514638ed"), 28, y-5)
                blit(self.inserts[item], 42, y-6)
                rank = build.ranks.get(item, 0)
                blit(label(f"{i+1}   {INSERTS[item].name}", 14, 125, GOLD if selected else PALE), 82, y)
                blit(label(f"{rank} 阶 → {rank+1} 阶", 12, 96, FOAM), 215, y+1)
            choice = build.options[self.forge_focus]
            blit(label("装配预览", 13, 65, GOLD), 29, 128)
            blit(label(INSERTS[choice].effect, 11, 225), 104, 130)
            strike = "短刃首击" if c.weapon == "light" else "重锤首击"
            for i, (title, x) in enumerate(((strike, 29), ("潮印冷却 / 秒", 138), ("固定减伤", 262))):
                old, new = self.forge_current[i], self.forge_offers[choice][i]
                current, result = (f"{old*STEP:.1f}", f"{new*STEP:.1f}") if i == 1 else (str(old), str(new))
                value = result if old == new else f"{current} → {result}"
                blit(label(title, 11, 108, FOAM), x, 101)
                blit(label(value, 15, 115, GOLD if old != new else PALE), x, 80)
            blit(label(self.forge_note, 11, 300, FOAM), 29, 44)
            commands = f"↑ ↓ 预览    Enter 装配    1–{len(build.options)} 快选    Esc 返回"
            blit(label(commands, 11, 320, FOAM), 29, 18)
            return
        if self.paused:
            if message:
                blit(message, 303, 12)
            return
        if c.hp and self.mode == "play":
            if self.region_age < 2.8:
                alpha = min(1, self.region_age / 0.35, (2.8-self.region_age)/0.45)
                blit(self.region_title, 222, 296, round(alpha*255))
            elif self.objective_age < 3:
                alpha = min(1, self.objective_age/0.18, (3-self.objective_age)/0.35)
                text = (f"{c.room.goal}   ·   {self.index+1}/{len(self.route.rooms)} 室"
                        if self.entering_objective else self.objective_text)
                plate = panel((220, 23), [(110, 3, text, 12, PALE)], style="toast")
                blit(plate, 210, 319, round(255*alpha))
            blit(self.seal_tag, 50, 291)
            arcade.draw_lbwh_rectangle_filled(80, 297, 46, 3, (47,61,68))
            fill = round(46*(1-c.cooldown/c.seal_period))
            if fill:
                arcade.draw_lbwh_rectangle_filled(80, 297, fill, 3, (139,184,171))
        w = self.walker
        boss = next((e for e in c.foes if isinstance(e, Bellkeeper)), None)
        if boss and boss.hp and abs(boss.x - w.x) < 475:
            blit(self.boss_tags[boss.phase - 1], 465, 310)
        hint = None
        if self.gear_badge and self.elapsed_ticks < self.gear_until:
            blit(self.gear_badge, 10, 268, min(255, 6*(self.gear_until-self.elapsed_ticks)))
        if message:
            blit(message, 11, 48)
        elif self.elapsed_ticks < self.recipe_until:
            blit(self.recipe_tag, 11, 48)
        if c.crate and c.near(w, c.crate):
            hint = "crate"
        elif c.room.valve and c.near(w, c.room.valve):
            hint = "valve_open" if c.valve_open else "valve"
        elif c.near(w, c.room.door):
            hint = (
                "locked"
                if not c.cleared
                else "need_valve"
                if not c.valve_open
                else "ring"
                if self.index == len(self.route.rooms) - 1
                else "open"
            )
        if hint and c.hp and self.mode == "play":
            texture = self.hints[hint]
            if hint in ("open", "valve", "ring", "crate"):
                texture = tag(self.binding_label("use") + texture.lines[0][2][1:], texture.width)
            blit(
                texture,
                min(630 - texture.width, max(10, round(w.x - self.scroll) - texture.width // 2)),
                64,
            )
        if self.mode == "won":
            blit(self.result, 163, 110)
            blit(self.seed_tag, 163, 87)
        elif not c.hp and c.death_age > 40:
            blit(self.death_panel, 207, 159)
            blit(self.seed_tag, 207, 136)
