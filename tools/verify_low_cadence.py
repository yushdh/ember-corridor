"""Present the same seed-17 inputs at two wall-clock cadences on a real Arcade window."""
import argparse
import json
import statistics
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

import arcade
import pyglet
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.combat import CHAIN_OPEN, CHAIN_RADIUS, chain_tip
from game.flame import FULL_CHARGE
from game.motion import STEP
from game.profile import ProfileStore

K = arcade.key
LEVELS = (0, 0, 2, 1)
# Held-key changes are expressed in units of the 120 Hz clock, after the room opens.
# Both rates see the same movement/release edges at shared frame boundaries.
GALLERY = [
    (0.3, (K.D,)),
    (92.3, (K.D, K.SPACE)),
    (172.3, (K.A, K.K)),
    (176.3, ()),
    (232.3, (K.D, K.L)),
    (236.3, (K.L,)),
    (288.3, ()),
    (372.3, (K.A,)),
    (408.3, (K.A, K.J)),
    (412.3, ()),
]
CROSSING = [
    (0.3, (K.D, K.L)),
    (4.3, (K.L,)),
    (64.3, ()),
    (160.3, (K.A,)),
    (196.3, (K.A, K.J)),
    (200.3, ()),
]
TAPS = {"gallery": (326.8, 327.75), "crossing": (114.35, 115.6)}


class RecordingWindow(CampaignWindow):
    def step_encounter(self, axis, moves, slot):
        super().step_encounter(axis, moves, slot)
        c, p = self.combat, self.walker
        if p.roll_age == 0:
            self.rolls.append(c.tick)
        if p.roll_age < 0 or c.tick < self.final_tap:
            return
        chain = c.foes[0]
        x, y = chain_tip(chain, c.surfaces)
        if (
            chain.state == "active"
            and abs(x - p.x) <= 11 + CHAIN_RADIUS
            and p.y + p.height < y - CHAIN_RADIUS
        ):
            self.hook.append(c.tick)
        if any(abs(b.x - p.x) <= 12 for b in c.bolts):
            self.bolt.append(c.tick)


def until(deadline):
    delay = deadline - perf_counter()
    if delay > 0:
        sleep(delay)


def clip(frames, fps, path, encoder):
    if encoder:
        command = [
            str(encoder),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "640x360",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
            "-vf",
            "scale=1280:720:flags=neighbor",
            "-c:v",
            "libx264",
            "-crf",
            "15",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path.with_suffix(".mp4")),
        ]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
            for frame in frames:
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            if proc.wait():
                raise RuntimeError("video encoder failed")
    else:
        durations = [
            10 * (round((i + 1) * 100 / fps) - round(i * 100 / fps)) for i in range(len(frames))
        ]
        frames[0].save(
            path.with_suffix(".gif"),
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
        )


