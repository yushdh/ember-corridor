"""Capture the shipping window at 720p using a disposable profile and seed 17."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import arcade
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.resources import font_face
from pixel_check import check_pixels

OUT = ROOT / "docs/verification/hud"
K = arcade.key


def tap(w, key):
    w.on_key_press(key, 0)
    w.on_key_release(key, 0)


def step(w, count):
    for _ in range(count):
        w.on_update(1/60)


def shot(w, name):
    w.on_draw()
    im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
    check_pixels(im)
    im.save(OUT / (name + ".png"))
    return im


def comparison():
    canvas = Image.new("RGB", (1280, 776), "#14222b")
    pen = ImageDraw.Draw(canvas)
    face = ImageFont.truetype(font_face(), 18)
    for row, stem in enumerate(("entry", "run")):
        for col, suffix in enumerate(("-before", "")):
            with Image.open(OUT / (stem + suffix + ".png")) as im:
                canvas.paste(im.resize((640, 360), Image.Resampling.LANCZOS), (col*640, row*388+28))
            caption = ("修改前" if col == 0 else "修改后") + ("   /   首次入场" if row == 0 else "   /   奔跑至盐栈")
            pen.text((col*640+12, row*388+2), caption, font=face, fill="#edcd98")
    canvas.save(OUT / "comparison.png")


def menus(w):
    shot(w, "title")
    tap(w, K.DOWN)
    tap(w, K.ENTER)
    assert w.controls.page == "settings" and w.mode == "title"
    tap(w, K.DOWN)
    tap(w, K.RIGHT)
    assert w.battle_view.levels[1] == w.store.data.levels[1] == 3
    tap(w, K.LEFT)
    tap(w, K.ESCAPE)
    tap(w, K.UP)
    tap(w, K.ENTER)
    step(w, 60)
    shot(w, "entry")
    step(w, 150)
    w.on_key_press(K.D, 0)
    step(w, 78)
    assert round(w.walker.x, 1) == 265.7 and w.scroll == 0 and w.combat.tick == 576
    shot(w, "run")
    tap(w, K.ESCAPE)
    shot(w, "pause")
    tick = w.combat.tick
    tap(w, K.DOWN)
    tap(w, K.ENTER)
    shot(w, "character")
    tap(w, K.ESCAPE)
    tap(w, K.DOWN)
    tap(w, K.ENTER)
    tap(w, K.DOWN)
    shot(w, "settings")
    tap(w, K.ESCAPE)
    tap(w, K.F5)
    tap(w, K.ENTER)
    tap(w, K.H)
    assert w.binding_label("left") == "H"
    shot(w, "bindings")
    tap(w, K.ESCAPE)
    tap(w, K.F6)
    step(w, 1)
    assert w.combat.tick == tick+2 and not w.paused
    tap(w, K.KEY_2)
    step(w, 1)
    assert w.combat.weapon == "heavy" and w.battle_view.weapon_until > w.combat.tick
    tap(w, K.KEY_1)
    step(w, 1)
    assert w.combat.weapon == "light" and w.battle_view.weapon_until > w.combat.tick
    shot(w, "weapon")
    step(w, 110)
    assert w.combat.tick > w.battle_view.weapon_until
    w.start_room(1, w.combat)
    assert w.region_age == 0
    w.start_room(0, w.combat)
    assert w.region_age >= 2.8
    comparison()


def forge_menu(w, folder):
    from verify_stage5 import GearRoute
    import pyglet

    class FirstCrate(GearRoute):
        def drive(self, dt):
            if w.index:
                raise AssertionError("Passed the first crate")
            if w.mode == "forge":
                tap(w, K.DOWN)
                shot(w, "forge")
                tap(w, K.ENTER)
                assert w.combat.loadout.equipped == "tide" and w.store.data.shell_known
                self.finished = True
                w.close()
            else:
                if (not w.entering_objective and w.region_age >= 2.8 and 0.3 < w.objective_age < 2.5
                        and "1/2" in w.objective_text and "progress" not in self.snaps):
                    shot(w, "progress")
                    self.snaps.add("progress")
                super().drive(dt)

    run = FirstCrate(w, folder)
    pyglet.clock.schedule_interval(run.drive, 1/60)
    arcade.run()
    assert run.finished and "progress" in run.snaps


def record(w, encoder):
    command = [str(encoder), "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", "1280x720", "-r", "30", "-i", "-", "-an", "-c:v", "libx264", "-crf", "17",
               "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               str(OUT / "entry-to-pause.mp4")]
    history, last = [], None
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        for i in range(360):
            if i == 18:
                tap(w, K.ENTER)
            if i == 198:
                w.on_key_press(K.D, 0)
            if i == 267:
                w.on_key_release(K.D, 0)
                tap(w, K.J)
            if i == 303:
                tap(w, K.ESCAPE)
            step(w, 2)
            w.on_draw()
            im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
            process.stdin.write(im.tobytes())
            w.flip()
            title = w.mode == "play" and not w.paused and w.region_age < 2.8
            status = (w.mode, w.paused, title, w.guidance.active)
            if status != last or i in (197, 266, 302):
                history.append(dict(time=round(i/30, 3), mode=w.mode, paused=w.paused, title=title,
                                    lesson=w.guidance.active, stamina=round(w.walker.stamina, 2),
                                    hp=w.combat.hp, x=round(w.walker.x, 1)))
                last = status
            if i == 197:
                assert w.walker.x == 75 and w.guidance.shown == {"move"} and not w.guidance.active
            elif i == 266:
                drained = w.walker.stamina
                assert drained < 70 and w.combat.hp == 100
            elif i == 302:
                assert w.walker.stamina > drained
        process.stdin.close()
        if process.wait():
            raise RuntimeError("Video encoding failed")
    assert w.paused and len([r for r in history if r["lesson"] == "move"]) == 1
    (OUT / "timeline.json").write_text(json.dumps(history, indent=2), encoding="utf8")
    subprocess.run([str(encoder), "-loglevel", "error", "-xerror", "-i", str(OUT / "entry-to-pause.mp4"),
                    "-f", "null", "-"], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder", type=Path, help="Record using this ffmpeg executable")
    parser.add_argument("--forge", action="store_true", help="Play to the first crate")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=17, save_dir=Path(tmp))
        try:
            if args.encoder:
                record(w, args.encoder)
            elif args.forge:
                forge_menu(w, Path(tmp)/"frames")
            else:
                menus(w)
        finally:
            if not w.closed:
                w.close()


if __name__ == "__main__":
    main()
