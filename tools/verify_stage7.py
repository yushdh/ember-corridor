"""Exercise the tide fork in its shipping room and replay seed 17 to the bell."""
import argparse
import json
import shutil
import statistics
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet
from PIL import Image

from verify_stage6 import CampaignWindow, ROOT, SeedTrip
from pixel_check import check_pixels

OUT = ROOT / "docs/verification/stage7"


def check_cast(w, index):
    w.start_room(index)
    e = w.combat.foes[0]
    v = w.battle_view
    variants = (v.clips["fork"].frames, *v.flashes["fork"])
    observed = set()
    ready = False
    for n in range(500):
        ready |= e.state == "recover"
        distance = e.x - w.walker.x
        if n >= 25 and distance > (32 if ready else 55) and arcade.key.D not in w.keys:
            w.on_key_press(arcade.key.D, 0)
        if distance <= (32 if ready else 55):
            w.on_key_release(arcade.key.D, 0)
            if ready and n % 10 == 0:
                w.on_key_press(arcade.key.J, 0)
                w.on_key_release(arcade.key.J, 0)
        w.on_update(1 / 60)
        w.on_draw()
        sp = v.enemies[0]
        for frames in variants:
            for i, frame in enumerate(frames):
                if sp.visible and sp.alpha and sp.texture is (frame.right if e.facing > 0 else frame.left):
                    observed.add(i)
        if e.state == "warn" and 40 <= e.age < 42:
            w.ctx.get_framebuffer_image(w.ctx.screen, components=3).save(OUT / "brace.png")
        w.flip()
        if not e.hp:
            break
    return observed


def duel(window):
    w = window
    w.on_key_press(arcade.key.ENTER, 0)
    index = next(i for i, t in enumerate(w.route.rooms) if t.key == "sluice-twins")
    frames, costs, paths = [], [], {}
    audio_played = False
    observed = set()
    for jump in (False, True):
        w.start_room(index)
        w.walker.x = 235
        c = w.combat
        enemy = c.foes[0]
        assert enemy.kind == "fork"
        timeline = []
        jumped = attacked = False
        for n in range(94):
            if jump and not jumped and enemy.state == "warn" and enemy.age >= 47:
                w.on_key_press(arcade.key.SPACE, 0)
                jumped = True
            if jumped and w.walker.vy < 0:
                w.on_key_release(arcade.key.SPACE, 0)
            if jump and not attacked and enemy.state == "recover" and w.walker.support:
                w.on_key_press(arcade.key.J, 0)
                attacked = True
            start = perf_counter()
            w.on_update(1 / 60)
            w.on_draw()
            w.ctx.finish()
            costs.append((perf_counter() - start) * 1000)
            for i, frame in enumerate(w.battle_view.clips["fork"].frames):
                if w.battle_view.enemies[0].texture is frame.left:
                    observed.add(i)
            audio_played |= any(s is w.battle_view.sounds["fork"] and s.is_playing(p)
                                for s, p in w.battle_view.players)
            if not timeline or timeline[-1][0] != enemy.state:
                timeline.append((enemy.state, c.tick))
            label = None
            if not jump and n == 7:
                label = "after"
            if jump and enemy.state == "active" and "jump" not in paths:
                label = "jump"
            if jump and enemy.state == "hurt" and "counter" not in paths:
                label = "counter"
            if label or (jump and n % 2 == 0):
                im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                if label:
                    check_pixels(im)
                    im.save(OUT / (label + ".png"))
                    paths[label] = c.tick
                if jump and n % 2 == 0:
                    frames.append(im.resize((640, 360), Image.Resampling.NEAREST))
            w.flip()
        if jump:
            assert jumped and attacked and c.hp == 100 and enemy.hp < enemy.spec.hp
            assert any(ev["kind"] == "hit" and ev["enemy"] == "fork" for ev in c.events)
        else:
            assert [e["hp"] for e in c.events if e["kind"] == "hurt"] == [84]
        print("jump" if jump else "standing", timeline, c.hp, enemy.hp)
    assert set(paths) == {"jump", "after", "counter"} and audio_played
    observed |= check_cast(w, index)
    assert observed == set(range(10)), observed
    frames[0].save(OUT / "duel.gif", save_all=True, append_images=frames[1:],
                   duration=[30, 30, 40] * (len(frames)//3) + [30, 30][:len(frames)%3], loop=0)
    return dict(gpu=pyglet.gl.gl_info.get_renderer(), framebuffer=list(w.get_framebuffer_size()),
                poses=paths, standing_hp=84, jumping_hp=c.hp, counter_enemy_hp=enemy.hp,
                warning_audio_playing=audio_played, frames_seen=sorted(observed), samples=len(costs),
                update_draw_finish_ms_median=round(statistics.median(costs), 2),
                update_draw_finish_ms_p95=round(statistics.quantiles(costs, n=100)[94], 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=17, save_dir=Path(tmp) / "profile")
        if args.route:
            trip = SeedTrip(w, Path(tmp) / "frames")
            pyglet.clock.schedule_interval(trip.drive, 1 / 60)
            arcade.run()
            assert trip.finished and trip.paused_once and trip.visited == trip.first["templates"]
            assert trip.run == 3 and {"phase", "death", "gate", "seal"} <= {ev["kind"] for ev in trip.events}
            assert any(ev.get("enemy") == "fork" and ev.get("hp") == 0 for ev in trip.events)
            shutil.copyfile(trip.out / "victory.png", OUT / "victory.png")
            result = dict(route=trip.first, visited=trip.visited, victory_seconds=trip.victory_time,
                          restarts=2, combat_audio=sorted(trip.audio))
        else:
            try:
                result = duel(w)
            finally:
                w.close()
        (OUT / ("route.json" if args.route else "duel.json")).write_text(
            json.dumps(result, indent=2), encoding="utf8")
        print(result)


if __name__ == "__main__":
    main()