def replay(w, fps, scene, out, encoder, *, early=False):
    base = w.route
    index = next(i for i, t in enumerate(base.rooms) if t.key == "gallery-west")
    if scene == "crossing":
        rooms = list(base.rooms)
        room = rooms[index].room
        guards = (room.guards[0], ("rivet", 330, 143, (250, 380)), ("ram", 198, 94, (197, 209)))
        rooms[index] = replace(rooms[index], room=replace(room, guards=guards))
        w.route = replace(base, rooms=tuple(rooms))
    w.start_room(index)
    w.route = base
    if scene == "crossing":
        w.walker.x = 166
    w.sync_pose()
    events = list(GALLERY if scene == "gallery" else CROSSING)
    down, up = TAPS[scene]
    if early:
        down, up = 321.2, 322.2
    events.extend([(down, (K.K,)), (up, ())])
    events.sort()
    w.final_tap = down
    w.rolls, w.hook, w.bolt = [], [], []
    snapshots = (
        {"charge": 288, "recovery": 328, "counter": 424}
        if scene == "gallery"
        else {"charge": 60, "signals": 64, "swing": 84, "recovery": 112, "counter": 212}
    )
    end = 432 if scene == "gallery" else 216
    group = 120 // fps
    held, cursor = set(), 0
    counts = {key: [] for key in ("full_blade", "double_warning", "open_jaw_and_aim", "bow_ready")}
    presents, frames, tap_log, work = [], [], [], []
    positions = []
    peak = 0
    w.on_draw()
    w.flip()
    # The replay clock paces swaps. A second, display-dependent vblank wait
    # would delay input delivery, especially a tap late in a 60 Hz frame.
    w.set_vsync(False)
    origin = perf_counter()
    for tick in range(group, end + 1, group):
        while cursor < len(events) and events[cursor][0] < tick:
            stamp, bindings = events[cursor]
            until(origin + stamp * STEP)
            now = perf_counter()
            target = set(bindings)
            for key in held - target:
                w.on_key_release(key, 0)
            for key in bindings:
                if key not in held:
                    w.on_key_press(key, 0)
            if stamp in (down, up):
                tap_log.append(
                    dict(
                        kind="press" if stamp == down else "release",
                        after_sim_tick=w.combat.tick,
                        ms=round((now - origin) * 1000, 2),
                    )
                )
            held, cursor = target, cursor + 1
        until(origin + tick * STEP)
        start = perf_counter()
        w.on_update(1 / fps)
        w.on_draw()
        w.ctx.finish()
        work.append((perf_counter() - start) * 1000)
        c = w.combat
        assert c.tick == tick
        assert not any(w.battle_view.flash.values())
        chain, bow = c.foes[:2]
        if c.flame.charge >= FULL_CHARGE:
            assert c.flame.light_pose(w.battle_view.levels[1])[0] == "firelight"
            counts["full_blade"].append(tick)
        if chain.state == bow.state == "warn":
            assert len(w.battle_view.warning_badges) >= 2
            counts["double_warning"].append(tick)
            if chain.age >= CHAIN_OPEN:
                counts["open_jaw_and_aim"].append(tick)
        if bow.state == "warn" and bow.age * 3 >= bow.spec.windup * 2:
            counts["bow_ready"].append(tick)
        peak = max(peak, len(w.battle_view.particles))
        if not early:
            im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
            frames.append(im.resize((640, 360), Image.Resampling.NEAREST))
            for name, snap in snapshots.items():
                if tick == snap:
                    # Encode stills after the run to keep the presentation clock steady.
                    positions.append(
                        (
                            name,
                            im,
                            [
                                round(w.scroll),
                                round(w.lift),
                                round(w.walker.x, 2),
                                round(w.walker.y, 2),
                            ],
                        )
                    )
        w.flip()
        presents.append(perf_counter())
    for key in held:
        w.on_key_release(key, 0)
    stem = f"{scene}-{fps}"
    for name, im, _ in positions:
        im.save(out / f"{stem}-{name}.png")
    if not early:
        clip(frames, fps, out / stem, encoder)
    intervals = [(b - a) * 1000 for a, b in zip(presents, presents[1:])]
    return dict(
        fps_measured=round(1000 / statistics.mean(intervals), 2),
        frames=len(presents),
        interval_median_ms=round(statistics.median(intervals), 2),
        interval_p95_ms=round(statistics.quantiles(intervals, n=100)[94], 2),
        update_draw_sync_median_ms=round(statistics.median(work), 2),
        update_draw_sync_p95_ms=round(statistics.quantiles(work, n=100)[94], 2),
        sampled_ticks=counts,
        tap=tap_log,
        rolls=w.rolls,
        hook=w.hook,
        bolt=w.bolt,
        particles_peak=peak,
        hp=c.hp,
        chain_hp=chain.hp,
        events=list(c.events),
        camera_and_player={n: pos for n, _, pos in positions},
    )


def verify(out, encoder=None, baseline=False):
    out.mkdir(parents=True, exist_ok=True)
    result = dict(
        seed=17,
        levels=LEVELS,
        vsync=False,
        physics_hz=120,
        frozen=getattr(sys, "frozen", False),
        runs={},
    )
    for scene, fps, early in (
        ("gallery", 60, False),
        ("gallery", 30, False),
        ("crossing", 60, False),
        ("crossing", 30, False),
        ("gallery", 30, True),
    ):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            store = ProfileStore(profile)
            for i, level in enumerate(LEVELS):
                store.update(setting=(i, level))
            w = RecordingWindow(seed=17, save_dir=profile)
            try:
                w.on_key_press(K.ENTER, 0)
                assert tuple(w.battle_view.levels) == LEVELS
                result.update(
                    gpu=pyglet.gl.gl_info.get_renderer(), framebuffer=w.get_framebuffer_size()
                )
                run = replay(w, fps, scene, out, encoder, early=early)
            finally:
                w.close()
            name = f"{scene}-{fps}" + ("-early" if early else "")
            result["runs"][name] = run
            print(name, run["fps_measured"], run["hp"], run["rolls"], flush=True)
    (out / "report.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    for name, run in result["runs"].items():
        missed = name == "gallery-30-early" or (baseline and name == "gallery-30")
        assert (run["hp"], run["chain_hp"]) == ((82, 68) if missed else (100, 52)), name
        assert run["particles_peak"] <= 16
        assert run["tap"][0]["after_sim_tick"] == run["tap"][1]["after_sim_tick"]
        assert run["sampled_ticks"]["full_blade"]
        if not missed:
            assert run["hook"] and run["bolt"], name
        if name.startswith("crossing"):
            assert run["sampled_ticks"]["open_jaw_and_aim"]
    for scene in ("gallery", "crossing"):
        low, high = (result["runs"][f"{scene}-{fps}"] for fps in (30, 60))
        assert abs(low["fps_measured"] - 30) < 2 and abs(high["fps_measured"] - 60) < 4
        if not baseline or scene == "crossing":
            for key in ("rolls", "events", "camera_and_player", "hook", "bolt"):
                assert low[key] == high[key], (scene, key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--encoder", type=Path)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    verify(args.out, args.encoder, args.baseline)
