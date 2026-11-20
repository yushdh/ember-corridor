"""Play the movement course in a visible window using targeted Windows keyboard messages."""
import ctypes
import argparse
import json
import platform
from pathlib import Path
import sys
from time import monotonic

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.window import QuayWindow
from game.terrain import FLOOR, SURFACES
from game.motion import Walker, STAND_HEIGHT
import arcade
import pyglet

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "docs" / "verification" / "stage2")
OUT = parser.parse_args().output
OUT.mkdir(parents=True, exist_ok=True)
window = QuayWindow(practice=True)
w = window.walker
samples = []
frames = []
last_frame = -1
complete = False
held_directions = set()
reissued = []


def key(char, down):
    vk = {"space": 32, "esc": 27}.get(char)
    if vk is None:
        vk = ord(char.upper())
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = 1 | (scan << 16) | (0 if down else 0xC0000000)
    if not ctypes.windll.user32.PostMessageW(window._hwnd, 0x100 if down else 0x101, vk, flags):
        raise RuntimeError("Windows did not accept game key")
    if char in ("a", "d"):
        (held_directions.add if down else held_directions.discard)(char)


def until(label, predicate, timeout=4):
    start = monotonic()
    while not predicate():
        if monotonic() - start > timeout:
            raise AssertionError(
                f"{label}: x={w.x:.1f} y={w.y:.1f} vy={w.vy:.1f} {w.action} {w.support}"
            )
        yield


def picture():
    window.switch_to()
    window.on_draw()
    return window.ctx.get_framebuffer_image(window.ctx.screen, components=3)


def mark(label, png=False):
    samples.append(
        dict(
            event=label,
            x=round(w.x, 2),
            y=round(w.y, 2),
            vy=round(w.vy, 2),
            support=w.support.name if w.support else None,
            action=w.action,
            camera=[round(window.scroll, 1), round(window.lift, 1)],
            invulnerable=w.invulnerable,
        )
    )
    if png:
        picture().save(OUT / (label + ".png"))


def stop(char):
    key(char, False)
    yield from until("stop", lambda: w.speed == 0 and w.support)


def on(name):
    return w.support is not None and w.support.name == name


