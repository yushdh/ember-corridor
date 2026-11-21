import arcade
import pyglet
from PIL import Image, ImageDraw
from arcade.gl import geometry
from functools import lru_cache

from .motion import WIDTH, HEIGHT, STEP, MAX_STEPS, Walker, fit_view
from .terrain import WORLD_WIDTH, SURFACES
from .resources import ASSETS, load_clips
from .profile import ProfileStore
from .combat import Encounter
from .battle_view import BattleView, position
from .harbour import SKY, WHEEL, BAY, WORKS, ROOM_WORKS


from .guidance import Guidance, opportunities
from .controls import Controls
from .ui import tag, panel, blit, draw_stamina, PALE, GOLD


@lru_cache(maxsize=8)
def save_notice(message):
    return tag(message,max(200,13*len(message)+18),GOLD)


# Leave room for multiple 1280-wide scenery layers alongside the character clips.
CAMPAIGN_ATLAS_SIZE = (8192, 4096)


class QuayWindow(arcade.Window):
    skirmish_result = True

    def __init__(self, *, practice=False, save_dir=None):
        # Arcade selects stretch at import. Set physical pixels before making the window.
        pyglet.options.dpi_scaling = "real"
        super().__init__(1280, 720, "余烬回廊 · 盐炉渡口", resizable=True, antialiasing=False, vsync=True)
        if not self.skirmish_result:
            # Reserve campaign scenery space before the first sprite upload. Repacking
            # the shared atlas mid-fight copies every resident image on the render thread.
            limit = min(self.ctx.info.MAX_TEXTURE_SIZE, *self.ctx.info.MAX_VIEWPORT_DIMS)
            self.ctx.atlas_size = tuple(min(side, limit) for side in CAMPAIGN_ATLAS_SIZE)
        self.set_minimum_size(WIDTH, HEIGHT)
        rect = arcade.LBWH(0, 0, WIDTH, HEIGHT)
        self.world_texture = self.ctx.texture((WIDTH, HEIGHT), components=3,
                                              filter=(self.ctx.NEAREST, self.ctx.NEAREST))
        self.world_buffer = self.ctx.framebuffer(color_attachments=[self.world_texture])
        self.screen_quad = geometry.quad_2d_fs()
        self.camera = arcade.Camera2D(position=(0, 0), projection=rect, viewport=rect,
                                      render_target=self.world_buffer)
        self.ui_camera = arcade.Camera2D(position=(0, 0), projection=rect, render_target=self.ctx.screen)
        self.ui_regions = []
        self.resize_canvas()
        self.walker = Walker()
        self.keys = set()
        self.menu_held = set()
        self.edges = set()
        self.drop_request = False
        self.remaining = self.scroll = 0.0
        self.lift = 0.0
        self.paused = False
        self.clips = load_clips()
        self.combat = None if practice else Encounter()
        self.battle_view = None if practice else BattleView(self.clips, self.combat.foes)
        self.store = ProfileStore(save_dir, background_lessons=True)
        self.controls = Controls(self.store)
        self.guidance = Guidance(self.store.data.learned)
        if self.battle_view:
            self.battle_view.levels[:] = self.store.data.levels
        self.scene = arcade.SpriteList()
        self.people = arcade.SpriteList()
        self.foreground = arcade.SpriteList()
        batch = self.scene
        self.layers = []
        self.layer_camera = None
        self.ambient_tick = 0
        self.ambient = []
        with Image.open(ASSETS / "quay/atmosphere.png") as atlas:
            loops = [
                [
                    arcade.Texture(atlas.crop((48 * i, 40 * row, 48 * i + 48, 40 * row + 40)))
                    for i in range(12)
                ]
                for row in range(3)
            ]

        def add_animation(frames, x, y, rate, ticks, phase=0):
            sprite = arcade.Sprite(frames[phase])
            self.ambient.append((sprite, frames, ticks, phase))
            self.layers.append((sprite, x, HEIGHT - y, rate))
            batch.append(sprite)
            return sprite

        def load_strip(spec, groups=1):
            with Image.open(ASSETS / "quay" / (spec.name + ".png")) as image:
                return [
                    [arcade.Texture(image.crop(spec.box(group * spec.count + i)))
                     for i in range(spec.count)]
                    for group in range(groups)
                ]

        def add_loop(row, x, y, rate, ticks, phase):
            return add_animation(loops[row], x, y, rate, ticks, phase)

        def add_layer(name, left, rate, mirror=False):
            texture = arcade.load_texture(ASSETS / "quay" / f"{name}.png")
            sprite = arcade.Sprite(texture.flip_left_right() if mirror else texture)
            start = left + texture.width // 2
            sprite.position = start, HEIGHT // 2
            self.layers.append((sprite, start, HEIGHT // 2, rate))
            batch.append(sprite)
            return sprite

        add_layer("sky", 0, 0)
        add_animation(load_strip(SKY)[0], WIDTH // 2, SKY.height // 2, 0, 18)
        add_animation(load_strip(BAY)[0], 306, 235, 0, 7)
        add_animation(load_strip(WHEEL)[0], 492, 166, 0.34, 5)
        add_layer("engine", 0, 0.34)
        add_layer("annex", WIDTH, 0.34)
        add_loop(0, 574, 15, 0.34, 13, 0)
        add_loop(0, 612, 37, 0.34, 16, 5)
        for i in range(5):
            add_loop(1, 552 + 20 * i, 178, 0.34, 5 + i % 2, i * 2)
        for i in range(2):
            add_layer("quay", i * WIDTH, 1, bool(i))
            add_loop(2, i * WIDTH + 170, 348, 1, 8, 1)
            add_loop(2, i * WIDTH + 470, 348, 1, 8, 8)
        self.structure_layer = add_layer("structures", 0, 1)
        if not self.skirmish_result:
            self.room_decor = []
            strips = load_strip(WORKS, len(ROOM_WORKS))
            for frames, (ticks, centres) in zip(strips, ROOM_WORKS):
                sprites = [add_animation(frames, x, y, 1, ticks, j * 5)
                           for j, (x, y) in enumerate(centres)]
                for sprite in sprites:
                    sprite.visible = False
                self.room_decor.append(sprites)
            with Image.open(ASSETS / "foundry/room-fronts.png") as fronts:
                self.room_fronts = [
                    arcade.Texture(fronts.crop((0, i * HEIGHT, WORLD_WIDTH, (i + 1) * HEIGHT)))
                    for i in range(len(ROOM_WORKS))
                ]
            self.room_front = arcade.Sprite(self.room_fronts[0])
            self.layers.append((self.room_front, WORLD_WIDTH // 2, HEIGHT // 2, 1))
            batch.append(self.room_front)
        self.actor = arcade.Sprite(self.clips["idle"].frames[0].right)
        shadow = Image.new("RGBA", (34, 6))
        pen = ImageDraw.Draw(shadow)
        pen.ellipse((0, 0, 33, 5), fill=(18, 28, 37, 66))
        pen.ellipse((5, 1, 28, 4), fill=(15, 22, 31, 128))
        self.contact_shadows = {
            width: arcade.Texture(shadow.resize((width, 5), Image.Resampling.NEAREST))
            for width in range(1, 35)
        }
        self.people.append(self.actor)
        batch = self.foreground
        for i in range(2):
            add_layer("posts", i * WIDTH, 1)
        self.practice_tag = panel((184, 48), [(40, 0, "耐力", 11, PALE),
                                               (40, 24, "移动练习", 11, PALE)], style="hud")
        self.sync_pose()

    def resize_canvas(self):
        view = fit_view(*self.get_framebuffer_size())
        self.ui_camera.viewport = arcade.LBWH(*view)
        self.ui_scale = view[2] // WIDTH

    def on_resize(self, width, height):
        super().on_resize(width, height)
        if hasattr(self, "ui_camera"):
            self.resize_canvas()

    def binding_label(self, action):
        return self.controls.labels[action]

    def on_key_press(self, key, modifiers):
        if key in self.menu_held:
            return
        if getattr(self, "mode", "play") == "forge":
            self.press_game(key, modifiers)
            if self.mode != "forge":
                self.menu_held.add(key)
            return
        if self.paused or getattr(self, "mode", "play") == "title":
            root = "pause" if self.paused else "title"
            levels = self.battle_view.levels if self.battle_view else None
            action = self.controls.menu_key(key, root, levels)
            if action == "start":
                self.press_game(arcade.key.ENTER, modifiers)
            elif action in ("resume", "replay"):
                if action == "replay":
                    self.guidance.reset(())
                self.toggle_pause()
            self.menu_held.add(key)
            return
        if getattr(self, "mode", "play") not in ("forge", "title"):
            key = self.controls.gameplay_key(key)
        if key is not None:
            self.press_game(key, modifiers)

    def press_game(self, key, modifiers):
        if key in self.keys:
            return
        self.keys.add(key)
        if key == arcade.key.R and self.combat and (not self.combat.hp or self.combat.cleared):
            self.combat = Encounter()
            self.walker = Walker()
            self.battle_view.reset()
            self.battle_view.status_weapon = None
            self.battle_view.echo_hp = self.battle_view.previous_hp = self.combat.hp
            self.clear_input()
            self.scroll = self.lift = 0.0
            self.paused = False
            self.guidance.reset(self.store.data.learned)
            self.sync_pose()
            return
        if key == arcade.key.ESCAPE:
            self.toggle_pause()
            self.menu_held.add(key)
        elif not self.paused:
            if key == arcade.key.SPACE:
                self.drop_request = arcade.key.S in self.keys
            elif key == arcade.key.S and arcade.key.SPACE in self.keys:
                self.drop_request = True
            self.edges.add(key)

    def toggle_pause(self):
        self.paused = not self.paused
        self.controls.open_menu("pause")
        self.clear_input()
        self.walker.clear_transients(self.combat.surfaces if self.combat else SURFACES)
        if self.combat:
            self.combat.pause()
        self.guidance.clear()

    def on_key_release(self, key, modifiers):
        self.menu_held.discard(key)
        self.keys.discard(self.controls.gameplay_key(key))

    def clear_input(self):
        self.menu_held.clear()
        self.keys.clear()
        self.edges.clear()
        self.drop_request = False
        self.remaining = 0.0

    def on_deactivate(self):
        if hasattr(self, "keys"):
            self.clear_input()

    def on_update(self, delta_time):
        # A final scheduled update can arrive after Arcade closes the GL context.
        if self.closed or self.paused:
            return
        self.store.poll()
        self.guidance.advance(delta_time)
        self.remaining = min(self.remaining + delta_time, MAX_STEPS * STEP)
        axis = int(arcade.key.D in self.keys) - int(arcade.key.A in self.keys)
        while self.remaining + 1e-12 >= STEP:
            moves = dict(
                jump=arcade.key.SPACE in self.edges,
                held=arcade.key.SPACE in self.keys,
                drop=self.drop_request,
                roll=arcade.key.K in self.edges,
            )
            w = self.walker
            old_x, old_vy, old_roll = w.x, w.vy, w.roll_age
            serial = self.combat.serial if self.combat else 0
            frozen = False
            if self.combat:
                frozen = self.combat.freeze > 0 and self.combat.hp > 0
                old = self.walker.action
                slot = (
                    "heavy"
                    if arcade.key.KEY_2 in self.edges
                    else "light"
                    if arcade.key.KEY_1 in self.edges
                    else None
                )
                self.step_encounter(axis, moves, slot)
                self.battle_view.tick(self.combat, self.walker, old)
            else:
                self.walker.step(axis, **moves)
            if self.combat and not self.combat.hp:
                self.guidance.clear()
            else:
                completed = []
                if (axis * (w.x-old_x)>0 and w.roll_age < 0
                        and not (self.combat and (self.combat.attack or self.combat.hurt))):
                    completed.append("move")
                if old_vy <= 0 < w.vy and w.action == "jump":
                    completed.append("jump")
                if old_roll < 0 <= w.roll_age:
                    completed.append("roll")
                if self.combat and self.combat.serial != serial:
                    completed.append("attack")
                if len(self.guidance.known) < 4 or self.guidance.active:
                    nearby = opportunities(w, self.combat, self.combat.surfaces if self.combat else SURFACES)
                    learned = self.guidance.observe(nearby,completed)
                    if learned - set(self.store.data.learned):
                        self.store.remember(learned)
            if not frozen:
                self.edges.clear()
                self.drop_request = False
            # Dead zone follows the player in world space; only rendering rounds to pixels.
            screen_x = self.walker.x - self.scroll
            self.scroll += max(0, screen_x - 354) + min(0, screen_x - 238)
            self.scroll = min(WORLD_WIDTH - WIDTH, max(0, self.scroll))
            self.lift += (max(0, self.walker.y - 204) - self.lift) * 0.09
            self.remaining -= STEP
            self.ambient_tick += 1
        self.sync_pose()

    def step_encounter(self, axis, moves, slot):
        self.combat.step(self.walker, axis, **moves, attack=arcade.key.J in self.edges, slot=slot)

    def sync_pose(self):
        actor = self.walker
        if actor.action == "tuck":
            frame = self.clips["roll"].frames[0]
        else:
            frame = self.clips[actor.action].frame(actor.age)
        dx, dy = 0, 0
        if self.combat:
            frame = self.battle_view.actor_frame(self.combat, actor) or frame
            dx, dy = self.battle_view.offset()
            self.battle_view.sync(
                self.combat, actor, round(self.scroll) - dx, round(self.lift) - dy
            )
        position(
            self.actor,
            frame,
            actor.x,
            actor.y,
            actor.facing,
            round(self.scroll) - dx,
            round(self.lift) - dy,
        )
        self.actor.alpha = (
            180 if self.combat and self.combat.immune and self.combat.tick % 12 < 4 else 255
        )
        for sprite, frames, ticks, phase in self.ambient:
            if sprite.visible:
                sprite.texture = frames[(self.ambient_tick // ticks + phase) % len(frames)]
        camera = (self.scroll, self.lift, dx, dy)
        if camera != self.layer_camera:
            for sprite, start, base_y, rate in self.layers:
                sprite.position = (start - round(self.scroll * rate) + round(dx * rate),
                                   base_y - round(self.lift * rate) + round(dy * rate))
            self.layer_camera = camera

    def on_draw(self):
        self.camera.use()
        self.world_buffer.clear(color=(12, 19, 27, 255))
        self.scene.draw(pixelated=True)
        dx, dy = self.battle_view.offset() if self.combat else (0, 0)
        scroll, lift = round(self.scroll) - dx, round(self.lift) - dy
        w = self.walker
        surface = max(
            (
                s
                for s in (self.combat.surfaces if self.combat else SURFACES)
                if s.left <= w.x < s.right and s.top <= w.y + 0.01
            ),
            key=lambda s: s.top,
            default=None,
        )
        if surface:
            gap = max(0, w.y - surface.top)
            radius = max(5, 17 - round(gap / 10))
            left, right = max(surface.left, round(w.x) - radius), min(
                surface.right, round(w.x) + radius
            )
            if right > left and gap < 130:
                arcade.draw_texture_rect(
                    self.contact_shadows[right - left],
                    arcade.LBWH(left - scroll, surface.top - lift - 4, right - left, 5),
                    alpha=max(45, 235 - round(gap * 1.5)),
                    pixelated=True,
                )
        if self.combat:
            self.draw_weapon_glow(scroll, lift)
            self.battle_view.trails.draw(pixelated=True)
            self.battle_view.enemies.draw(pixelated=True)
            self.draw_world_effects(scroll, lift)
            self.battle_view.particle_list.draw(pixelated=True)
            self.battle_view.warnings(self.combat, scroll, lift, self.walker)
        self.people.draw(pixelated=True)
        self.foreground.draw(pixelated=True)
        if self.combat:
            v = self.battle_view
            v.projectiles.draw(pixelated=True)
            v.draw_badges()
        self.present_world()
        self.ui_regions.clear()
        if self.paused:
            self.draw_menu("pause")
            return
        if getattr(self, "mode", "play") != "play":
            return
        if self.combat:
            self.battle_view.draw_hud(self.combat, self.walker.stamina, self.skirmish_result)
        else:
            blit(self.practice_tag, 10, 301)
            draw_stamina(self.walker.stamina)
        if not self.combat or self.combat.hp:
            self.controls.draw_lesson(self.guidance)
        if self.skirmish_result and self.store.notice:
            blit(save_notice(self.store.notice),14,54)

    @property
    def help_open(self):
        return self.controls.page == "bindings"

    def draw_menu(self, root):
        c = self.combat
        self.controls.draw_menu(root, self.battle_view.levels if c else None,
                                hp=c.hp if c else None, stamina=self.walker.stamina,
                                weapon=self.battle_view.weapon_names[c.weapon] if c else "")

    def present_world(self):
        self.ui_camera.use()
        self.ctx.screen.clear(color=(12,19,27,255), viewport=(0,0,*self.get_framebuffer_size()))
        self.world_texture.use(0)
        with self.ctx.enabled_only():
            self.screen_quad.render(self.ctx.utility_textured_quad_program)

    def close(self):
        if hasattr(self, "store"):
            self.store.close()
        super().close()

    def on_close(self):
        if self.battle_view:
            self.battle_view.reset()
        super().on_close()

    def draw_world_effects(self, scroll, lift):
        pass

    def draw_weapon_glow(self, scroll, lift):
        pass
