"""Capture the game framebuffer and reconstruct only its admitted game sounds for the reel."""
import argparse
from array import array
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, sleep
from unittest.mock import patch
import wave

import arcade
import pyglet
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.campaign import CampaignWindow
from game.flame import FULL_CHARGE


def export(out, frames, calls, encoder):
    rate = 22050
    mix = [0.0] * round(len(frames) * rate / 60)
    for cue in calls:
        if not cue["played"]:
            continue
        with wave.open(str(ROOT / "assets/combat/audio" / (cue["name"] + ".wav")), "rb") as wav:
            samples = array("h", wav.readframes(wav.getnframes()))
        offset = round(cue["frame"] * rate / 60)
        end = round(cue.get("stop", len(frames)) * rate / 60)
        for i, value in enumerate(samples[: max(0, min(len(mix), end) - offset)]):
            mix[offset + i] += value * cue["gain"]
    with TemporaryDirectory() as tmp:
        track = Path(tmp) / "game.wav"
        with wave.open(str(track), "wb") as wav:
            wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            wav.writeframes(array("h", (round(max(-32767, min(32767, v))) for v in mix)).tobytes())
        command = [
            str(encoder),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "640x360",
            "-r",
            "60",
            "-i",
            "-",
            "-i",
            str(track),
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out / "combat.mp4"),
        ]
        subprocess.run(command, input=b"".join(frames), check=True)


def capture(w, out, encoder):
    frames, calls, shots, events = [], [], {}, {}
    view = w.battle_view
    sound = view.sound
    tracking = {}

    def observe(name):
        previous = {p for s, p in view.players if s.is_playing(p)}
        sound(name)
        live = {p for s, p in view.players}
        for p in previous - live:
            if p in tracking:
                tracking[p]["stop"] = len(frames)
        added = live - previous
        record = dict(scene=scene, name=name, frame=len(frames), played=bool(added))
        if added:
            (player,) = added
            record["gain"] = player.volume
            tracking[player] = record
        calls.append(record)

    w.on_key_press(arcade.key.ENTER, 0)
    w.on_key_release(arcade.key.ENTER, 0)
    view.sound = observe
    seen_lights = {}
    light_textures = {
        tex: (name, i)
        for name in ("fire-ignite", "firelight")
        if name in w.extra
        for i, frame in enumerate(w.extra[name].frames)
        for tex in (frame.right, frame.left)
    }
    draw_rect = arcade.draw_texture_rect

    def observe_draw(texture, *args, **kwargs):
        if texture in light_textures:
            seen_lights.setdefault(scene, set()).add(light_textures[texture])
        return draw_rect(texture, *args, **kwargs)

    for scene, release, length in (
        ("cancel", 14, 54),
        ("hold", 77, 118),
        ("overlap", 30, 88),
        ("six-voices", 36, 79),
        ("muted", 46, 72),
    ):
        for record in tracking.values():
            record.setdefault("stop", len(frames))
        tracking.clear()
        w.start_room(3)
        w.guidance.reset(("move", "jump", "attack", "roll"))
        w.region_age = w.objective_age = 8
        view.levels[:] = [3] * 4
        if scene == "muted":
            view.levels[1:3] = [0, 0]
            w.walker.facing = -1
        w.ambient_tick = 0
        view.rng.seed(19)
        w.walker.x, w.scroll = 830, 520
        hook, bolt, ram = w.combat.foes
        if scene == "overlap":
            hook.x, hook.patrol = 910, (875, 960)
            hook.enter("recover")
            bolt.x, bolt.y, bolt.patrol = 996, 155, (850, 1002)
            ram.x = 1070
        else:
            for enemy in w.combat.foes:
                enemy.x, enemy.patrol = 1200, (1180, 1230)
        w.on_key_press(arcade.key.L, 0)
        previous = -1
        pressure = False
        for i in range(length):
            started = perf_counter()
            pyglet.app.platform_event_loop.dispatch_posted_events()
            flame = w.combat.flame
            if (
                scene == "six-voices"
                and not pressure
                and FULL_CHARGE - 2 <= flame.charge < FULL_CHARGE
            ):
                for name in ("land", "roll", "sabre", "maul", "hit", "crush"):
                    view.sound(name)
                assert len(view.players) == 6
                pressure = True
            if i == release:
                w.on_key_release(arcade.key.L, 0)
            w.on_update(1 / 60)
            with patch.object(arcade, "draw_texture_rect", observe_draw):
                w.on_draw()
            assert len(view.players) <= 6
            if scene == "six-voices" and previous < FULL_CHARGE <= flame.charge:
                # A competing enemy warning arriving immediately after readiness.
                view.sound("rivet")
                if "fire-ignite" in w.extra:
                    playing = {s for s, player in view.players if s.is_playing(player)}
                    assert {view.sounds["ignite"], view.sounds["rivet"]} <= playing
            im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
            label = None
            if scene == "hold":
                for age, name in (
                    (FULL_CHARGE, "ignite"),
                    (FULL_CHARGE + 6, "opening"),
                    (FULL_CHARGE + 12, "cooling"),
                    (FULL_CHARGE + 18, "held"),
                    (FULL_CHARGE + 36, "held-next"),
                ):
                    if previous < age <= flame.charge:
                        label = name
            if scene == "overlap" and flame.swing >= 0 and flame.frame == 8 and view.warning_badges:
                label = "fire-warning"
            if label and label not in shots:
                im.save(out / (label + ".png"))
                shots[label] = dict(
                    frame=i,
                    charge=flame.charge,
                    pose=flame.frame,
                    badges=len(view.warning_badges),
                    scroll=w.scroll,
                )
            frames.append(im.resize((640, 360), Image.Resampling.NEAREST).tobytes())
            previous = flame.charge
            w.flip()
            sleep(max(0, 1 / 60 - (perf_counter() - started)))
        events[scene] = [e["kind"] for e in w.combat.events]
        assert events[scene].count("ignite") == int(scene != "cancel")
        assert events[scene].count("firecut") == int(scene != "cancel")
    assert len(shots) == 6
    if "fire-ignite" in w.extra:
        assert {i for name, i in seen_lights["hold"] if name == "fire-ignite"} == {0, 1, 2}
        assert all(
            name != "fire-ignite" for scene in ("cancel", "muted") for name, i in seen_lights[scene]
        )
        assert all(not cue["played"] for cue in calls if cue["scene"] == "muted")
        assert all(
            cue["played"] for cue in calls if cue["name"] == "ignite" and cue["scene"] != "muted"
        )
    export(out, frames, calls, encoder)
    lights = {scene: sorted(seen) for scene, seen in seen_lights.items()}
    (out / "trace.json").write_text(
        json.dumps(dict(shots=shots, events=events, sounds=calls, lights=lights), indent=2),
        encoding="utf8",
    )
    print([(c["scene"], c["name"], c["played"]) for c in calls if c["name"] in ("ignite", "rivet")])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--encoder", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory() as profile:
        window = CampaignWindow(classic=True, save_dir=profile)
        try:
            capture(window, args.out, args.encoder)
        finally:
            window.close()
