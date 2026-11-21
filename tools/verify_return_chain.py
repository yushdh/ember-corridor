"""Capture the shipping gallery entrance with the production update and draw paths."""
import argparse
import json
import sys
from pathlib import Path
from statistics import median, quantiles
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.combat import CHAIN_RADIUS, chain_tip

OUT = ROOT / "docs/verification/return-chain"


def cross_swords(w, index, dodge, out):
    w.start_room(index)
    c, enemy = w.combat, w.combat.foes[0]
    assert enemy.kind == "chain"
    rolled = attack_tick = counter_age = None
    overlap = []
    timeline, frames, costs = [], [], []
    snapshots = set()
    sound = False
    for n in range(160):
        if dodge and rolled is None and enemy.state == "active" and enemy.age >= 7:
            w.on_key_press(arcade.key.K, 0)
            w.on_key_release(arcade.key.K, 0)
            rolled = c.tick
        if dodge and rolled is not None and w.walker.roll_age < 0 and enemy.state == "recover" and attack_tick is None:
            direction = arcade.key.A if enemy.x < w.walker.x else arcade.key.D
            w.on_key_press(direction, 0)
            if abs(enemy.x - w.walker.x) <= 32 and w.walker.facing == (-1 if direction == arcade.key.A else 1):
                w.on_key_release(direction, 0)
                attack_tick, counter_age = c.tick, enemy.age
                w.on_key_press(arcade.key.J, 0)
                w.on_key_release(arcade.key.J, 0)
        start = perf_counter()
        w.on_update(1 / 60)
        w.on_draw()
        w.ctx.finish()
        costs.append((perf_counter()-start)*1000)
        sound |= any(s is w.battle_view.sounds["chain"] and s.is_playing(p) for s,p in w.battle_view.players)
        if not timeline or timeline[-1][0] != enemy.state:
            timeline.append((enemy.state, c.tick))
        if enemy.state == "active":
            tx, ty = chain_tip(enemy, c.surfaces)
            if abs(tx - w.walker.x) <= 11 + CHAIN_RADIUS and w.walker.y + w.walker.height < ty - CHAIN_RADIUS:
                overlap.append(dict(tick=c.tick, roll_age=w.walker.roll_age, invulnerable=w.walker.invulnerable))
        label = None
        if dodge:
            if enemy.state == "warn" and enemy.age >= 66:
                label = "open"
            elif overlap and overlap[-1]["tick"] == c.tick and w.walker.roll_age >= 6:
                label = "dodge"
            elif enemy.state == "recover" and enemy.age >= 12:
                label = "slack"
            elif enemy.state == "hurt":
                label = "counter"
        elif c.hp < 100:
            label = "contact"
        if label in snapshots:
            label = None
        if label or (dodge and n % 2 == 0):
            im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
            if label:
                im.save(out / (label + ".png"))
                snapshots.add(label)
            if dodge and n % 2 == 0:
                frames.append(im.resize((640,360), Image.Resampling.NEAREST))
        w.flip()
        if (not dodge and enemy.state == "recover") or (dodge and enemy.state == "hurt" and c.freeze == 0):
            break
    events = [ev for ev in c.events if ev.get("enemy") == "chain"]
    print(dodge, timeline, c.hp, enemy.hp, overlap, attack_tick, snapshots, events)
    if dodge:
        assert snapshots == {"open","dodge","slack","counter"} and overlap and c.hp == 100
        assert any(not sample["invulnerable"] for sample in overlap)
        assert enemy.hp == enemy.spec.hp - 16 and sum(ev["kind"] == "hit" for ev in events) == 1
        frames[0].save(out / "duel.gif", save_all=True, append_images=frames[1:], loop=0,
                       duration=([30,30,40]*len(frames))[:len(frames)])
    else:
        assert snapshots == {"contact"} and [ev["hp"] for ev in events if ev["kind"] == "hurt"] == [82]
    assert sound
    return dict(states=timeline, player_hp=c.hp, enemy_hp=enemy.hp, roll_tick=rolled, attack_tick=attack_tick,
                recovery_age_at_attack=counter_age, passes_under_head=overlap, events=events, warning_audio=sound,
                frames=len(costs), median_update_draw_finish_ms=round(median(costs),2),
                p95_update_draw_finish_ms=round(quantiles(costs,n=100)[94],2))


def verify(out):
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        window = CampaignWindow(seed=17, save_dir=Path(tmp) / "profile")
        try:
            window.on_key_press(arcade.key.ENTER, 0)
            index = next(i for i, room in enumerate(window.route.rooms) if room.key == "gallery-west")
            window.start_room(index)
            for _ in range(16):
                window.on_update(1 / 60)
                window.on_draw()
                window.flip()
            window.on_draw()
            frame = window.ctx.get_framebuffer_image(window.ctx.screen, components=3)
            frame.save(out / "after.png")
            report = dict(route=window.route.record(), room_index=index, framebuffer=window.get_framebuffer_size(),
                          frozen=getattr(sys,"frozen",False), gpu=pyglet.gl.gl_info.get_renderer(),
                          standing=cross_swords(window,index,False,out), dodge=cross_swords(window,index,True,out))
            (out / "duel.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        finally:
            window.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    verify(parser.parse_args().out)
