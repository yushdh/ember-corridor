import arcade
import pyglet
from PIL import Image

from .motion import WIDTH, HEIGHT, STEP, MAX_STEPS, Walker, fit_view
from .terrain import WORLD_WIDTH, SURFACES
from .resources import ASSETS, load_clips, ui_texture
from .combat import Encounter
from .battle_view import BattleView, position


def make_layer(texture):
    sprite = arcade.Sprite(texture)
    sprite.position = WIDTH // 2, HEIGHT // 2
    return sprite


class QuayWindow(arcade.Window):
    skirmish_result = True

    def __init__(self, *, practice=False):
        # Arcade selects stretch at import. Set physical pixels before making the window.
        pyglet.options.dpi_scaling = "real"
        super().__init__(1280, 720, "余烬回廊 · 盐炉渡口", resizable=True, antialiasing=False, vsync=True)
        self.set_minimum_size(WIDTH, HEIGHT)
        self.camera = arcade.Camera2D(position=(0, 0), projection=arcade.LBWH(0, 0, WIDTH, HEIGHT))
        self.resize_canvas()
        self.walker = Walker()
        self.keys = set()
        self.edges = set()
        self.drop_request = False
        self.remaining = self.scroll = 0.0
        self.lift = 0.0
        self.paused = False
        self.clips = load_clips()
        self.combat = None if practice else Encounter()
        self.battle_view = None if practice else BattleView(self.clips)
        self.scene = arcade.SpriteList()
        self.people = arcade.SpriteList()
        self.foreground = arcade.SpriteList()
        self.interface = arcade.SpriteList()
        batch = self.scene
        self.layers = []
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

        def add_loop(row, x, y, rate, ticks, phase):
            frames = loops[row]
            sprite = arcade.Sprite(frames[phase])
            self.ambient.append((sprite, frames, ticks, phase))
            self.layers.append((sprite, x, HEIGHT - y, rate))
            batch.append(sprite)

        def add_layer(name, left, rate, mirror=False):
            texture = arcade.load_texture(ASSETS / "quay" / f"{name}.png")
            sprite = arcade.Sprite(texture.flip_left_right() if mirror else texture)
            start = left + texture.width // 2
            sprite.position = start, HEIGHT // 2
            self.layers.append((sprite, start, HEIGHT // 2, rate))
            batch.append(sprite)
            return sprite

        add_layer("sky", 0, 0)
        add_layer("engine", 0, 0.34)
        add_layer("annex", WIDTH, 0.34)
        add_loop(0, 574, 15, 0.34, 13, 0)
        add_loop(0, 612, 37, 0.34, 16, 5)
        for i in range(5):
            add_loop(1, 552 + 20 * i, 178, 0.34, 5 + i % 2, i * 2)
        for i in range(2):
            add_layer("quay", i * WIDTH, 1, bool(i))
            add_loop(2, i * WIDTH + 189, 348, 1, 11, 1)
            add_loop(2, i * WIDTH + 470, 344, 1, 12, 8)
        self.structure_layer = add_layer("structures", 0, 1)
        self.actor = arcade.Sprite(self.clips["idle"].frames[0].right)
        self.people.append(self.actor)
        batch = self.foreground
        for i in range(2):
            add_layer("posts", i * WIDTH, 1)
        self.hud = make_layer(ui_texture())
        self.hud.visible = practice
        self.interface.append(self.hud)
        self.pause_overlay = make_layer(ui_texture(paused=True))
        self.pause_overlay.visible = False
        self.interface.append(self.pause_overlay)
        self.sync_pose()

    def resize_canvas(self):
        self.camera.viewport = arcade.LBWH(*fit_view(*self.get_framebuffer_size()))

    def on_resize(self, width, height):
        super().on_resize(width, height)
        if hasattr(self, "camera"):
            self.resize_canvas()

    def on_key_press(self, key, modifiers):
        if key in self.keys:
            return
        self.keys.add(key)
        setting_keys = (arcade.key.F1, arcade.key.F2, arcade.key.F3, arcade.key.F4)
        if self.paused and self.battle_view and key in setting_keys:
            i = setting_keys.index(key)
            self.battle_view.levels[i] = (self.battle_view.levels[i] + 1) % 4
            return
        if key == arcade.key.R and self.combat and (not self.combat.hp or self.combat.cleared):
            self.combat = Encounter()
            self.walker = Walker()
            self.battle_view.reset()
            self.clear_input()
            self.scroll = self.lift = 0.0
            self.paused = self.pause_overlay.visible = False
            self.sync_pose()
            return
        if key == arcade.key.ESCAPE:
            self.paused = not self.paused
            self.clear_input()
            self.keys.add(key)
            self.walker.clear_transients(self.combat.surfaces if self.combat else SURFACES)
            if self.combat:
                self.combat.pause()
            self.pause_overlay.visible = self.paused and self.combat is None
        elif not self.paused:
            if key == arcade.key.SPACE:
                self.drop_request = arcade.key.S in self.keys
            self.edges.add(key)

    def on_key_release(self, key, modifiers):
        self.keys.discard(key)

    def clear_input(self):
        self.keys.clear()
        self.edges.clear()
        self.drop_request = False
        self.remaining = 0.0

    def on_deactivate(self):
        if hasattr(self, "keys"):
            self.clear_input()

    def on_update(self, delta_time):
        if self.paused:
            return
        self.remaining = min(self.remaining + delta_time, MAX_STEPS * STEP)
        axis = int(arcade.key.D in self.keys) - int(arcade.key.A in self.keys)
        while self.remaining + 1e-12 >= STEP:
            moves = dict(
                jump=arcade.key.SPACE in self.edges,
                held=arcade.key.SPACE in self.keys,
                drop=self.drop_request,
                roll=arcade.key.K in self.edges,
            )
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
            sprite.texture = frames[(self.ambient_tick // ticks + phase) % len(frames)]
        for sprite, start, base_y, rate in self.layers:
            sprite.center_x = start - round(self.scroll * rate) + round(dx * rate)
            sprite.center_y = base_y - round(self.lift * rate) + round(dy * rate)

    def on_draw(self):
        self.clear((12, 19, 27), viewport=(0, 0, *self.get_framebuffer_size()))
        self.camera.use()
        self.scene.draw(pixelated=True)
        if self.combat:
            dx, dy = self.battle_view.offset()
            self.draw_weapon_glow(round(self.scroll) - dx, round(self.lift) - dy)
            self.battle_view.enemies.draw(pixelated=True)
            self.battle_view.warnings(self.combat, round(self.scroll) - dx, round(self.lift) - dy)
            self.draw_world_effects(round(self.scroll) - dx, round(self.lift) - dy)
            self.battle_view.trails.draw(pixelated=True)
            self.battle_view.particle_list.draw(pixelated=True)
        self.people.draw(pixelated=True)
        self.foreground.draw(pixelated=True)
        if self.combat:
            v = self.battle_view
            v.projectiles.draw(pixelated=True)
            v.draw_badges()
            v.draw_hud(self.combat, self.skirmish_result)
        self.interface.draw(pixelated=True)
        if self.paused and self.battle_view:
            self.battle_view.draw_pause()

    def on_close(self):
        if self.battle_view:
            self.battle_view.reset()
        super().on_close()

    def draw_world_effects(self, scroll, lift):
        pass

    def draw_weapon_glow(self, scroll, lift):
        pass
