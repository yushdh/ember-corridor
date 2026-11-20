"""Drive a seeded or intentionally rejected route in the production window."""
import argparse
import json
import shutil
import sys
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import arcade
import pyglet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.foundry import ledge
from game.routes import CLASSIC, ATTEMPTS, generate
from verify_stage4 import Route

OUT = ROOT / "docs/verification/stage6"


class SeedTrip(Route):
    def __init__(self, window, out):
        super().__init__(window, out)
        self.first = window.route.record()
        self.visited = []

    def observe(self):
        super().observe()
        w = self.w
        template = w.route.rooms[w.index]
        assert w.route.record() == self.first
        if self.run == 1 and (not self.visited or self.visited[-1] != template.key):
            self.visited.append(template.key)
        if self.run == 1 and w.walker.x >= 360 and template.key == "sluice-twins":
            self.snap("twin-gate")
        if self.run == 1 and template.key == "pump-steps" and w.walker.y == 201:
            self.snap("high-bridge")
        if w.mode == "play":
            saved = w.store.directory / "last-route.json"
            if self.room_snapshot is not w.combat:
                assert json.loads(saved.read_text(encoding="utf8")) == self.first
                self.room_snapshot = w.combat

    room_snapshot = None


def batch():
    from collections import Counter

    counts = Counter()
    fallback = 0
    for n in range(4096):
        first = generate(n)
        assert first.record() == generate(n).record()
        counts[tuple(t.key for t in first.rooms)] += 1
        fallback += first.fallback
    assert len(counts) == 48 and not fallback
    return dict(
        seeds=[0, 4095],
        samples=4096,
        distinct=len(counts),
        fallbacks=fallback,
        min_frequency=min(counts.values()),
        max_frequency=max(counts.values()),
    )


def failed_candidates():
    # Preserve a real floor at the objective, but move it far above a full-height jump.
    base = CLASSIC[3]
    high = ledge("孤台", 650, 760, 334)
    room = replace(base.room, surfaces=(*base.room.surfaces, high), valve=(705, high.top))
    return (*CLASSIC[:3], replace(base, room=room), CLASSIC[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.batch:
        data = batch()
        (OUT / "batch.json").write_text(json.dumps(data, indent=2), encoding="utf8")
        print(data)
        return
    out = OUT / ("fallback" if args.fallback else "seed-17")
    out.mkdir(exist_ok=True)
    failure = (
        patch("game.routes.candidate", return_value=failed_candidates())
        if args.fallback
        else nullcontext()
    )
    with TemporaryDirectory() as tmp, failure:
        window = CampaignWindow(seed=17, save_dir=Path(tmp) / "profile")
        trip = SeedTrip(window, Path(tmp) / "frames")
        trip.gpu = pyglet.gl.gl_info.get_renderer()
        pyglet.clock.schedule_interval(trip.drive, 1 / 60)
        arcade.run()
        assert trip.finished and trip.paused_once and trip.run == 3
        assert trip.visited == trip.first["templates"]
        assert trip.first["fallback"] == args.fallback
        assert trip.first["attempts"] == (ATTEMPTS if args.fallback else 1)
        events = {e["kind"] for e in trip.events}
        assert {"gate", "death", "phase", "seal", "sweep", "vent"} <= events
        for label in (
            ("victory", "pause")
            if args.fallback
            else ("start", "victory", "winch", "high-bridge", "twin-gate", "pause")
        ):
            shutil.copyfile(trip.out / (label + ".png"), out / (label + ".png"))
        data = dict(
            route=trip.first,
            visited=trip.visited,
            victory_seconds=trip.victory_time,
            restarts=2,
            events=sorted(events),
            gpu=trip.gpu,
            framebuffer=[1280, 720],
        )
        (out / "run.json").write_text(json.dumps(data, indent=2), encoding="utf8")
        print(data)


if __name__ == "__main__":
    main()
