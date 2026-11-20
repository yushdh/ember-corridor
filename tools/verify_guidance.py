"""Record real startup and test contextual hints, rebindings and integer presentation."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.guidance import LESSONS, opportunities
from game.motion import STEP, fit_view
from game.profile import ProfileStore
from pixel_check import check_pixels

OUT = ROOT / "docs/verification/onboarding"
K = arcade.key


class Check(CampaignWindow):
    def __init__(self, case, profile):
        self.ready = False
        super().__init__(classic=True, save_dir=profile)
        self.case, self.frame, self.last = case, 0, None
        self.frames, self.stamps, self.events = [], [], []
        self.zone = set()
        self.sizes = []
        self.source_matches = []
        self.hit_tick = None
        self.start = None
        self.clock_start = perf_counter()
        self.ready = True

    def on_update(self, dt):
        if self.ready and self.case == "idle":
            super().on_update(dt)

    def tap(self, k):
        self.on_key_press(k, 0)
        self.on_key_release(k, 0)

    def grab(self):
        return self.ctx.get_framebuffer_image(self.ctx.screen, components=3)

    def done(self):
        self.ready = False
        pyglet.clock.schedule_once(lambda dt: self.close(), 0)

    def on_draw(self):
        if not self.ready:
            return
        if self.case == "idle":
            self.idle()
        elif self.case == "sizes":
            self.scaling()
        elif self.case == "warning":
            self.warning()
        elif self.case == "teardown":
            self.teardown()
        else:
            self.play()
        self.frame += 1

    def log(self, t):
        name = self.guidance.active
        if name != self.last:
            self.events.append([round(t, 3), name])
            self.last = name

    def idle(self):
        now = perf_counter()
        if self.start is None and now - self.clock_start > 0.45:
            self.tap(K.ENTER)
            self.start = now
        super().on_draw()
        age = now - self.start if self.start else -1
        self.log(age)
        if age < 3.55 and (not self.stamps or now - self.stamps[-1] >= 0.075):
            self.stamps.append(now)
            self.frames.append(self.grab())
        if age >= 10.3:
            assert self.walker.x == 75 and not self.guidance.active
            assert [v for _, v in self.events] == ["move", None], self.events
            assert self.events[-1][0] < 3, self.events
            self.grab().save(OUT / "idle-10s.png")
            self.elapsed = age
            self.done()

    def play(self):
        i = self.frame
        if i == 0:
            self.tap(K.ENTER)
        if self.case == "expert":
            if i <= 12 or i >= 110:
                self.on_key_press(K.D, 0)
            if i == 13:
                self.on_key_release(K.D, 0)
            if i == 4:
                self.on_key_press(K.SPACE, 0)
            if i == 18:
                self.on_key_release(K.SPACE, 0)
            if i == 60:
                self.tap(K.J)
            if i == 90:
                self.tap(K.K)
        elif self.case == "context" and i >= 20:
            self.on_key_press(K.D, 0)
        elif self.case == "reopen":
            if i == 10:
                self.tap(K.ESCAPE)
                self.tap(K.F5)
                self.tap(K.ENTER)
                self.tap(K.H)  # Rebind left.
                assert self.binding_label("left") == "H"
                self.tap(K.ESCAPE)
                self.tap(K.F6)
            if i == 24:
                assert self.guidance.active == "move" and self.binding_label("left") == "H"
                self.on_draw_snapshot("replay-H")
                self.on_key_press(K.A, 0)
            if i == 28:
                assert self.walker.x == 75
                self.on_key_release(K.A, 0)
                self.on_key_press(K.H, 0)
            if i == 37:
                self.on_key_release(K.H, 0)
                assert self.walker.x < 75 and "move" in self.guidance.known
            if i == 55:
                self.tap(K.ESCAPE)
                self.tap(K.F5)
                assert self.paused and self.help_open
                self.on_draw_snapshot("controls")
                self.done()
                return
        super().on_update(2 * STEP)
        super().on_draw()
        self.log(i / 60)
        self.zone.update(opportunities(self.walker, self.combat, self.combat.surfaces))
        if self.case == "expert" and i == 335:
            assert self.guidance.known == set(LESSONS) and not self.guidance.shown, self.events
            assert {"jump", "attack", "roll"} <= self.zone, self.zone
            self.done()
        if self.case == "context" and i == 295:
            assert self.guidance.shown == set(LESSONS), self.events
            self.start_room(1)
            assert not self.guidance.active and self.guidance.shown == set(LESSONS)
            self.done()
        if self.case == "reopen" and i == 8:
            assert self.guidance.known == set(LESSONS) and not self.guidance.shown

    def on_draw_snapshot(self, name):
        super().on_draw()
        self.grab().save(OUT / (name + ".png"))

    def teardown(self):
        self.tap(K.ENTER)
        super().on_update(2*STEP)
        assert self.guidance.active == "move"
        self.start_room(1)
        assert self.guidance.active is None and "move" in self.guidance.shown
        self.tap(K.ESCAPE)
        self.tap(K.F6)
        super().on_update(2*STEP)
        assert self.guidance.active == "move"
        self.combat.hp = 1
        self.combat.damage_player(self.walker,self.combat.foes[0],self.walker.x,self.walker.y)
        super().on_update(2*STEP)
        assert not self.combat.hp and self.guidance.active is None
        self.events = ["visible_before_room_change", "cleared_on_room_change",
                       "visible_before_lethal_hit", "cleared_on_death"]
        self.done()

    def warning(self):
        if self.frame == 0:
            self.tap(K.ENTER)
            self.walker.x = 330
            for foe, x in zip(self.combat.foes, (370, 470)):
                foe.x, foe.patrol = x, (310, 550)
            self.battle_view.levels[:] = [3] * 4
        if self.frame in (0, 12):
            self.tap(K.J)
        super().on_update(2 * STEP)
        super().on_draw()
        for ev in self.combat.events:
            if ev["kind"] == "hit":
                self.hit_tick = ev["tick"]
        if (
            self.hit_tick is not None
            and self.combat.foes[1].state == "warn"
            and self.battle_view.warning_badges
        ):
            assert not self.battle_view.trail.visible and not self.battle_view.particles
            self.events.append(
                dict(
                    hit_tick=self.hit_tick,
                    warn_tick=self.combat.tick,
                    particles=0,
                    trail=False,
                    badges=len(self.battle_view.warning_badges),
                )
            )
            self.grab().save(OUT / "next-warning.png")
            self.done()
        assert self.frame < 300, "expected the second guard to telegraph"

    def scaling(self):
        targets = [(1280, 720), (1920, 1080), (1366, 768)]
        index = self.frame // 12
        if self.frame == 0:
            self.tap(K.ENTER)
            self.walker.x = 335
        self.on_key_press(K.D, 0)
        if self.frame % 12 == 0:
            self.set_size(*targets[index])
        super().on_update(2 * STEP)
        super().on_draw()
        if self.frame % 12 == 10:
            image = self.grab()
            assert image.size == targets[index], image.size
            check_pixels(image)
            x, y, w, h = fit_view(*image.size)
            scale = w // 640
            hud = image.crop(
                (
                    x + 10 * scale,
                    image.height - y - h + 10 * scale,
                    x + 171 * scale,
                    image.height - y - h + 49 * scale,
                )
            )
            assert ImageChops.difference(
                hud,
                hud.resize((161, 39), Image.Resampling.NEAREST).resize(
                    hud.size, Image.Resampling.NEAREST
                ),
            ).getbbox()
            self.present_world()
            world = self.ctx.get_framebuffer_image(self.world_buffer, components=3)
            native = world.resize((w, h), Image.Resampling.NEAREST)
            expected = Image.new("RGB", image.size, (12, 19, 27))
            expected.paste(native, (x, image.height - y - h))
            assert not ImageChops.difference(
                self.grab(), expected
            ).getbbox(), "world presentation mismatch"
            # Isolate the live actor draw so a foreground post or warning badge cannot
            # hide source texels in the sampler comparison.
            with self.camera.activate():
                self.world_buffer.clear(color=(12, 19, 27, 255))
                self.people.draw(pixelated=True)
                world = self.ctx.get_framebuffer_image(self.world_buffer, components=3)
            source = self.actor.texture.image.convert("RGBA")
            left = round(self.actor.center_x - source.width / 2)
            top = 360 - round(self.actor.center_y + source.height / 2)
            samples = [
                (x, y)
                for x in range(source.width)
                for y in range(source.height)
                if source.getpixel((x, y))[3] == 255
            ]
            matches = sum(
                world.getpixel((left + x, top + y)) == source.getpixel((x, y))[:3]
                for x, y in samples
            )
            assert matches == len(samples), (matches, len(samples))
            self.source_matches.append([matches, len(samples)])
            super().on_draw()
            self.sizes.append([*image.size, scale, x, y])
            if index == 2:
                self.done()


def run(case, profile, encoder=None):
    w = Check(case, profile)
    arcade.run()
    report = dict(
        events=w.events,
        learned=sorted(w.guidance.known),
        shown=sorted(w.guidance.shown),
        zones=sorted(w.zone),
    )
    if case == "idle":
        duration = [max(10, round((b - a) * 100) * 10) for a, b in zip(w.stamps, w.stamps[1:])] + [
            120
        ]
        w.frames[0].save(
            OUT / "tutorial.gif",
            save_all=True,
            append_images=w.frames[1:],
            duration=duration,
            loop=0,
            disposal=1,
        )
        if encoder:
            with TemporaryDirectory() as frames:
                folder = Path(frames)
                listing = []
                for i, (frame, ms) in enumerate(zip(w.frames, duration)):
                    name = f"frame-{i}.png"
                    frame.save(folder / name)
                    listing.extend([f"file '{name}'", f"duration {ms/1000:.3f}"])
                listing.append(f"file '{name}'")
                manifest = folder / "frames.txt"
                manifest.write_text("\n".join(listing), encoding="ascii")
                subprocess.run(
                    [
                        str(encoder),
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-f",
                        "concat",
                        "-i",
                        str(manifest),
                        "-vf",
                        "fps=30",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "16",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(OUT / "tutorial.mp4"),
                    ],
                    check=True,
                )
        report["wait_seconds"] = round(w.elapsed, 3)
    if case == "sizes":
        report["framebuffer_scale_border"] = w.sizes
        report["opaque_actor_texels_matched"] = w.source_matches
    if case == "reopen":
        saved = ProfileStore(profile).data
        assert set(saved.learned) == set(LESSONS) and saved.bindings[0] == "H"
        report["persisted_after_replay"] = list(saved.learned)
        report["saved_left_key"] = saved.bindings[0]
    (OUT / (case + ".json")).write_text(json.dumps(report, indent=2), encoding="utf8")
    print(case, report)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=("idle", "expert", "reopen", "context", "sizes", "warning", "teardown"))
    ap.add_argument("--profile", type=Path)
    ap.add_argument(
        "--encoder", type=Path, help="Optional ffmpeg binary for a full-color MP4 of idle"
    )
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.profile:
        run(args.case, args.profile, args.encoder)
    else:
        with TemporaryDirectory() as tmp:
            run(args.case, tmp, args.encoder)
