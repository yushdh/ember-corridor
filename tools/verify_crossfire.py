"""Record the gallery crossfire using the campaign window and normal key bindings."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from statistics import median, quantiles
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.combat import CHAIN_OPEN, CHAIN_RADIUS, chain_tip
from game.motion import STEP

# Times are 120 Hz input steps. The same inputs drive both renderer revisions.
K = arcade.key
PAIR = {87: (K.D, K.K), 88: (), 130: (K.A,), 164: (K.A, K.J), 165: ()}
ROUTE = {1: (K.D,), 95: (K.D, K.SPACE), 172: (K.D,), 173: (),
         174: (K.A,), 271: (), 336: (K.D, K.K), 337: (), 398: (K.A,),
         432: (K.A, K.J), 433: ()}


def run(window, out, staged, dodge, roll_tick=None):
    w = window
    route = w.route
    index = next(i for i, t in enumerate(route.rooms) if t.key == "gallery-west")
    if staged:
        # Keep the actual guards, cover and step; station the bow on the west step.
        template = route.rooms[index]
        chain, _, guard = template.room.guards
        room = replace(template.room, guards=(chain, ("rivet", 300, 143, (250, 380)), guard))
        rooms = list(route.rooms)
        rooms[index] = replace(template, room=room)
        w.route = replace(route, rooms=tuple(rooms))
    w.start_room(index)
    w.route = route
    if staged:
        w.walker.x = 178
    c = w.combat
    chain, bow, _ = c.foes
    keys = PAIR if staged else ROUTE
    if roll_tick is not None:
        keys = {t + roll_tick - 87: bindings for t, bindings in PAIR.items()}
    stop_inputs = 0 if staged else 271
    name = ("crossing" if staged else "gallery") + ("" if dodge else "-standing")
    held, frames, costs = set(), [], []
    crossing, clearance, bolts = [], [], []
    snap = {72: "lock", 102: "pass", 176: "counter"} if staged else {220: "high-aim", 370: "return", 444: "riposte"}
    end = 215 if roll_tick is not None else 184 if staged else 454
    for tick in range(1, end+1):
        if tick in keys and (dodge or tick <= stop_inputs):
            target = set(keys[tick])
            for key in sorted(held-target):
                w.on_key_release(key, 0)
            for key in keys[tick]:
                if key not in held:
                    w.on_key_press(key, 0)
            held = target
        start = perf_counter()
        w.on_update(STEP)
        assert c.tick == tick
        tx, ty = chain_tip(chain, c.surfaces)
        if chain.state == bow.state == "warn" and chain.age >= CHAIN_OPEN:
            dx, dy = tx-(bow.x+bow.facing*21), ty-(bow.y+30)
            along = dx*bow.aim[0]+dy*bow.aim[1]
            offset = abs(dx*bow.aim[1]-dy*bow.aim[0])
            if 0 <= along <= 190 and offset <= CHAIN_RADIUS:
                crossing.append(tick)
        p = w.walker
        if chain.state == "active" and abs(tx-p.x) <= 11+CHAIN_RADIUS and p.roll_age >= 0:
            clearance.append(tick)
        if p.roll_age >= 0 and any(abs(b.x-p.x)<=12 for b in c.bolts):
            bolts.append(tick)
        if tick % 2 == 0:
            w.on_draw()
            w.ctx.finish()
            costs.append((perf_counter()-start)*1000)
            if dodge and roll_tick is None and (tick in snap or tick % 4 == 0):
                im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                if tick in snap:
                    im.save(out / (snap[tick]+".png"))
                if tick % 4 == 0:
                    frames.append(im.resize((640,360),Image.Resampling.NEAREST))
            w.flip()
    for key in held:
        w.on_key_release(key,0)
    events = [e for e in c.events if e.get("enemy") in {"chain","rivet"}]
    if dodge and roll_tick is None:
        assert c.hp == 100 and chain.hp == 52 and clearance and bolts, (name,events,clearance,bolts)
        assert any(e["kind"]=="hit" and e["action"]=="cut" and e["enemy"]=="chain" for e in events)
        durations = ([30,30,40]*len(frames))[:len(frames)]
        frames[0].save(out/(name+".gif"),save_all=True,append_images=frames[1:],duration=durations,loop=0)
    elif not dodge:
        assert {e["enemy"] for e in events if e["kind"] in ("hurt","guarded")} == {"rivet","chain"}, events
    assert any(e["kind"]=="shot" for e in events)
    if staged:
        assert crossing and c.foes[1].y == 143
    return dict(player_hp=c.hp,chain_hp=chain.hp,events=events,open_hook_on_aim_ticks=crossing,
                roll_crosses_chain_ticks=clearance,roll_crosses_bolt_ticks=bolts,
                samples=len(costs),second_step_draw_finish_median_ms=round(median(costs),2),
                second_step_draw_finish_p95_ms=round(quantiles(costs,n=100)[94],2))


def verify(out):
    out.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=17,save_dir=Path(tmp)/"profile")
        try:
            w.on_key_press(K.ENTER,0)
            report = dict(seed=17,framebuffer=w.get_framebuffer_size(),gpu=pyglet.gl.gl_info.get_renderer(),
                          frozen=getattr(sys,"frozen",False))
            for name,staged in (("crossing",True),("gallery",False)):
                for dodge in (False,True):
                    report[name+("" if dodge else "_standing")]=run(w,out,staged,dodge)
            timings = []
            for tick in (62, 68, 87, 103, 111):
                sample = run(w,out,True,True,tick)
                timings.append(dict(roll_tick=tick, player_hp=sample["player_hp"], chain_hp=sample["chain_hp"]))
            assert [s["player_hp"] for s in timings] == [82,100,100,100,82]
            assert all(s["chain_hp"] == 52 for s in timings if s["player_hp"] == 100)
            report["roll_timing_samples"] = timings
            (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf8")
        finally:
            w.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    verify(parser.parse_args().out)
