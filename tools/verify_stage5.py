"""Exercise the loot loop with native keys, then reopen good and damaged test profiles."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from verify_stage4 import Route
from pixel_check import check_pixels

OUT = ROOT / "docs/verification/stage5"


class GearRoute(Route):
    def __init__(self, w, out):
        super().__init__(w, out)
        self.fits = []
        self.cancelled = False
        self.wait = 0
        self.pause_test = 0
        self.saw_reset = False
        self.defeat_ready = False

    def check_defeat_restart(self):
        if self.w.index == 0:
            return False
        assert self.w.index == 1 and self.w.combat.loadout.equipped == "shell"
        if self.w.walker.y >= 147 and self.w.walker.x >= 352:
            self.defeat_ready = True
        return self.defeat_ready

    def drive(self, dt):
        w = self.w
        c = w.combat
        if self.wait:
            self.wait -= 1
            return
        if self.run == 2 and w.index == 0 and not self.saw_reset and w.mode == "play":
            assert c.loadout.ranks == {} and c.loadout.shell_known
            self.saw_reset = True
        if self.run == 3:
            assert not c.loadout.ranks and c.loadout.shell_known and self.defeat_ready
        if w.mode == "forge":
            self.hold(set())
            if not self.cancelled:
                self.snap("choice")
                self.tap("esc")
                self.cancelled = True
            else:
                choice = 3 if self.run == 2 else (1, 1, 2, 2)[w.index]
                if choice == 3:
                    self.snap("blueprint")
                if self.run == 1 and w.index == 1:
                    self.snap("upgrade")
                self.tap(str(choice))
            self.wait = 4
            return
        if w.mode == "play" and not w.paused and c.crate and c.near(w.walker, c.crate):
            self.snap("crate")
            self.hold(set())
            self.tap("e")
            self.wait = 3
            return
        if c.crate_taken and (self.run, w.index) not in [row[:2] for row in self.fits]:
            item = c.loadout.equipped
            self.fits.append((self.run, w.index, item, c.loadout.rank(item)))
            self.snap("equipped")
        if self.run == 1 and w.index == 0 and c.crate_taken and self.pause_test < 4:
            if self.pause_test == 0 or self.pause_test == 3:
                self.tap("esc")
            else:
                self.tap("f1" if self.pause_test == 1 else "f2")
            self.pause_test += 1
            self.wait = 4
            return
        super().drive(dt)

    def post(self, key, down):
        if key not in ("f1", "f2"):
            return super().post(key, down)
        import ctypes

        vk = 112 if key == "f1" else 113
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        flags = 1 | scan << 16 | (0 if down else 0xC0000000)
        assert ctypes.windll.user32.PostMessageW(self.w._hwnd, 0x100 if down else 0x101, vk, flags)

    def save(self):
        assert self.finished and self.fits == [
            (1, 0, "tooth", 1),
            (1, 1, "tooth", 2),
            (1, 2, "tide", 1),
            (1, 3, "tide", 2),
            (2, 0, "shell", 1),
        ], self.fits
        assert self.w.store.data.levels == (3, 3, 2, 2)
        assert any(e["kind"] == "death" and e["run"] == 2 for e in self.events)
        hits = [
            e
            for e in self.events
            if e["kind"] == "hit" and e["room"] == 2 and e["run"] == 1 and e["action"] == "breaker"
        ]
        assert hits
        for name in ("choice", "crate", "upgrade", "equipped", "blueprint", "victory", "death"):
            shutil.copyfile(self.out / (name + ".png"), OUT / (name + ".png"))
        report = dict(
            victory_seconds=self.victory_time,
            framebuffer=[1280, 720],
            gpu=self.gpu,
            picks=self.fits,
            settings=list(self.w.store.data.levels),
            victory_and_defeat_reset=True,
            hammer_hits=hits,
        )
        (OUT / "route.json").write_text(json.dumps(report, indent=2), encoding="utf8")


def reopen(directory, recovered):
    w = CampaignWindow(classic=True, save_dir=directory)

    def check(dt):
        w.on_draw()
        assert w.store.data.shell_known and not w.combat.loadout.ranks
        if recovered:
            # Learning a move can also be the last successful write.
            backup = w.store.backup.read_bytes()
            assert w.store.main.read_bytes() == backup
            assert list(w.battle_view.levels) == json.loads(backup)["levels"]
        else:
            assert tuple(w.battle_view.levels) == (3, 3, 2, 2)
        assert bool(w.store.notice) == recovered
        im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
        check_pixels(im)
        im.save(OUT / ("restored.png" if recovered else "relaunch.png"))
        w.close()

    pyglet.clock.schedule_once(check, 0.2)
    arcade.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reopen", type=Path)
    parser.add_argument("--recovered", action="store_true")
    args = parser.parse_args()
    if args.reopen:
        reopen(args.reopen, args.recovered)
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            w = CampaignWindow(classic=True, save_dir=profile)
            route = GearRoute(w, Path(tmp) / "frames")
            route.gpu = pyglet.gl.gl_info.get_renderer()
            pyglet.clock.schedule_interval(route.drive, 1 / 60)
            arcade.run()
            route.save()
            cmd = [sys.executable, __file__, "--reopen", str(profile)]
            subprocess.run(cmd, check=True)
            (profile / "profile.json").write_bytes(b"truncated{")
            subprocess.run(cmd + ["--recovered"], check=True)
            print("Verified five fittings, victory, defeat, relaunch and backup recovery.")
