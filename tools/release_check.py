"""Offline verification of the installed game using its native window and input."""
import argparse
from importlib.metadata import version
import json
import platform
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory

import arcade
import pyglet

from game.campaign import CampaignWindow
from game.resources import ASSETS
from verify_stage4 import Route


def verify(out):
    assert arcade.__version__ == version("arcade")
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf8"))
    expected = {row["path"] for row in manifest["assets"]}
    actual = {"assets/" + p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*")
              if p.is_file() and p != ASSETS / "manifest.json"}
    if actual != expected:
        raise RuntimeError(f"Asset mismatch: {sorted(actual ^ expected)}")

    with TemporaryDirectory() as tmp:
        w = CampaignWindow(seed=17, save_dir=Path(tmp)/"profile")
        trip = Route(w, Path(tmp)/"frames")
        gpu = pyglet.gl.gl_info.get_renderer()
        driver = type(pyglet.media.get_audio_driver()).__module__
        pyglet.clock.schedule_interval(trip.drive, 1/60)
        try:
            arcade.run()
        finally:
            pyglet.clock.unschedule(trip.drive)
        kinds = {e["kind"] for e in trip.events}
        rooms = sorted({e["room"] for e in trip.events if e["run"] == 1})
        assert trip.finished and trip.run == 3 and trip.paused_once and rooms == [1,2,3,4,5]
        assert {"death", "gate", "phase", "hit", "sweep", "vent", "seal"} <= kinds
        assert "silent" not in driver and {"seal", "maul", "gate"} <= trip.audio
        saved_route = json.loads((w.store.directory/"last-route.json").read_bytes())
        assert saved_route == w.route.record() and w.store.main.is_file()
        for name in ("start", "pause", "room-4", "victory", "death"):
            (out/(name+".png")).write_bytes((trip.out/(name+".png")).read_bytes())
        report = dict(frozen=getattr(sys,"frozen",False), os=platform.platform(),
                      python=platform.python_version(), arcade=arcade.__version__, gpu=gpu,
                      framebuffer=[1280,720], assets=len(actual), route=saved_route, rooms=rooms,
                      victory_seconds=trip.victory_time, restarts=2, paused=True,
                      audio_driver=driver, playing=sorted(trip.audio), events=sorted(kinds))
        (out/"installed.json").write_text(json.dumps(report,indent=2),encoding="utf8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-install", type=Path, required=True)
    out = parser.parse_args().verify_install
    out.mkdir(parents=True, exist_ok=False)
    try:
        verify(out)
    except Exception:
        (out/"error.txt").write_text(traceback.format_exc(), encoding="utf8")
        raise SystemExit(1)
