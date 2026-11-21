"""Repeat the seed-17 entrance, west gallery duel, lethal enemy attacks and R in one window."""
import argparse
import csv
import gc
import gzip
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import get_ident
from time import perf_counter

import arcade
import pyglet
from PIL import Image
from profile_crossing import FrameTrace, stats
from verify_low_cadence import (
    GALLERY,
    K,
    LEVELS,
    ProfileStore,
    RecordingWindow,
    STEP,
    TAPS,
    clip,
    until,
)
from verify_stage4 import Route
from game import ui

FPS = 30
KEYS = {"enter": K.ENTER, "space": K.SPACE, "2": K.KEY_2}


class DoorPilot(Route):
    """Use the existing route follower for room one, with the starting short blade."""

    def post(self, name, down):
        key = KEYS.get(name, getattr(K, name.upper(), None))
        (self.w.on_key_press if down else self.w.on_key_release)(key, 0)

    def snap(self, label):
        pass

    def tap(self, name):
        if name == "e" and self.w.walker.stamina < 100:
            return
        super().tap(name)


def run(out, seconds, encoder):
    out.mkdir(parents=True, exist_ok=True)
    rows, fights, writes, tapes = [], [], [], {}
    with TemporaryDirectory() as tmp:
        directory = Path(tmp)
        store = ProfileStore(directory)
        for i, level in enumerate(LEVELS):
            store.update(setting=(i, level))
        w = RecordingWindow(seed=17, save_dir=directory)
        w.rolls, w.bolt, w.hook, w.final_tap = [], [], [], float("inf")
        pilot = DoorPilot(w, directory / "unused", blade_detour=True)
        trace = FrameTrace(w, False)
        original_raster = ui.raster
        for obj, name in (
            (w, "start_room"),
            (w, "prepare_run"),
            (w, "record_run"),
            (w.battle_view, "draw_hud"),
            (w, "present_world"),
            (w.ctx.default_atlas, "resize"),
            (w.ctx.default_atlas, "rebuild"),
            (w.ctx.default_atlas, "write_image"),
            (ui, "raster"),
            (w.controls, "draw_lesson"),
            (w.battle_view, "draw_badges"),
        ):
            trace.time_call(obj, name, name)
        origin = perf_counter()
        ui_thread = get_ident()
        collecting = {}

        def observe_gc(phase, info):
            if get_ident() != ui_thread:
                return
            gen = info["generation"]
            if phase == "start":
                collecting[gen] = perf_counter()
            elif gen in collecting:
                trace.parts["gc"] += (perf_counter() - collecting.pop(gen)) * 1000

        def watch_background(name):
            fn = getattr(w.store, name)

            def logged(*args, **kwargs):
                start = perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    writes.append(
                        dict(
                            kind=name,
                            start=round(start - origin, 5),
                            end=round(perf_counter() - origin, 5),
                            main=get_ident() == ui_thread,
                        )
                    )

            setattr(w.store, name, logged)

        watch_background("_commit")
        if hasattr(w.store, "_write_route"):
            watch_background("_write_route")
        w.set_vsync(False)
        atlas_at_open = w.ctx.default_atlas.size
        w.on_draw()
        w.flip()
        trace.parts.clear()
        origin = previous = perf_counter()
        deadline = origin
        gc.callbacks.append(observe_gc)
        cycle = 1
        cycle_begin = 0
        cycle_time = origin
        film_cycle = "first"
        tape = []
        restarts = doors = 0
        held = set()
        completed = False
        try:
            while not completed:
                deadline += 1 / FPS
                c = w.combat
                # Both edges of the recovery tap arrive between successive updates.
                short = w.index == 1 and c.tick == 324
                if short:
                    down, up = TAPS["gallery"]
                    until(deadline - (328 - down) * STEP)
                    press = perf_counter()
                    w.on_key_press(K.K, 0)
                    until(deadline - (328 - up) * STEP)
                    w.on_key_release(K.K, 0)
                    tap_ms = (perf_counter() - press) * 1000
                until(deadline)
                start = perf_counter()
                w.dispatch_events()
                if w.has_exit or w.closed:
                    raise InterruptedError("Game window closed during the soak")
                pumped = perf_counter()
                action = "play"
                was = w.index
                if w.mode == "title":
                    pilot.tap("enter")
                    action = "start"
                    pilot.jump_until = -1
                elif not c.hp and c.death_age >= 48:
                    assert was == 1 and len(fights) == cycle
                    pilot.hold(set())
                    pilot.tap("r")
                    assert w.index == 0 and w.combat.hp == 100
                    pilot.counter = 0
                    pilot.jump_until = -1
                    restarts += 1
                    action = "restart"
                elif w.index == 0:
                    pilot.counter += 1
                    pilot.drive_room()
                if was == 0 and w.index == 1:
                    assert c.cleared and c.valve_open and w.route.rooms[1].key == "gallery-west"
                    doors += 1
                    held.clear()
                    w.rolls, w.hook, w.bolt, w.final_tap = [], [], [], 326
                    entry_hp = w.combat.hp
                    action = "door"
                if w.index == 1:
                    c = w.combat
                    for moment, names in GALLERY:
                        if c.tick == int(moment):
                            target = set(names)
                            for key in held - target:
                                w.on_key_release(key, 0)
                            for key in names:
                                if key not in held:
                                    w.on_key_press(key, 0)
                            held = target
                    if c.tick >= 432 and c.hp:
                        # After the validated counter, stay within enemy reach until killed.
                        guard = c.foes[0]
                        keys = set()
                        if w.walker.x > guard.x + 34:
                            keys.add("a")
                        elif w.walker.x < guard.x - 34:
                            keys.add("d")
                        pilot.hold(keys)
                driven = perf_counter()
                w.on_update(1 / FPS)
                updated = perf_counter()
                w.on_draw()
                drawn = perf_counter()
                w.ctx.finish()
                synced = perf_counter()
                c = w.combat
                capture = bool(film_cycle) and (
                    action == "restart"
                    or (w.index == 0 and c.cleared and w.walker.x > c.room.door[0] - 90)
                    or (w.index == 1 and (c.tick <= 448 or not c.hp))
                )
                if capture:
                    im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
                    tape.append(im.resize((640, 360), Image.Resampling.NEAREST))
                captured = perf_counter()
                w.flip()
                presented = perf_counter()

                def ms(a, b):
                    return round(1000 * (a - b), 3)

                row = dict(
                    frame=len(rows) + 1,
                    s=round(presented - origin, 4),
                    cycle=cycle,
                    room=w.index + 1,
                    tick=c.tick,
                    action=action,
                    capture=int(capture),
                    interval=ms(presented, previous),
                    late=ms(start, deadline),
                    pump=ms(pumped, start),
                    input=ms(driven, pumped),
                    update=ms(updated, driven),
                    draw=ms(drawn, updated),
                    gpu=ms(synced, drawn),
                    readback=ms(captured, synced),
                    swap=ms(presented, captured),
                )
                for name in (
                    "record_run",
                    "prepare_run",
                    "start_room",
                    "save",
                    "sync_pose",
                    "sound",
                    "draw_hud",
                    "present_world",
                    "warnings",
                    "draw_weapon_glow",
                    "resize",
                    "rebuild",
                    "raster",
                    "write_image",
                    "draw_lesson",
                    "draw_badges",
                    "gc",
                ):
                    row[name] = round(trace.parts[name], 3)
                trace.parts.clear()
                rows.append(row)
                previous = presented
                if w.index == 1 and c.tick == 432:
                    hits = [e for e in c.events if e["kind"] == "hit" and e.get("enemy") == "chain"]
                    fight = dict(
                        cycle=cycle,
                        hp_in=entry_hp,
                        hp_out=c.hp,
                        rolls=list(w.rolls),
                        hook=list(w.hook),
                        bolt=list(w.bolt),
                        tap_ms=round(tap_ms, 3),
                        hits=hits,
                        chain_hp=c.foes[0].hp,
                    )
                    assert (
                        c.hp == entry_hp == 100
                        and w.rolls == [173, 332]
                        and w.hook == list(range(332, 338))
                        and w.bolt == list(range(344, 352))
                        and hits
                        and hits[-1]["tick"] == 420
                        and c.foes[0].hp == 52
                    ), fight
                    fights.append(fight)
                if action == "restart":
                    worst = max(rows[cycle_begin:], key=lambda r: r["interval"])
                    print(
                        f"cycle {cycle}, {presented-origin:.1f}s, {len(rows)} frames, "
                        f"max {worst['interval']} ms at {worst['frame']} ({worst['action']})",
                        flush=True,
                    )
                    if tape:
                        tapes[film_cycle] = tape
                        tape = []
                    completed = presented - origin >= seconds
                    film_cycle = (
                        "late"
                        if seconds >= 120
                        and seconds - (presented - origin) <= 2 * (presented - cycle_time)
                        else None
                    )
                    cycle_time, cycle_begin = presented, len(rows)
                    cycle += 1
                    w.final_tap = float("inf")
                if c.tick > 120 * 100:
                    raise RuntimeError(
                        (cycle, w.index, c.tick, c.hp, w.walker.x, w.walker.y, c.room.door)
                    )
                # Avoid a burst of synthetic catch-up frames after an OS interruption.
                deadline = max(deadline, presented - 1 / FPS)
        finally:
            ui.raster = original_raster
            gc.callbacks.remove(observe_gc)
            gpu = pyglet.gl.gl_info.get_renderer()
            atlas_at_close = w.ctx.default_atlas.size
            framebuffer = w.get_framebuffer_size()
            w.close()
            if rows:
                with gzip.open(out / "frames.csv.gz", "wt", newline="", encoding="utf8") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0])
                    writer.writeheader()
                    writer.writerows(rows)
        data = ProfileStore(directory).data
        assert set(data.learned) == {"attack", "jump", "move", "roll"} and data.levels == LEVELS
        assert json.loads((directory / "last-route.json").read_bytes()) == w.route.record()
        report = dict(
            seed=17,
            fps=FPS,
            levels=LEVELS,
            gpu=gpu,
            seconds=round(previous - origin, 3),
            frozen=getattr(sys, "frozen", False),
            framebuffer=framebuffer,
            atlas_at_open=atlas_at_open,
            atlas_at_close=atlas_at_close,
            frames=len(rows),
            doors=doors,
            restarts=restarts,
            fights=fights,
            writes=writes,
            learned=data.learned,
            route=w.route.record(),
            intervals=stats([r["interval"] for r in rows]),
            over40=sum(r["interval"] > 40 for r in rows),
            slowest=sorted(rows, key=lambda r: r["interval"], reverse=True)[:12],
            transitions=[r for r in rows if r["action"] != "play"],
        )
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
        for name, frames in tapes.items():
            clip(frames, FPS, out / name, encoder)
        print(report["intervals"], report["over40"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--encoder", type=Path)
    args = parser.parse_args()
    run(args.out, args.seconds, args.encoder)
