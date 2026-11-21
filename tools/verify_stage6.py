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
    def __init__(self, window, out, *, survey=False):
        super().__init__(window, out)
        self.first = window.route.record()
        self.visited = []
        self.survey = survey
        self.landmarks = {}
        self.exits = []
        self.pending_exit = None

    def position_record(self):
        w = self.w
        p = w.walker
        return dict(room=w.index+1, template=w.route.rooms[w.index].key, tick=w.combat.tick,
                    x=round(p.x, 2), feet_y=round(p.y, 2), height=p.height, action=p.action,
                    support=p.support.name if p.support else None)

    def landmark(self, label, **details):
        if label not in self.landmarks:
            self.landmarks[label] = dict(self.position_record(), **details)
            self.snap(label)

    def tap(self, key):
        w = self.w
        c = w.combat
        if self.survey and self.run == 1 and key == "e" and c.near(w.walker, c.room.door):
            assert c.cleared and c.valve_open
            self.pending_exit = dict(self.position_record(), door=c.room.door)
        super().tap(key)

    def survey_room(self, template):
        w = self.w
        p, c = w.walker, w.combat
        if self.pending_exit and (self.pending_exit["room"] != w.index+1 or w.mode == "won"):
            self.exits.append(dict(self.pending_exit, destination="victory" if w.mode == "won" else template.key,
                                   arrival=[round(p.x, 2), round(p.y, 2)]))
            self.pending_exit = None
        if w.mode != "play" or w.paused:
            return
        for i, surface in enumerate(c.room.surfaces[1:], 1):
            if p.support is surface and surface.left <= p.x < surface.right:
                self.landmark(f"{template.key}-landing-{i}", surface=surface.name, top=surface.top)
            if surface.name == "泄洪闸" and abs(p.x - (surface.left+surface.right)/2) < 8:
                if p.tucked and p.y+p.height <= surface.bottom:
                    self.landmark(f"{template.key}-under-{i}", underside=surface.bottom)
        if c.room.valve and c.valve_open and c.near(p, c.room.valve):
            self.landmark("winch-open", valve=c.room.valve)

    def observe(self):
        super().observe()
        w = self.w
        template = w.route.rooms[w.index]
        assert w.route.record() == self.first
        if self.survey and self.run == 1:
            self.survey_room(template)
        if self.run == 1 and (not self.visited or self.visited[-1] != template.key):
            self.visited.append(template.key)
        if self.run == 1 and w.walker.x >= 360 and template.key == "sluice-twins":
            self.snap("twin-gate")
        if self.run == 1 and template.key == "pump-steps" and w.walker.y == 201:
            self.snap("high-bridge")
        if w.mode == "play":
            saved = w.store.directory / "last-route.json"
            if self.room_snapshot is not w.combat:
                w.store.poll(wait=True)
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fallback", action="store_true")
    mode.add_argument("--batch", action="store_true")
    parser.add_argument("--seed", type=int, default=17, help="Decimal tide-map seed")
    parser.add_argument("--output", type=Path, help="Directory for this run's evidence")
    args = parser.parse_args()
    if not 0 <= args.seed <= 0xffffffff:
        parser.error("seed must be in the range 0 to 4294967295")
    if args.batch:
        out = args.output or OUT
        out.mkdir(parents=True, exist_ok=True)
        data = batch()
        (out / "batch.json").write_text(json.dumps(data, indent=2), encoding="utf8")
        print(data)
        return
    name = f"seed-{args.seed}"
    if args.fallback:
        name = "fallback" if args.seed == 17 else f"fallback-{args.seed}"
    out = args.output or OUT / name
    out.mkdir(parents=True, exist_ok=True)
    failure = (
        patch("game.routes.candidate", return_value=failed_candidates())
        if args.fallback
        else nullcontext()
    )
    with TemporaryDirectory() as tmp, failure:
        window = CampaignWindow(seed=args.seed, save_dir=Path(tmp) / "profile")
        trip = SeedTrip(window, Path(tmp) / "frames", survey=True)
        trip.gpu = pyglet.gl.gl_info.get_renderer()
        pyglet.clock.schedule_interval(trip.drive, 1 / 60)
        arcade.run()
        assert trip.finished and trip.paused_once and trip.run == 3
        assert trip.visited == trip.first["templates"]
        assert trip.first["fallback"] == args.fallback
        assert trip.first["attempts"] == (ATTEMPTS if args.fallback else 1)
        events = {e["kind"] for e in trip.events}
        assert {"gate", "death", "phase", "seal", "sweep", "vent"} <= events
        assert [row["room"] for row in trip.exits] == [1, 2, 3, 4, 5]
        assert [row["destination"] for row in trip.exits] == trip.visited[1:] + ["victory"]
        assert "winch-open" in trip.landmarks
        if "sluice-twins" in trip.visited:
            assert {"sluice-twins-under-1", "sluice-twins-under-3"} <= trip.landmarks.keys()
        if "pump" in trip.visited:
            assert {"pump-landing-1", "pump-landing-3"} <= trip.landmarks.keys()
        labels = {"start", "victory", "winch", "pause", *trip.landmarks}
        labels.update(trip.snaps & {"high-bridge", "twin-gate"})
        for label in sorted(labels):
            shutil.copyfile(trip.out / (label + ".png"), out / (label + ".png"))
        data = dict(
            route=trip.first,
            visited=trip.visited,
            victory_seconds=trip.victory_time,
            restarts=2,
            events=sorted(events),
            gpu=trip.gpu,
            framebuffer=[1280, 720],
            input="Win32 keyboard messages", landmarks=trip.landmarks, exits=trip.exits,
        )
        (out / "run.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
        print(data)


if __name__ == "__main__":
    main()
