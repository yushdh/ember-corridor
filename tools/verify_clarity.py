"""Deterministic campaign framebuffer captures for running, camera travel and a combo."""
import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import arcade
import pyglet
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.motion import STEP


class Replay(CampaignWindow):
    def __init__(self, profile, out):
        self.ready = False
        super().__init__(classic=True, save_dir=profile)
        self.out = out
        self.i = 0
        self.reel = []
        self.records = {}
        self.hits = set()
        self.on_key_press(arcade.key.ENTER, 0)
        self.ready = True

    def on_update(self, dt):
        pass

    def on_draw(self):
        if not self.ready:
            return
        scene, frame = divmod(self.i, 108)
        if frame == 0:
            self.start_room(0)
            self.ambient_tick = 0
            self.battle_view.rng.seed(19)
            self.battle_view.levels[:] = [3] * 4
            if scene == 0:
                self.walker.x = 165
                self.on_key_press(arcade.key.D, 0)
            else:
                self.walker.x = 330
                for foe, x in zip(self.combat.foes, (370, 466)):
                    foe.x, foe.patrol = x, (310, 550)
        if scene == 0 and arcade.key.D not in self.keys:
            self.on_key_press(arcade.key.D, 0)
        if scene and frame in (0, 12, 26, 40, 54, 68, 82):
            self.on_key_press(arcade.key.J, 0)
            self.on_key_release(arcade.key.J, 0)
        super().on_update(2 * STEP)
        super().on_draw()
        snapshot = None
        if scene == 0 and frame in (16, 99):
            snapshot = "run" if frame == 16 else "follow"
        if scene:
            for ev in self.combat.events:
                if ev["kind"] == "hit" and ev["action"] not in self.hits:
                    self.hits.add(ev["action"])
                    snapshot = ev["action"]
            if frame == 95:
                snapshot = "after-combo"
        if snapshot or frame % 4 == 0:
            im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
            if snapshot:
                im.save(self.out / (snapshot + ".png"))
                self.records[snapshot] = dict(
                    frame=frame,
                    x=self.walker.x,
                    y=self.walker.y,
                    scroll=self.scroll,
                    facing=self.walker.facing,
                    foes=[(e.state, e.hp) for e in self.combat.foes],
                )
            if frame % 4 == 0:
                self.reel.append(im.resize((640, 360), Image.Resampling.NEAREST))
        self.i += 1
        if self.i == 216:
            self.ready = False
            pyglet.clock.schedule_once(lambda dt: self.close(), 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as profile:
        w = Replay(profile, out)
        arcade.run()
        assert w.hits and w.records["follow"]["scroll"] > 0
        (out / "samples.json").write_text(json.dumps(w.records, indent=2), encoding="utf8")
        w.reel[0].save(
            out / "action.gif",
            save_all=True,
            append_images=w.reel[1:],
            duration=[70, 60, 70] * 18,
            loop=0,
        )
        print(w.records)