def compare_updates():
    # Exercise the game's actual accumulator and key callbacks with controlled deltas.
    traces = {}
    for hz in (30, 60, 144):
        window.walker = Walker()
        window.clear_input()
        window.scroll = window.lift = 0
        result = []
        for edits in [
            [("D", True)],
            [("SPACE", True)],
            [("SPACE", False)],
            [("K", True)],
            [("K", False), ("D", False), ("A", True)],
            [("A", False)],
        ]:
            for name, down in edits:
                callback = window.on_key_press if down else window.on_key_release
                callback(getattr(arcade.key, name), 0)
            for _ in range(hz // 2):
                window.on_update(1 / hz)
            test = window.walker
            result.append(
                (test.x, test.y, test.action, test.speed, test.invulnerable, window.scroll)
            )
        traces[hz] = result
    assert traces[30] == traces[60] == traces[144]
    return traces[60]


def play():
    global complete
    yield
    key("a", True)
    yield from until("under overhead", lambda: w.x < 219)
    yield from stop("a")
    key("space", True)
    limit = next(s.bottom for s in SURFACES if s.name == "weighbridge") - STAND_HEIGHT
    yield from until("ceiling contact", lambda: w.y >= limit - 1 and w.vy <= 0)
    assert w.y <= limit
    mark("head-stop")
    key("space", False)
    yield from until("floor", lambda: w.support is FLOOR)
    key("d", True)
    yield from until("open ground", lambda: w.x > 280)
    yield from stop("d")
    key("space", True)
    yield from until("tap release", lambda: w.y > 102)
    key("space", False)
    yield from until("tap apex", lambda: w.vy <= 0)
    tap_y = w.y
    mark("tap-apex")
    yield from until("feet down", lambda: w.support is FLOOR)
    key("space", True)
    yield from until("long jump", lambda: w.y > 166)
    yield from until("full apex", lambda: w.vy <= 0)
    assert w.y > tap_y + 40
    mark("held-apex")
    key("space", False)
    yield from until("buffer before landing", lambda: 94 < w.y < 117 and w.vy < 0)
    mark("buffer-pressed")
    key("space", True)
    yield from until("buffered jump", lambda: w.vy > 0 and w.y > 100)
    mark("buffer-fired")
    key("space", False)
    yield from until("ground", lambda: w.support is FLOOR)
    key("d", True)
    yield from until("below sling", lambda: w.x > 389)
    yield from stop("d")
    key("space", True)
    yield from until("above deck", lambda: w.y > 161)
    mark("jump-through", True)
    key("space", False)
    yield from until("boarded", lambda: on("sling"))
    mark("deck-land")
    key("s", True)
    key("space", True)
    yield from until("under deck", lambda: w.y < 153 and not w.support)
    mark("drop-through")
    key("space", False)
    key("s", False)
    yield from until("floor", lambda: w.support is FLOOR)
    key("d", True)
    yield from until("solid wall", lambda: w.x == 521 and w.speed == 0)
    key("k", True)
    yield from until("roll on wall", lambda: w.invulnerable)
    assert w.x == 521 and w.speed == 0
    mark("wall-roll")
    key("k", False)
    key("esc", True)
    yield from until("pause", lambda: window.paused)
    key("esc", False)
    assert not w.invulnerable
    yield
    key("esc", True)
    yield from until("resume", lambda: not window.paused)
    key("esc", False)
    key("d", False)
    key("a", True)
    yield from until("back to sling", lambda: w.x < 421)
    yield from stop("a")
    key("space", True)
    yield from until("deck", lambda: on("sling"))
    key("space", False)
    key("d", True)
    yield from until("walk off edge", lambda: w.support is None and w.grace > 0)
    mark("edge-pressed")
    key("space", True)
    yield from until("grace jump", lambda: w.vy > 0 and w.y > 164)
    mark("edge-jump", True)
    yield from until("stone landing", lambda: on("landing"))
    key("space", False)
    yield from until("beam entrance", lambda: w.x == 724)
    key("k", True)
    yield from until("beneath beam", lambda: 751 < w.x < 794 and w.action == "roll")
    assert w.tucked and w.y + w.height <= 140
    mark("under-beam", True)
    key("k", False)
    yield from until("standing again", lambda: w.x > 821 and not w.tucked)
    mark("roll-exit")
    yield from until("sluice face", lambda: w.x == 1017)
    key("space", True)
    yield from until("sluice ledge", lambda: on("sluice"))
    key("space", False)
    yield from until("upper approach", lambda: w.x > 1093)
    key("space", True)
    yield from until("upper deck", lambda: on("gallery"))
    key("space", False)
    yield from stop("d")
    assert window.scroll == 640 and window.lift > 5
    mark("gallery", True)
    key("a", True)
    yield from until("return to gantry", lambda: w.x == 819)
    key("k", True)
    yield from until("clear left side", lambda: w.x < 724 and not w.tucked)
    key("k", False)
    yield from until("eastern face of stone", lambda: w.x == 668)
    key("space", True)
    yield from until("back atop stone", lambda: on("landing"))
    key("space", False)
    yield from until("back at starting quay", lambda: w.x < 294, timeout=5)
    yield from stop("a")
    mark("returned")
    trace = compare_updates()
    frames[0].save(
        OUT / "route.gif", save_all=True, append_images=frames[1:], duration=100, loop=0, disposal=2
    )
    report = dict(
        os=platform.platform(),
        python=platform.python_version(),
        arcade=arcade.__version__,
        renderer=pyglet.gl.gl_info.get_renderer(),
        opengl=pyglet.gl.gl_info.get_version(),
        framebuffer=window.get_framebuffer_size(),
        events=samples,
        equivalent_update_hz=[30, 60, 144],
        reissued_directions=reissued,
        half_second_trace=trace,
    )
    (OUT / "route.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    complete = True


route = play()


def advance(dt):
    global last_frame
    for char in sorted(held_directions):
        if not window.paused and getattr(arcade.key, char.upper()) not in window.keys:
            key(char, True)
            reissued.append((char, w.x))
    if monotonic() - last_frame >= 0.095:
        frames.append(picture().resize((640, 360), Image.Resampling.NEAREST))
        last_frame = monotonic()
    try:
        next(route)
    except StopIteration:
        window.close()


if __name__ == "__main__":
    pyglet.clock.schedule_interval(advance, 1 / 120)
    arcade.run()
    if not complete:
        raise RuntimeError("Verification window closed early")
