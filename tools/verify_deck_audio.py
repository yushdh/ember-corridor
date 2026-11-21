"""Replay platform chords and melee impacts in the normal campaign window."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

import arcade
import pyglet
from verify_charge_signal import export
from game.campaign import CampaignWindow
from game.guidance import DEFAULT_KEYS
from game.motion import STEP

K = arcade.key


def check(out, encoder, verify):
    out.mkdir(parents=True, exist_ok=True)
    calls, frames, cases = [], [], {}
    with TemporaryDirectory() as directory:
        w = CampaignWindow(classic=True, save_dir=directory)
        try:
            w.on_key_press(K.ENTER, 0)
            w.on_key_release(K.ENTER, 0)
            view = w.battle_view
            play = view.sound

            def observe(name):
                before = {p for _, p in view.players}
                play(name)
                for sound, player in view.players:
                    if player not in before:
                        actual = next(n for n, s in view.sounds.items() if s is sound)
                        calls.append(dict(name=actual, scene=scene, played=True, frame=len(frames),
                                          gain=player.volume))

            view.sound = observe

            def setup():
                w.start_room(0)
                w.region_age = w.objective_age = 9
                w.guidance.reset(("move", "jump", "attack", "roll"))
                w.walker.x, w.scroll = 414, 90
                for foe in w.combat.foes:
                    foe.x, foe.patrol = 1050, (1030, 1110)

            def tick():
                w.on_update(STEP)

            for scene, offset in (("down-first", -1), ("jump-first-same-tick", 0),
                                  ("jump-first-3-ticks", 3), ("remapped", 3),
                                  ("jump-only", None), ("late-down", 14)):
                setup()
                w.controls.configure(DEFAULT_KEYS)
                jump, down = K.SPACE, K.S
                if scene == "remapped":
                    w.controls.configure(tuple({"SPACE":"UP", "S":"DOWN"}.get(n,n) for n in DEFAULT_KEYS))
                    jump, down = K.UP, K.DOWN
                deck = w.combat.surfaces[1]
                w.on_key_press(jump, 0)
                for _ in range(120):
                    tick()
                w.on_key_release(jump, 0)
                assert w.walker.support is deck
                if offset == -1:
                    w.on_key_press(down, 0)
                w.on_key_press(jump, 0)
                heights = []
                for i in range(90):
                    if i == offset:
                        w.on_key_press(down, 0)
                    if i == 16:
                        w.on_key_release(jump, 0)
                        w.on_key_release(down, 0)
                    tick()
                    heights.append(round(w.walker.y, 2))
                    if i == 24 and scene == "jump-first-3-ticks":
                        w.on_draw()
                        w.ctx.get_framebuffer_image(w.ctx.screen, components=3).save(out/"platform.png")
                cases[scene] = dict(top=deck.top, peak=max(heights), end=heights[-1],
                                    below=next((i for i,y in enumerate(heights) if y<deck.top), None))

            w.controls.configure(DEFAULT_KEYS)
            # Same spacing, weapon inputs and target positions in both recordings.
            for scene in ("miss", "combo", "hammer"):
                setup()
                if scene != "miss":
                    foe = w.combat.foes[0]
                    foe.x, foe.patrol = 451, (395, 510)
                    foe.enter("recover")
                if scene == "hammer":
                    w.on_key_press(K.KEY_2, 0)
                    w.on_key_release(K.KEY_2, 0)
                for i in range(84):
                    start = perf_counter()
                    pyglet.app.platform_event_loop.dispatch_posted_events()
                    if i == 6 or (scene == "combo" and i in (17, 31)):
                        w.on_key_press(K.J, 0)
                        w.on_key_release(K.J, 0)
                    w.on_update(1/60)
                    w.on_draw()
                    buf = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                    frames.append(buf.resize((640, 360), 0).tobytes())
                    w.flip()
                    sleep(max(0, 1/60 - (perf_counter()-start)))
                cases[scene] = [(e["action"], e["frame"]) for e in w.combat.events if e["kind"]=="hit"]
            battle_calls = [cue for cue in calls if cue["scene"] in ("miss", "combo", "hammer")]
            export(out, frames, battle_calls, encoder)
            if verify:
                for name in ("down-first", "jump-first-same-tick", "jump-first-3-ticks", "remapped"):
                    assert cases[name]["end"] == 94 and cases[name]["below"] is not None, name
                for name in ("jump-only", "late-down"):
                    assert cases[name]["end"] == 151 and cases[name]["below"] is None, name
                assert [e[0] for e in cases["combo"]] == ["cut", "liftcut", "thrust"]
                assert {s["name"] for s in calls if s["scene"] == "combo"} >= {"hit","hit_lift","hit_thrust"}
                assert "crush" in {s["name"] for s in calls if s["scene"] == "hammer"}
                assert [s["name"] for s in calls if s["scene"] == "miss"] == ["sabre"]
                cases["health"] = verify_health(w, out)
            (out/"checks.json").write_text(json.dumps(dict(cases=cases, sounds=calls), indent=2))
            print(cases)
        finally:
            w.close()


def verify_health(w, out):
    w.start_room(3)
    w.walker.x, w.scroll = 830, 520
    hook, rivet, ram = w.combat.foes
    for foe, x in ((hook, 880), (rivet, 971), (ram, 1025)):
        foe.x = x
    hook.hp //= 2
    rivet.enter("warn")
    ram.hp = 1

    def draw():
        w.sync_pose()
        w.on_draw()
        return list(w.battle_view.health_bars)

    bars = draw()
    assert len(bars) == 3
    for foe in (hook, rivet, ram):
        tex, x, y = next(bar for bar in bars if bar[1]+bar[0].width//2 == round(foe.x-w.scroll))
        assert tex.width == foe.spec.half_width*2+4
        assert y > foe.y + foe.spec.height - round(w.lift)
        lit = sum(tex.image.getpixel((i,1))[:3] == (230,162,116) for i in range(tex.width))
        assert lit == max(1, round((tex.width-2)*foe.hp/foe.spec.hp))
    assert w.battle_view.warning_badges
    w.ctx.get_framebuffer_image(w.ctx.screen, components=3).save(out/"guards.png")
    hook.x, hook.y = rivet.x, rivet.y
    overlapped = draw()
    nearby = [(tex, y) for tex,x,y in overlapped if x+tex.width//2 == round(rivet.x-w.scroll)]
    (ta, ya), (tb, yb) = sorted(nearby, key=lambda row: row[1])
    assert ya+ta.height < yb
    icon, bx, by = w.battle_view.warning_badges[0]
    assert all(by-8 >= y+tex.height or by+8 <= y for tex,y in nearby)
    hook.hp = 0
    ram.x = 1250
    assert len(draw()) == 1
    rivet.x = w.scroll + 660
    rivet.facing, rivet.aim = -1, (-1, 0)
    assert not draw()
    assert any(mark.visible and 0 < mark.center_x < 640 for mark in w.battle_view.warning_list)
    w.start_room(4)
    boss = w.combat.foes[0]
    w.walker.x = boss.x - 100
    w.scroll = round(w.walker.x - 260)
    boss.hp = boss.spec.hp // 2
    boss_bar, = draw()
    assert boss_bar[0].width == boss.spec.half_width*2+4
    w.ctx.get_framebuffer_image(w.ctx.screen, components=3).save(out/"boss.png")
    return dict(regular_widths=sorted(tex.width for tex,x,y in bars), boss_width=boss_bar[0].width)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    check(args.out, args.encoder, args.verify)
