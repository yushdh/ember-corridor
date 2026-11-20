"""Record the five campaign backdrops from the same cameras and time a separate pass."""
import argparse
import json
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.motion import STEP
from game.harbour import SKY, BAY, WHEEL, WORKS
from pixel_check import check_pixels


class HarbourCapture(CampaignWindow):
    def __init__(self, out, profile, check_art):
        self.ready = False
        super().__init__(classic=True, save_dir=profile)
        self.on_key_press(arcade.key.ENTER, 0)
        self.out = out
        self.i = 0
        self.images = []
        self.times = []
        self.submits = []
        self.last_flip = None
        self.timing = False
        self.check_art = check_art
        self.seen = {
            key: set() for key in ("sky", "bay", "wheel", *(f"room-{i+1}" for i in range(5)))
        }
        self.scene_size = len(self.scene)
        self.renderer = pyglet.gl.gl_info.get_renderer()
        self.battle_view.levels[:] = [3] * 4
        self.ready = True

    def on_update(self, dt):
        pass

    def on_draw(self):
        if not self.ready:
            return
        if self.i >= 1500:
            self.audit_frame()
            self.i += 1
            return
        room, frame = divmod(self.i, 150)
        if frame == 0:
            self.start_room(room % 5)
            self.ambient_tick = 0
            self.walker.x = (75, 120, 115, 120, 548)[room % 5]
            self.scroll = max(0, self.walker.x - 310)
        start = perf_counter()
        super().on_update(2 * STEP)
        super().on_draw()
        self.timing = room >= 5 and frame >= 10
        if self.timing:
            self.submits.append(1000 * (perf_counter() - start))
        if room < 5 and frame % 10 == 0:
            im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
            self.images.append(check_pixels(im))
            if frame == 80:
                im.save(self.out / f"room-{room+1}.png")
        self.i += 1

    def audit_frame(self):
        room, frame = divmod(self.i - 1500, 300)
        self.timing = False
        if frame == 0:
            self.start_room(room)
            assert len(self.scene) == self.scene_size
            assert all(
                sprite.visible == (i == room)
                for i, group in enumerate(self.room_decor)
                for sprite in group
            )
            self.on_key_press(arcade.key.ESCAPE, 0)
            tick = self.ambient_tick
            super().on_update(2 * STEP)
            assert self.paused and self.ambient_tick == tick
            self.on_key_release(arcade.key.ESCAPE, 0)
            self.on_key_press(arcade.key.ESCAPE, 0)
            self.on_key_release(arcade.key.ESCAPE, 0)
        super().on_update(2 * STEP)
        super().on_draw()
        tracks = dict(zip(("sky", "bay", "wheel"), self.ambient[:3]))
        tracks[f"room-{room+1}"] = next(a for a in self.ambient if a[0] is self.room_decor[room][0])
        for name, (sprite, frames, _, _) in tracks.items():
            self.seen[name].add(frames.index(sprite.texture))

    def flip(self):
        super().flip()
        if not getattr(self, "ready", False):
            return
        now = perf_counter()
        if self.timing:
            self.times.append(1000 * (now - self.last_flip))
        self.last_flip = now
        if self.i == (3000 if self.check_art else 1500):
            self.ready = False
            pyglet.clock.schedule_once(lambda dt: self.close(), 0)

    def save(self):
        assert len(self.times) == len(self.submits) == 700 and len(self.images) == 75
        self.images[0].save(
            self.out / "rooms.gif",
            save_all=True,
            append_images=self.images[1:],
            duration=[170, 160, 170] * 25,
            loop=0,
            disposal=1,
        )
        stats = dict(
            gpu=self.renderer,
            window=[1280, 720],
            samples=len(self.times),
            fps=1000 / statistics.mean(self.times),
            p95_ms=statistics.quantiles(self.times, n=100)[94],
            p99_ms=statistics.quantiles(self.times, n=100)[98],
            submit_p95_ms=statistics.quantiles(self.submits, n=100)[94],
        )
        (self.out / "timing.json").write_text(json.dumps(stats, indent=2), encoding="utf8")
        if self.check_art:
            counts = {name: len(seen) for name, seen in self.seen.items()}
            assert list(counts.values()) == [
                SKY.count,
                BAY.count,
                WHEEL.count,
                *([WORKS.count] * 5),
            ], counts
            (self.out / "animation.json").write_text(json.dumps(counts, indent=2), encoding="utf8")
        print(stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--check-art", action="store_true")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as profile:
        win = HarbourCapture(out, profile, args.check_art)
        arcade.run()
        win.save()
