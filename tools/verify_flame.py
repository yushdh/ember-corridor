"""Capture one real-time-scale furnace cut through the campaign's normal input callbacks."""
import json
import sys
from pathlib import Path

import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.flame import FULL_CHARGE
from game.motion import STEP
from pixel_check import check_pixels


class Capture(CampaignWindow):
    def __init__(self, out):
        self.ready = False
        super().__init__()
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.frames = []
        self.seen = set()
        self.sounds = set()
        self.started = False
        self.whiff = True
        self.hit_frames = 0
        self.impact_frames = set()
        self.age = 0
        self.done = False
        self.ready = True
        self.on_key_press(arcade.key.ENTER, 0)
        self.on_key_press(arcade.key.L, 0)

    def on_update(self, dt):
        pass

    def on_draw(self):
        if not self.ready or self.done:
            return
        self.age += 1
        assert self.age < 290, "encounter did not complete"
        if not self.whiff and self.walker.x >= 291 and not self.started:
            self.on_key_release(arcade.key.D, 0)
            self.on_key_press(arcade.key.L, 0)
            self.started = True
        flame = self.combat.flame
        if flame.charge >= FULL_CHARGE + 16:
            self.on_key_release(arcade.key.L, 0)
        super().on_update(2 * STEP)
        super().on_draw()
        for cue, player in self.battle_view.players:
            if cue.is_playing(player):
                self.sounds.update(k for k, v in self.battle_view.sounds.items() if v is cue)
        if self.whiff:
            assert (
                not self.combat.freeze
                and not self.battle_view.shake
                and "fire_hit" not in self.sounds
            )
            if not flame.busy:
                self.whiff = False
                self.on_key_press(arcade.key.D, 0)
            return
        if self.started:
            im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
            small = check_pixels(im)
            self.frames.append(small)
            if self.combat.freeze:
                self.hit_frames += 1
                assert self.battle_view.flash.get(1, 0) == 0, "unstruck hook flashed"
            for particle in self.battle_view.particles:
                if particle.animation:
                    self.impact_frames.add(particle.animation.index(particle.sprite.texture))
            if flame.busy and flame.frame not in self.seen:
                self.seen.add(flame.frame)
                label = {2: "windup", 3: "ignition", 8: "flame-cut", 11: "embers"}.get(flame.frame)
                if label:
                    im.save(self.out / (label + ".png"))
            if not flame.busy:
                self.done = True
                pyglet.clock.schedule_once(lambda dt: self.close(), 0)

    def save(self):
        assert self.done and self.seen == set(range(14)), self.seen
        hits = [e for e in self.combat.events if e["kind"] == "hit" and e["action"] == "firecut"]
        assert len(hits) == 1 and hits[0]["hp"] == 8, hits
        assert {"ignite", "firecut", "fire_hit"} <= self.sounds, self.sounds
        assert self.hit_frames and self.impact_frames == set(range(4))
        self.frames[0].save(
            self.out / "firecut.gif",
            save_all=True,
            append_images=self.frames[1:],
            duration=[20, 20, 10] * (len(self.frames) // 3) + [20] * (len(self.frames) % 3),
            loop=0,
        )
        (self.out / "capture.json").write_text(
            json.dumps(
                dict(
                    poses=sorted(self.seen),
                    hit=hits[0],
                    frames=len(self.frames),
                    hitstop_display_frames=self.hit_frames,
                    impact_frames=sorted(self.impact_frames),
                    whiff_checked=True,
                    sounds=sorted(self.sounds),
                    framebuffer=[1280, 720],
                ),
                indent=2,
            ),
            encoding="utf8",
        )
        print("verified", len(self.frames), "frames", hits[0])


if __name__ == "__main__":
    window = Capture(ROOT / "docs/verification/firecut")
    arcade.run()
    window.save()
