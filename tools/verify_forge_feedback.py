"""Inspect overlapping fire, a live warning and contact animations in the game framebuffer."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.motion import STEP
from pixel_check import check_pixels


class Inspection(CampaignWindow):
    def __init__(self, directory, output):
        self.ready = False
        super().__init__(classic=True, save_dir=directory)
        self.output = output
        self.frame_no = 0
        self.overlap = None
        self.contacts = {"cut": set(), "breaker": set()}
        self.boss_flash = set()
        self.sounds = set()
        self.poses = {name: set() for name in ("liftcut", "cast", "death")}
        self.ready = True
        self.on_key_press(arcade.key.ENTER, 0)
        self.battle_view.levels[:] = [3] * 4

    def on_update(self, dt):
        pass

    def on_draw(self):
        if not self.ready:
            return
        scene, age = divmod(self.frame_no, 72)
        if age == 0 and scene >= 3:
            self.start_room(0)
            if scene == 3:
                self.on_key_press(arcade.key.J, 0)
                self.on_key_release(arcade.key.J, 0)
            elif scene == 4:
                self.on_key_press(arcade.key.Q, 0)
            else:
                self.combat.hp = 1
                self.combat.damage_player(
                    self.walker, self.combat.foes[0], self.walker.x, self.walker.y + 30
                )
        elif age == 0:
            self.start_room(3 if scene == 0 else 4)
            self.walker.x = 830 if scene == 0 else 730
            self.scroll = self.walker.x - 310
            if scene == 0:
                hook, rivet, ram = self.combat.foes
                hook.x, hook.patrol = 910, (875, 960)
                hook.enter("recover")
                rivet.x, rivet.y, rivet.patrol = 996, 155, (850, 1002)
                ram.x = 1070
                self.on_key_press(arcade.key.L, 0)
            else:
                self.combat.foes[0].x = 778
                if scene == 2:
                    self.on_key_press(arcade.key.KEY_2, 0)
                self.on_key_press(arcade.key.J, 0)
        if scene == 0 and age == 30:
            self.on_key_release(arcade.key.L, 0)
        if scene == 3 and age == 10:
            self.on_key_press(arcade.key.J, 0)
        super().on_update(2 * STEP)
        super().on_draw()
        v = self.battle_view
        self.sounds.update(
            k
            for k, s in v.sounds.items()
            if any(cue is s and cue.is_playing(player) for cue, player in v.players)
        )
        if scene == 0:
            flame = self.combat.flame
            if self.overlap is None and flame.swing >= 0 and flame.frame == 8 and v.warning_badges:
                im = self.ctx.get_framebuffer_image(self.ctx.screen, components=3)
                check_pixels(im)
                im.save(self.output / "warning-fire.png")
                self.overlap = dict(
                    flame_frame=8,
                    warnings=[e.kind for e in self.combat.foes if e.state == "warn"],
                    badges=len(v.warning_badges),
                    particles=len(v.particles),
                )
        elif scene <= 2:
            name = "cut" if scene == 1 else "breaker"
            frames = v.contacts[scene == 2][1]
            for p in v.particles:
                if p.animation is frames:
                    self.contacts[name].add(frames.index(p.sprite.texture))
            sprite = v.enemies[0]
            for strength, bank in enumerate(v.flashes["bell"]):
                if any(sprite.texture in (f.right, f.left) for f in bank):
                    self.boss_flash.add(strength)
        else:
            name = ("liftcut", "cast", "death")[scene - 3]
            clip = self.extra[name] if name == "cast" else v.clips[name]
            self.poses[name].update(
                i for i, f in enumerate(clip.frames) if self.actor.texture is f.right
            )
        self.frame_no += 1
        if self.frame_no == 432:
            self.ready = False
            pyglet.clock.schedule_once(lambda dt: self.close(), 0)


if __name__ == "__main__":
    out = ROOT / "docs/verification/forge-visual/after"
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as directory:
        window = Inspection(directory, out)
        arcade.run()
        assert window.overlap and "rivet" in window.overlap["warnings"], window.overlap
        assert all(s == {0, 1, 2} for s in window.contacts.values()), window.contacts
        assert (
            window.boss_flash == {0, 1} and {"crush", "hit", "fire_hit", "rivet"} <= window.sounds
        )
        for key, length in (("liftcut", 7), ("cast", 6), ("death", 8)):
            assert window.poses[key] == set(range(length)), (key, window.poses[key])
        result = dict(
            overlap=window.overlap,
            contacts={k: sorted(v) for k, v in window.contacts.items()},
            poses={k: sorted(v) for k, v in window.poses.items()},
            boss_flash=sorted(window.boss_flash),
            sounds=sorted(window.sounds),
        )
        (out / "overlap.json").write_text(json.dumps(result, indent=2), encoding="utf8")
        print(result)
