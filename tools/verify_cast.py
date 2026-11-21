"""Capture matched live character encounters. Fixed starting marks, normal AI and input."""
import argparse
import json
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow
from game.resources import ASSETS
from pixel_check import check_pixels
from verify_low_cadence import clip


def inspect_poses(w, out):
    """Drive the live pose selector through both facings, separately from the timed fights."""
    seen = {}
    areas = [0, 0]
    for bank, folder in ((w.battle_view.clips, "combat"), (w.extra, "foundry")):
        for name, info in json.loads((ASSETS/folder/"clips.json").read_bytes()).items():
            if not info.get("trim_transparent"):
                continue
            with Image.open(ASSETS/folder/info["sheet"]) as sheet:
                for entry, frame in zip(info["frames"], bank[name].frames, strict=True):
                    x,y,width,height = entry["region"]
                    source = sheet.crop((x,y,x+width,y+height))
                    ax,ay = entry["anchor"]
                    offset = (ax-frame.anchor[0], ay-frame.anchor[1])
                    rebuilt = Image.new("RGBA",source.size)
                    rebuilt.paste(frame.right.image,offset)
                    assert rebuilt.tobytes() == source.tobytes(), name
                    sx,sy = entry["weapon_socket"]
                    assert frame.attachment(1) == (sx-ax, ay-sy)
                    assert frame.attachment(-1) == (ax-sx, ay-sy)
                    areas[0] += width*height
                    areas[1] += frame.right.width*frame.right.height
    (out/"atlas-cells.json").write_text(json.dumps(dict(authored=areas[0],uploaded=areas[1])))
    for room in range(5):
        w.start_room(room)
        c, p, view = w.combat, w.walker, w.battle_view
        for target, enemy in enumerate(c.foes):
            if enemy.kind in seen:
                continue
            boss = enemy.kind == "bell"
            if boss:
                states = [("idle",0),("idle",15),("walk",0),("walk",15),
                          ("warn",0),("warn",45),("active",0),("recover",0),
                          ("warn",0),("warn",55),("active",0),("recover",0),
                          ("phase",25),("dead",0),("dead",12),("dead",24),
                          ("warn",None),("active",10),("phase",4)]
            else:
                states = [("idle",0),("idle",34),("walk",0),("walk",11),("warn",0),
                          ("warn",enemy.spec.windup//2),("active",0),("recover",0),
                          ("hurt",0),("dead",0),("dead",10),("dead",25),("walk",6),("walk",17)]
            for skin in (("bell","bell_tide") if boss else (enemy.kind,)):
                if boss:
                    enemy.phase = 2 if skin == "bell_tide" else 1
                clip = view.clips[skin]
                assert len(clip.frames) == len(states)
                assert len({f.right.image.tobytes() for f in clip.frames}) == len(states)
                for facing in (-1,1):
                    for n, (state, age) in enumerate(states):
                        if boss:
                            enemy.move_name = "vent" if 8 <= n <= 11 else "sweep"
                            enemy.targets = (p.x,)
                        enemy.facing, enemy.state = facing, state
                        enemy.age = enemy.windup-5 if age is None else age
                        enemy.hp = 0 if state == "dead" else enemy.spec.hp
                        w.scroll = max(0, min(640, round(enemy.x)-320))
                        w.sync_pose()
                        sprite = view.enemies[target]
                        frame = clip.frames[n]
                        expected = frame.right if facing > 0 else frame.left
                        assert sprite.texture is expected and sprite.visible
                        alpha = expected.image.getchannel("A")
                        l,t,r,b = alpha.getbbox()
                        assert alpha.getextrema() == (0,255) and 0<l<r<alpha.width and 0<t<b<alpha.height
                        assert b <= frame.anchor[1]+1, (skin,n,b)
                        w.on_draw()
                        if facing == -1 and n in (5,11):
                            w.ctx.get_framebuffer_image(w.ctx.screen,components=3).save(out/f"{skin}-{n}.png")
                        w.flip()
                seen[skin] = 2 * len(states)
    assert set(seen) == {"hook","fork","ram","rivet","chain","bell","bell_tide"}
    w.start_room(0)
    c,p,v = w.combat,w.walker,w.battle_view
    for heavy in (False,True):
        c.weapon = "heavy" if heavy else "light"
        for action in ("hurt","death"):
            key = ("hammer_" if heavy else "") + action
            clip = v.clips[key]
            for facing in (-1,1):
                p.facing = facing
                for n, end in enumerate(clip.ends):
                    tick = round(((clip.ends[n-1] if n else 0) + end)*.06)
                    c.hp = 0 if action == "death" else 83
                    c.death_age, c.hurt = tick, (23-tick if c.hp else 0)
                    w.sync_pose()
                    frame = clip.frames[n]
                    assert w.actor.texture is (frame.right if facing>0 else frame.left)
                    w.on_draw()
                    w.flip()
            seen[key] = 2*len(clip.frames)
    (out/"pose-audit.json").write_text(json.dumps(seen,indent=2),encoding="utf8")


def capture(out, audit=False, encoder=None):
    out.mkdir(parents=True, exist_ok=True)
    shots, clocks, events, reel = {}, {}, {}, []
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=17, save_dir=tmp)
        w.set_vsync(False)
        try:
            w.on_key_press(arcade.key.ENTER, 0)
            w.on_key_release(arcade.key.ENTER, 0)
            for room, x, count in ((0, 295, 167), (1, 92, 112), (3, 198, 105),
                                   (4, 704, 294)):
                w.start_room(room)
                c, p, v = w.combat, w.walker, w.battle_view
                p.x, w.scroll = x, max(0, x - 272)
                w.guidance.reset(("move", "jump", "roll", "attack"))
                w.region_age = w.objective_age = 8
                w.ambient_tick = 0
                v.rng.seed(19)
                v.levels[:] = [2, 2, 2, 2]
                seen, times = set(), []
                for tick in range(count):
                    if room == 0:
                        if tick == 24:
                            w.on_key_press(arcade.key.D, 0)
                        if tick == 48:
                            w.on_key_release(arcade.key.D, 0)
                        if tick in (62, 76, 96):
                            w.on_key_press(arcade.key.J, 0)
                            w.on_key_release(arcade.key.J, 0)
                    if room == 4 and tick == 172:
                        # Set up the half-health variant; the AI owns the transition.
                        c.foes[0].hp = c.foes[0].spec.hp // 2
                    w.dispatch_events()
                    start = perf_counter()
                    w.on_update(1/60)
                    w.on_draw()
                    w.ctx.finish()
                    times.append(round(1000 * (perf_counter() - start), 4))
                    e = c.foes[0]
                    name = None
                    if room == 0 and tick in (10, 38, 68, 110):
                        name = f"gate-{tick}"
                    if room in (1, 3) and tick in (20, 36, 65):
                        name = f"room{room+1}-{tick}"
                    if room == 4:
                        phase = f"{e.move_name}-{e.state}-{e.phase}"
                        if phase not in seen and e.age >= (e.windup//2 + 2 if e.state == "warn" else 4):
                            name = "boss-" + phase
                            seen.add(phase)
                    if name or (room in (0, 4) and tick % 3 == 0):
                        image = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                        if name:
                            check_pixels(image)
                            image.save(out / (name + ".png"))
                            shots[name] = [tick, c.tick, round(p.x, 2), round(w.scroll, 2),
                                           e.kind, e.state, e.facing, c.hp, e.hp]
                        if room in (0, 4) and tick % 3 == 0:
                            reel.append(image.resize((640,360), Image.Resampling.NEAREST))
                    w.flip()
                clocks[str(room+1)] = times
                events[str(room+1)] = list(c.events)
            if audit:
                inspect_poses(w, out)
        finally:
            w.close()
    clip(reel, 20, out/"encounters", encoder)
    warm = [t for case in clocks.values() for t in case[8:]]
    result = dict(shots=shots, events=events, frame_ms=clocks, warm_frames=len(warm),
                  median_ms=statistics.median(warm), p95_ms=statistics.quantiles(warm,n=100)[94])
    (out/"run.json").write_text(json.dumps(result, indent=2),encoding="utf8")
    print(sorted(shots), result["median_ms"], result["p95_ms"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--encoder", type=Path)
    args = parser.parse_args()
    capture(args.out, args.audit, args.encoder)
