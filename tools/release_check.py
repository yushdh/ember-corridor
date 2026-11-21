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


def verify(out, blade_detour=False, low_tour=False):
    assert arcade.__version__ == version("arcade")
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf8"))
    expected = {row["path"] for row in manifest["assets"]}
    actual = {"assets/" + p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*")
              if p.is_file() and p != ASSETS / "manifest.json"}
    if actual != expected:
        raise RuntimeError(f"Asset mismatch: {sorted(actual ^ expected)}")

    with TemporaryDirectory() as tmp:
        if blade_detour:
            from game.first_play import FirstPlayWindow
            w = FirstPlayWindow(report_root=Path(tmp), source="automated")
        else:
            profile_path = Path(tmp)/"profile"
            if low_tour:
                from verify_low_cadence import LEVELS, ProfileStore
                store = ProfileStore(profile_path)
                for i, level in enumerate(LEVELS):
                    store.update(setting=(i, level))
            w = CampaignWindow(seed=17, save_dir=profile_path)
        if low_tour:
            w.set_update_rate(1/30)
            w.set_draw_rate(1/30)
        atlas = w.ctx.default_atlas
        initial_size = atlas.size
        trip = Route(w, Path(tmp)/"frames", blade_detour=blade_detour)
        gpu = pyglet.gl.gl_info.get_renderer()
        trip.gpu = gpu
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
        assert "silent" not in driver and {"seal", "sabre" if blade_detour else "maul", "gate"} <= trip.audio
        saved_route = json.loads((w.store.directory/"last-route.json").read_bytes())
        assert saved_route == w.route.record() and w.store.main.is_file()
        evidence = ["start.png", "pause.png", "room-4.png", "victory.png", "death.png"]
        if blade_detour:
            trip.save()
            evidence.extend(("locked-door.png", "locked-objective.png", "west-step.png", "winch.png",
                             "valve-open.png", "first-victory.json", "run.json", "route.gif"))
        for name in evidence:
            (out/name).write_bytes((trip.out/name).read_bytes())
        report = dict(frozen=getattr(sys,"frozen",False), os=platform.platform(),
                      python=platform.python_version(), arcade=arcade.__version__, gpu=gpu,
                      framebuffer=[1280,720], assets=len(actual), route=saved_route, rooms=rooms,
                      victory_seconds=trip.victory_time, restarts=2, paused=True,
                      audio_driver=driver, playing=sorted(trip.audio), events=sorted(kinds))
        if low_tour:
            report.update(fps_cap=30, levels=list(w.battle_view.levels),
                          atlas_at_open=initial_size, atlas_at_close=atlas.size)
        (out/"installed.json").write_text(json.dumps(report,indent=2),encoding="utf8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-install", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--blade-detour", action="store_true")
    modes.add_argument("--forge-preview", action="store_true")
    modes.add_argument("--return-chain", action="store_true")
    modes.add_argument("--crossfire", action="store_true")
    modes.add_argument("--flame-crossfire", action="store_true")
    modes.add_argument("--low-cadence", action="store_true")
    modes.add_argument("--frame-pacing", action="store_true")
    modes.add_argument("--gallery-soak", action="store_true")
    modes.add_argument("--low-tour", action="store_true")
    parser.add_argument("--soak-seconds", type=int, help="minimum duration of the gallery soak")
    args = parser.parse_args()
    if args.soak_seconds is not None and (not args.gallery_soak or args.soak_seconds < 1):
        parser.error("--soak-seconds requires --gallery-soak and a positive duration")
    out = args.verify_install
    out.mkdir(parents=True, exist_ok=False)
    try:
        if args.gallery_soak:
            from soak_gallery import run as soak
            soak(out, args.soak_seconds or 600, None)
        elif args.frame_pacing:
            from profile_crossing import trial
            for mode in ("on", "off"):
                folder = out / mode
                folder.mkdir()
                trial(folder, mode, None, False)
        elif args.low_cadence:
            from verify_low_cadence import verify as verify_cadence
            verify_cadence(out)
        elif args.flame_crossfire:
            from verify_flame_crossfire import verify as verify_flame
            verify_flame(out)
        elif args.crossfire:
            from verify_crossfire import verify as verify_crossfire
            verify_crossfire(out)
        elif args.return_chain:
            from verify_return_chain import verify as verify_chain
            verify_chain(out)
        elif args.forge_preview:
            from verify_forge_preview import verify as verify_forge
            verify_forge(out)
        else:
            verify(out, args.blade_detour, args.low_tour)
    except Exception:
        (out/"error.txt").write_text(traceback.format_exc(), encoding="utf8")
        raise SystemExit(1)
