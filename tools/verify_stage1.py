"""Exercise the visible Windows game using window-targeted native key messages."""
import ctypes
import json
import platform
import sys
from pathlib import Path
from time import monotonic

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.window import QuayWindow
from pixel_check import check_pixels
import arcade
import pyglet

import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "docs" / "verification")
OUT = parser.parse_args().output
OUT.mkdir(parents=True, exist_ok=True)
window = QuayWindow(practice=True)
initial = window.walker.x
report = {
    "os": platform.platform(),
    "python": platform.python_version(),
    "arcade": arcade.__version__,
    "renderer": pyglet.gl.gl_info.get_renderer(),
    "opengl": pyglet.gl.gl_info.get_version(),
    "samples": [],
}
phase = 0
started = monotonic()
seen = set()
animation = []
last_sample = -1.0
paused_position = 0.0


def send_key(letter, down):
    vk = ord(letter)
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = 1 | (scan << 16) | (0 if down else 0xC0000000)
    if not ctypes.windll.user32.PostMessageW(window._hwnd, 0x100 if down else 0x101, vk, flags):
        raise RuntimeError("PostMessageW failed")


def capture():
    window.switch_to()
    window.on_draw()
    return window.ctx.get_framebuffer_image(window.ctx.screen, components=3)


def record(label, save=True):
    im = capture()
    check_pixels(im)
    if save:
        im.save(OUT / f"{label}.png")
    report["samples"].append(
        {
            "label": label,
            "framebuffer": im.size,
            "x": round(window.walker.x, 2),
            "facing": window.walker.facing,
            "action": window.walker.action,
        }
    )


def advance():
    global phase, started
    phase += 1
    started = monotonic()
    seen.clear()


def verify(dt):
    global last_sample, paused_position
    elapsed = monotonic() - started
    actor = window.walker
    frame = window.clips[actor.action].frame(actor.age)
    if actor.action == ("idle" if phase == 0 else "run"):
        seen.add(id(frame))
    if phase <= 3 and monotonic() - last_sample >= 0.075:
        im = capture()
        animation.append(im.resize((640, 360), Image.Resampling.NEAREST))
        last_sample = monotonic()
    if elapsed > 7:
        raise AssertionError(f"timed out in phase {phase}")
    if phase == 0 and len(seen) == 6 and elapsed > 1.05:
        assert actor.action == "idle" and actor.x == initial
        record("idle")
        send_key("D", True)
        advance()
    elif (
        phase == 1
        and actor.action == "run"
        and elapsed > 0.75
        and len(seen) == 8
        and frame is window.clips["run"].frames[4]
    ):
        assert actor.x > initial + 65 and actor.facing == 1
        record("run-right")
        send_key("D", False)
        send_key("A", True)
        advance()
    elif (
        phase == 2
        and actor.action == "run"
        and elapsed > 1.18
        and len(seen) == 8
        and frame is window.clips["run"].frames[0]
    ):
        assert actor.facing == -1 and actor.x < report["samples"][-1]["x"] - 70
        record("run-left")
        send_key("A", False)
        advance()
    elif phase == 3 and elapsed > 0.4:
        assert not window.keys and actor.action == "idle" and actor.speed == 0
        paused_position = actor.x
        window.set_size(1366, 768)
        advance()
    elif phase == 4 and elapsed > 0.23:
        assert window.get_framebuffer_size() == (1366, 768) and actor.x == paused_position
        record("letterbox", False)
        window.set_size(1920, 1080)
        advance()
    elif phase == 5 and elapsed > 0.23:
        assert window.get_framebuffer_size() == (1920, 1080)
        record("full-hd", False)
        animation[0].save(
            OUT / "motion.gif",
            save_all=True,
            append_images=animation[1:],
            duration=80,
            loop=0,
            disposal=2,
        )
        (OUT / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
        window.close()


if __name__ == "__main__":
    pyglet.clock.schedule_interval(verify, 1 / 60)
    arcade.run()
