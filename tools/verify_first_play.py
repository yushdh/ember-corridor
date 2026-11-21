"""Use real game input to verify a death, retry, classic route and first-victory timing."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from time import monotonic

import arcade
import pyglet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.first_play import FirstPlayWindow
from verify_stage5 import GearRoute


class FirstTrip(GearRoute):
    def drive(self, dt):
        w = self.w
        if monotonic() - self.start > 210:
            raise RuntimeError(f"Input route timed out in {w.combat.room.name}, mode={w.mode}")
        if w.record.attempt == 1:
            if w.mode == "title":
                self.snap("start")
                self.tap("enter")
            elif w.combat.hp:
                self.hold({"d"} if w.walker.x < 300 else set())
            else:
                self.snap("first-death")
                self.hold(set())
                self.tap("r")
            return
        if w.mode == "won":
            self.snap("victory")
            self.hold(set())
            w.close()
            return
        super().drive(dt)


def verify(out):
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        w = FirstPlayWindow(report_root=Path(tmp), source="automated")
        trip = FirstTrip(w, Path(tmp) / "frames")
        pyglet.clock.schedule_interval(trip.drive, 1 / 60)
        try:
            arcade.run()
        finally:
            pyglet.clock.unschedule(trip.drive)
        r = json.loads(w.record.path.read_bytes())
        assert r["outcome"] == "won" and r["attempts"] == 2 and r["deaths"] == 1
        assert all(r[k] > 0 for k in ("play_ms", "forge_ms", "pause_ms", "retry_wait_ms"))
        assert r["wall_ms"] == sum(r[k] for k in ("play_ms", "forge_ms", "pause_ms", "retry_wait_ms"))
        assert [entry["room"] for entry in r["rooms"] if entry["attempt"] == 2] == [
            template.room.name for template in w.route.rooms
        ]
        assert w.store.directory == w.record.path.parent / "profile"
        assert w.store.main.is_file() and w.route.seed is None
        shutil.copyfile(w.record.path, out / "automated-session.json")
        for name in ("first-death", "room-1", "choice", "pause", "victory"):
            shutil.copyfile(trip.out / (name + ".png"), out / (name + ".png"))
        print({k: v for k, v in r.items() if k not in {"rooms", "transitions"}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    verify(parser.parse_args().out)
