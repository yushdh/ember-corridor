"""Time the seed-17 crossing with and without framebuffer capture, in fresh game processes."""
import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import arcade
import pyglet
from verify_low_cadence import K, LEVELS, ProfileStore, RecordingWindow, STEP, clip, replay


class FrameTrace:
    def __init__(self, w, keep):
        self.rows = []
        self.keep = keep
        self.parts = Counter()
        self.camera = {}
        self.w = w
        for obj, name in (
            (w.store, "update"),
            (w.battle_view, "sound"),
            (w, "sync_pose"),
            (w, "draw_weapon_glow"),
            (w.battle_view, "warnings"),
        ):
            self.time_call(obj, name, "save" if obj is w.store else name)
        if hasattr(w.store, "remember"):
            self.time_call(w.store, "remember", "save")

    def time_call(self, obj, name, label):
        original = getattr(obj, name)

        def measured(*args, **kwargs):
            start = perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self.parts[label] += (perf_counter() - start) * 1000

        setattr(obj, name, measured)

    def frame(
        self, tick, origin, start, updated, drawn, synced, read_start, captured, presented, previous
    ):
        def ms(later, earlier):
            return round((later - earlier) * 1000, 3)

        row = dict(
            tick=tick,
            present=ms(presented, origin),
            interval=ms(presented, previous) if previous else None,
            wake_late=ms(start, origin + tick * STEP),
            work=ms(presented, start),
            update=ms(updated, start),
            draw=ms(drawn, updated),
            gpu_wait=ms(synced, drawn),
            capture=ms(captured, read_start),
            swap=ms(presented, captured),
        )
        row.update(
            {
                k: round(self.parts[k], 3)
                for k in ("save", "sound", "sync_pose", "draw_weapon_glow", "warnings")
            }
        )
        self.parts.clear()
        self.rows.append(row)
        if tick in (60, 64, 84, 112, 212):
            w = self.w
            self.camera[tick] = [
                round(w.scroll),
                round(w.lift),
                round(w.walker.x, 2),
                round(w.walker.y, 2),
            ]

    def film(self, frames, presents, path, encoder):
        if not self.keep:
            return
        # Reproduce the measured time each framebuffer remained on screen. Rounding
        # absolute timestamps avoids cumulative rounding error. GIF uses centiseconds.
        hz = 120 if encoder else 50
        times = [round((t - presents[0]) * hz) for t in presents]
        stops = times[1:] + [times[-1] + round(hz / 30)]
        film = [im for im, begin, end in zip(frames, times, stops) for _ in range(end - begin)]
        clip(film, hz, path, encoder)


def trial(out, mode, encoder, keep):
    with TemporaryDirectory() as tmp:
        store = ProfileStore(Path(tmp))
        for i, level in enumerate(LEVELS):
            store.update(setting=(i, level))
        w = RecordingWindow(seed=17, save_dir=Path(tmp))
        try:
            w.on_key_press(K.ENTER, 0)
            assert tuple(w.battle_view.levels) == LEVELS
            trace = FrameTrace(w, keep)
            run = replay(w, 30, "crossing", out, encoder, capture=mode == "on", trace=trace)
            assert (run["hp"], run["chain_hp"], run["rolls"]) == (100, 52, [117])
            assert run["hook"] and run["bolt"] and run["sampled_ticks"]["open_jaw_and_aim"]
            assert [
                e["tick"] for e in run["events"] if e["kind"] == "hit" and e["enemy"] == "chain"
            ] == [208]
            assert [tap["after_sim_tick"] for tap in run["tap"]] == [112, 112]
            info = dict(
                frozen=getattr(sys, "frozen", False),
                run=run,
                camera=trace.camera,
                mode=mode,
                gpu=pyglet.gl.gl_info.get_renderer(),
                framebuffer=w.get_framebuffer_size(),
                arcade=arcade.__version__,
                os=platform.platform(),
            )
            (out / "run.json").write_text(json.dumps(info, indent=2), encoding="utf8")
            with (out / "frames.csv").open("w", newline="", encoding="utf8") as f:
                writer = csv.DictWriter(f, fieldnames=trace.rows[0])
                writer.writeheader()
                writer.writerows(trace.rows)
        finally:
            w.close()
        assert set(ProfileStore(Path(tmp)).data.learned) == {"attack", "move", "roll"}


def stats(values):
    cuts = statistics.quantiles(values, n=100, method="inclusive")
    return {
        k: round(v, 3)
        for k, v in (
            ("median", statistics.median(values)),
            ("p95", cuts[94]),
            ("p99", cuts[98]),
            ("max", max(values)),
        )
    }


def series(args):
    all_rows = []
    runs = []
    for i in range(args.pairs):
        for mode in ("on", "off") if i % 2 == 0 else ("off", "on"):
            folder = args.out / f"{i+1}-{mode}"
            folder.mkdir(parents=True, exist_ok=True)
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--out",
                str(folder),
                "--mode",
                mode,
            ]
            if args.encoder:
                command.extend(["--encoder", str(args.encoder)])
            if i == 0 and mode == "on":
                command.append("--keep")
            subprocess.run(command, check=True)
            info = json.loads((folder / "run.json").read_bytes())
            if runs:
                assert info["camera"] == runs[0]["camera"]
                assert info["run"]["events"] == runs[0]["run"]["events"]
            runs.append(info)
            with (folder / "frames.csv").open() as f:
                rows = [dict(pair=i + 1, mode=mode, **r) for r in csv.DictReader(f)]
            all_rows.extend(rows)
            print(
                folder.name,
                stats([float(r["interval"]) for r in rows if r["interval"]]),
                flush=True,
            )
    totals = {}
    for mode in ("on", "off"):
        sample = [r for r in all_rows if r["mode"] == mode]
        totals[mode] = {
            k: stats([float(r[k]) for r in sample if r[k]])
            for k in sample[0]
            if k not in ("tick", "present", "mode", "pair")
        }
        totals[mode]["over_40ms"] = sum(float(r["interval"] or 0) > 40 for r in sample)
    with (args.out / "frames.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0])
        writer.writeheader()
        writer.writerows(all_rows)
    (args.out / "summary.json").write_text(
        json.dumps(dict(pairs=args.pairs, totals=totals, runs=runs), indent=2), encoding="utf8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--encoder", type=Path)
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--mode", choices=("on", "off"))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if args.mode:
        args.out.mkdir(parents=True, exist_ok=True)
        trial(args.out, args.mode, args.encoder, args.keep)
    else:
        if args.pairs < 1:
            parser.error("--pairs must be positive")
        series(args)
