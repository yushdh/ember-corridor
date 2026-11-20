"""Deterministic gameplay rendering and presented-frame timing in a visible Arcade window."""
import argparse
import json
import platform
import statistics
import sys
from math import ceil
from pathlib import Path
from time import perf_counter

from PIL import Image
import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.window import QuayWindow
from game.combat import Encounter
from game.motion import Walker, STEP
from game.terrain import SURFACES
from pixel_check import check_pixels

FRAMES = 96  # each scene lasts 192 fixed physics ticks
SCENES = ("motion", "blade", "hammer")
SAMPLES = 3


def stats(times):
    values = sorted(times)
    return {
        "mean": statistics.mean(values),
        "p95": values[ceil(0.95 * len(values)) - 1],
        "p99": values[ceil(0.99 * len(values)) - 1],
        "max": max(values),
    }


class Replay(QuayWindow):
    def __init__(self, out):
        self.ready = False
        super().__init__()
        self.out = out
        self.count = 0
        self.samples = []
        self.reel = []
        self.shots = {}
        self.last_flip = None
        self.played = {}
        self.texture_ids = {}
        for name, clip in {**self.clips, **self.battle_view.clips}.items():
            for i, frame in enumerate(clip.frames):
                for texture in (frame.left, frame.right):
                    self.texture_ids[id(texture)] = (name, i)
        self.ready = True

    def on_update(self, dt):
        pass  # fixed inputs and two production steps per submitted frame

    def setup_scene(self, scene):
        self.ambient_tick = 0
        self.combat = Encounter()
        self.clear_input()
        self.battle_view.reset()
        self.battle_view.levels[:] = [3, 3, 3, 3]
        self.battle_view.rng.seed(19)
        self.lift = self.scroll = 0.0
        if scene == "motion":
            self.walker = Walker(x=260)
        elif scene == "blade":
            self.walker = Walker(x=329)
            self.combat.foes[0].x = 369
        else:
            surface = next(s for s in SURFACES if s.name == "landing")
            self.walker = Walker(x=547, y=surface.top, support=surface)
            self.scroll = 214.0
            self.combat.weapon = "heavy"
            for enemy, x in zip(self.combat.foes, (590, 644, 630)):
                enemy.x, enemy.y = x, surface.top
                enemy.patrol = (550, 655)

    def input_step(self, scene, t):
        K = arcade.key
        if scene == "motion":
            events = {
                0: ((K.D, True),),
                38: ((K.SPACE, True),),
                91: ((K.SPACE, False),),
                150: ((K.K, True), (K.K, False)),
                182: ((K.D, False),),
            }
        else:
            times = (0, 20, 45, 105) if scene == "blade" else (0, 93)
            events = {n: ((K.J, True), (K.J, False)) for n in times}
        for key, down in events.get(t, ()):
            (self.on_key_press if down else self.on_key_release)(key, 0)
        super().on_update(STEP)

    def on_draw(self):
        if not self.ready:
            return
        i = self.count % FRAMES
        scene = SCENES[self.count // FRAMES % len(SCENES)]
        if i == 0:
            self.setup_scene(scene)
        start = perf_counter()
        for t in (i * 2, i * 2 + 1):
            self.input_step(scene, t)
        super().on_draw()
        self.work = (perf_counter() - start) * 1000
        self.label = scene
        self.nparticles = len(self.battle_view.particles)
        self.nbolts = len(self.combat.bolts)
        if self.count < FRAMES * len(SCENES):
            drawn = [self.actor, *self.battle_view.enemies, self.battle_view.trail]
            for sprite in drawn:
                if sprite.visible and id(sprite.texture) in self.texture_ids:
                    name, frame = self.texture_ids[id(sprite.texture)]
                    self.played.setdefault(name, set()).add(frame)
            for n, (sprite, frames, ticks, phase) in enumerate(self.ambient):
                self.played.setdefault(f"environment_{n}", set()).add(frames.index(sprite.texture))
            name = {
                ("motion", 12): "run",
                ("motion", 32): "jump",
                ("motion", 81): "roll",
                ("blade", 3): "windup",
                ("blade", 6): "cut",
                ("blade", 48): "recover",
                ("hammer", 20): "heavy-warning",
            }.get((scene, i))
            if name or i % 4 == 0:
                im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
                if name:
                    check_pixels(im)
                    im.save(self.out / (name + ".png"))
                    c = self.combat
                    self.shots[name] = dict(
                        x=self.walker.x,
                        y=self.walker.y,
                        facing=self.walker.facing,
                        motion=self.walker.action,
                        attack=c.attack,
                        age=c.age,
                        camera=[self.scroll, self.lift],
                        foes=[(e.kind, e.state, e.hp) for e in c.foes],
                        particles=self.nparticles,
                    )
                if i % 4 == 0:
                    self.reel.append(im.resize((640, 360), Image.Resampling.NEAREST))
        self.label_index = self.count
        self.count += 1

    def flip(self):
        super().flip()
        end = perf_counter()
        if not getattr(self, "ready", False) or not hasattr(self, "label_index"):
            return
        if self.label_index >= FRAMES * len(SCENES) * 2 and self.last_flip is not None:
            self.samples.append(
                [self.label, (end - self.last_flip) * 1000, self.work, self.nparticles, self.nbolts]
            )
        self.last_flip = end
        if self.count == FRAMES * len(SCENES) * (SAMPLES + 2):
            self.ready = False
            pyglet.clock.schedule_once(lambda dt: self.close(), 0)

    def save(self):
        assert len(self.samples) == FRAMES * len(SCENES) * SAMPLES, len(self.samples)
        self.reel[0].save(
            self.out / "motion.gif",
            save_all=True,
            append_images=self.reel[1:],
            duration=67,
            loop=0,
            disposal=2,
        )
        intervals = [r[1] for r in self.samples]
        report = dict(
            os=platform.platform(),
            python=platform.python_version(),
            arcade=arcade.__version__,
            gpu=self.gpu,
            opengl=self.gl,
            framebuffer=[1280, 720],
            canvas=[640, 360],
            vsync=True,
            target_hz=60,
            quality=[3, 3, 3, 3],
            enemies=3,
            samples=len(intervals),
            shots=self.shots,
            frame_ms=stats(intervals),
            mean_fps=1000 / statistics.mean(intervals),
            update_draw_submit_ms=stats([r[2] for r in self.samples]),
            particle_peak=max(r[3] for r in self.samples),
            bolt_peak=max(r[4] for r in self.samples),
            played={key: sorted(value) for key, value in self.played.items()},
            raw_columns=[
                "scene",
                "flip_interval_ms",
                "update_draw_submit_ms",
                "particles",
                "bolts",
            ],
            raw=self.samples,
        )
        (self.out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(report["frame_ms"], report["mean_fps"], report["particle_peak"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    win = Replay(out)
    win.gpu = pyglet.gl.gl_info.get_renderer()
    win.gl = pyglet.gl.gl_info.get_version()
    arcade.run()
    win.save()
