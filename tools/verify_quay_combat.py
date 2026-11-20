"""Capture matched production frames and record which poses and collision windows played."""
import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import arcade
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.attacks import STRIKES
from game.campaign import CampaignWindow
from pixel_check import check_pixels

K = arcade.key


def inspect(window, out):
    w = window
    w.on_key_press(K.ENTER, 0)
    w.on_key_release(K.ENTER, 0)
    poses, shots, phases, audio, reel = {}, {}, {}, set(), []
    contacts = {"cut": set(), "breaker": set()}
    hit_frames = {}
    for scene in ("motion", "hammer", "cut", "liftcut", "thrust", "breaker", "fire", "charge"):
        fire_scene = scene in ("fire", "charge")
        w.start_room(3 if fire_scene else 0)
        w.guidance.reset(("move", "jump", "attack", "roll"))
        w.region_age = w.objective_age = 8
        w.battle_view.levels[:] = [3] * 4
        w.ambient_tick = 0
        w.battle_view.rng.seed(19)
        c, p, v = w.combat, w.walker, w.battle_view
        p.x = 830 if fire_scene else 330
        w.scroll = 520 if fire_scene else 28

        def tap(key):
            w.on_key_press(key, 0)
            w.on_key_release(key, 0)

        if scene in ("hammer", "breaker"):
            tap(K.KEY_2)
        if scene in ("motion", "hammer"):
            for e in c.foes:
                e.x, e.patrol = 1070, (1040, 1120)
            w.on_key_press(K.D, 0)
        elif fire_scene:
            hook, bolt, ram = c.foes
            hook.x, hook.patrol = 910, (875, 960)
            hook.enter("recover")
            bolt.x, bolt.y, bolt.patrol = 996, 155, (850, 1002)
            ram.x = 1070
            w.on_key_press(K.L, 0)
        else:
            for e in c.foes:
                e.x, e.patrol = 371, (330, 475)
                e.enter("recover")
            # Enter the requested combo link; the normal attack clock drives all its frames.
            if scene in ("cut", "breaker"):
                tap(K.J)
            else:
                c.start_attack(p, scene)
        images = []
        for i in range(147 if scene in ("motion", "hammer") else 72):
            if scene in ("motion", "hammer"):
                if i == 33:
                    w.on_key_press(K.SPACE, 0)
                if i == 47:
                    w.on_key_release(K.SPACE, 0)
                if i == 93:
                    tap(K.K)
                if i == 117:
                    w.on_key_release(K.D, 0)
                    w.on_key_press(K.A, 0)
            if fire_scene and i == (30 if scene == "fire" else 42):
                w.on_key_release(K.L, 0)
            w.on_update(1 / 60)
            w.on_draw()
            if scene in contacts:
                textures = v.contacts[scene == "breaker"][p.facing]
                for particle in v.particles:
                    if particle.animation is textures:
                        contacts[scene].add(textures.index(particle.sprite.texture))
            audio.update(
                name
                for name, s in v.sounds.items()
                if any(cue is s and s.is_playing(player) for cue, player in v.players)
            )
            key = None
            if scene in ("motion", "hammer"):
                clip = v.clips["hammer_" + p.action] if scene == "hammer" else w.clips[p.action]
                index = next(
                    n
                    for n, f in enumerate(clip.frames)
                    if w.actor.texture is (f.right if p.facing == 1 else f.left)
                )
                poses.setdefault(scene + "/" + p.action, set()).add(index)
                if i in (18, 45, 99, 132):
                    key = f"{scene}-{i}"
            elif fire_scene:
                if c.flame.busy:
                    frame = w.extra["firecut"].frames[c.flame.frame]
                    assert w.actor.texture is (frame.right if p.facing > 0 else frame.left)
                    poses.setdefault("flame", set()).add(c.flame.frame)
                if (
                    scene == "charge"
                    and c.flame.charge >= 0
                    and c.flame.frame == 3
                    and "full-charge" not in shots
                ):
                    key = "full-charge"
                active = c.flame.swing >= 0 and c.flame.frame == 8 and v.warning_badges
                if active and "fire-warning" not in shots:
                    key = "fire-warning"
            elif c.attack:
                index = STRIKES[c.attack].frame(c.age)
                frame = v.clips[c.attack].frames[index]
                assert w.actor.texture is (frame.right if p.facing > 0 else frame.left)
                assert v.trail.visible == STRIKES[c.attack].active(index)
                if v.trail.visible:
                    trail = v.clips["trail_" + c.attack].frames[index]
                    assert v.trail.texture is (trail.right if p.facing > 0 else trail.left)
                phases.setdefault(scene, set()).add(index)
                if index in (2, 3, 4, 5) and f"{scene}-{index}" not in shots:
                    key = f"{scene}-{index}"
            if key or i % 3 == 0:
                im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                if key:
                    check_pixels(im)
                    im.save(out / (key + ".png"))
                    shots[key] = dict(
                        frame=i,
                        pos=[round(p.x, 3), round(p.y, 3)],
                        facing=p.facing,
                        scroll=round(w.scroll, 3),
                        enemies=[e.hp for e in c.foes],
                        badges=len(v.warning_badges),
                        particles=len(v.particles),
                    )
                if i % 3 == 0:
                    images.append(im.resize((640, 360), Image.Resampling.NEAREST))
            w.flip()
        if scene in STRIKES:
            hits = [e for e in c.events if e["kind"] == "hit" and e.get("action") == scene]
            assert hits and all(STRIKES[scene].active(e["frame"]) for e in hits)
            assert len({(e["attack_id"], e["target"]) for e in hits}) == len(hits)
            hit_frames[scene] = [e["frame"] for e in hits]
        if scene in ("motion", "breaker", "fire"):
            reel.extend(images)
    assert "fire-warning" in shots
    assert poses["flame"] == set(range(14))
    assert all(indices == set(range(7)) for indices in phases.values())
    assert all(indices == {0, 1, 2} for indices in contacts.values())
    report = dict(
        shots=shots,
        poses={k: sorted(v) for k, v in poses.items()},
        attacks={k: sorted(v) for k, v in phases.items()},
        hit_frames=hit_frames,
        contacts={k: sorted(v) for k, v in contacts.items()},
        sounds=sorted(audio),
    )
    (out / "playback.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    reel[0].save(out / "playback.gif", save_all=True, append_images=reel[1:], duration=50, loop=0)


def compare(before, after, output):
    """Crop native window pixels at the same coordinates after checking scene state."""
    old, new = (json.loads((p / "playback.json").read_bytes())["shots"] for p in (before, after))
    for name, shot in old.items():
        for field in ("frame", "pos", "facing", "scroll", "enemies", "badges"):
            assert new[name][field] == shot[field], (name, field)

    rows = [
        ("motion-18", "奔跑 · 手腕与刃线", (495, 378, 975, 544)),
        ("hammer-45", "跃起 · 锤面离开盔顶", (530, 218, 1010, 403)),
        ("hammer-99", "翻滚 · 外侧锤面", (540, 429, 1020, 542)),
        ("cut-2", "横斩准备 · 腕点退至头盔后侧", (490, 330, 970, 535)),
        ("fire-warning", "蓄焰斩 · 火带内沿与瞄准线", (510, 181, 990, 545)),
    ]
    sheet = Image.new("RGB", (988, 57 + sum(34 + box[3] - box[1] for _, _, box in rows)), "#17232b")
    pen = ImageDraw.Draw(sheet)
    header = ImageFont.truetype("msyh.ttc", 20)
    label = ImageFont.truetype("msyh.ttc", 16)
    for x, title in ((10, "修改前"), (498, "修改后")):
        pen.text((x, 10), title, font=header, fill="#eee4cf")
    y = 45
    for name, title, box in rows:
        pen.text((10, y + 3), title, font=label, fill="#d6b885")
        y += 34
        for x, folder in ((10, before), (498, after)):
            with Image.open(folder / (name + ".png")) as frame:
                sheet.paste(frame.crop(box), (x, y))
        y += box[3] - box[1]
    sheet.save(output)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument(
        "--baseline", type=Path, help="Also produce a matched comparison with this capture."
    )
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        window = CampaignWindow(classic=True, save_dir=Path(tmp))
        try:
            inspect(window, out)
        finally:
            window.close()
    if args.baseline:
        compare(args.baseline, out, out.parent / "comparison.png")
