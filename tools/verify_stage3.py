"""Play the normal encounter through native Windows messages; retain real framebuffer evidence."""
import ctypes
import argparse
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game.window import QuayWindow
from game.combat import Encounter
from game.motion import Walker
from pixel_check import check_pixels
import arcade
import pyglet

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=ROOT / "docs/verification/stage3")
OUT = parser.parse_args().output
OUT.mkdir(parents=True, exist_ok=True)
test_profile = TemporaryDirectory()
window = QuayWindow(save_dir=test_profile.name)
frames = []
rounds = []
captured = set()
last_frame = 0.0
finished = False
keys = set()
audio_seen = set()
reissued = []


def key(ch, down):
    if (ch in keys) == down:
        return
    vk = {"space": 32, "esc": 27, "f1": 112, "f2": 113, "f3": 114, "f4": 115}.get(ch) or ord(
        ch.upper()
    )
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = 1 | (scan << 16) | (0 if down else 0xC0000000)
    if not ctypes.windll.user32.PostMessageW(window._hwnd, 0x100 if down else 0x101, vk, flags):
        raise RuntimeError(ch)
    if down:
        keys.add(ch)
    else:
        keys.discard(ch)


def tap(ch):
    key(ch, True)
    key(ch, False)


def wait(label, predicate, timeout=4):
    start = monotonic()
    while not predicate():
        if monotonic() - start > timeout:
            c = window.combat
            raise AssertionError(
                f"{label}, keys {keys}/{window.keys}, player {(window.walker.x,window.walker.y,c.hp,c.attack,c.age)} "
                f"foes {[(e.x,e.hp,e.state,e.age) for e in c.foes]} recent {list(c.events)[-5:]}"
            )
        yield


def picture():
    window.switch_to()
    window.on_draw()
    return window.ctx.get_framebuffer_image(window.ctx.screen, components=3)


def snap(label):
    if label not in captured:
        image = picture()
        check_pixels(image)
        image.save(OUT / (label + ".png"))
        captured.add(label)


def stop(ch):
    key(ch, False)
    yield from wait("settle", lambda: abs(window.walker.speed) < 0.01)


def approach_hook(w, c):
    key("d", True)
    yield from wait("past lamp", lambda: w.x > 306)
    yield from stop("d")
    yield from wait("hook telegraph", lambda: c.foes[0].state == "warn")


def play():
    global finished
    c, w = window.combat, window.walker
    hook, gun, ram = c.foes
    yield
    yield from approach_hook(w, c)
    snap("hook-warn")
    tap("j")
    for name in ("cut", "liftcut"):
        yield from wait(name, lambda: c.attack == name and 12 <= c.age <= 23)
        tap("j")
    yield from wait("combo kill", lambda: not hook.hp)
    hits = [ev for ev in c.events if ev["kind"] == "hit" and ev["enemy"] == "hook"]
    assert [ev["action"] for ev in hits] == ["cut", "liftcut", "thrust"]
    assert [ev["hp"] for ev in hits] == [46, 27, 0]
    yield from wait("sheathe", lambda: not c.attack)
    tap("2")
    yield from wait("equip hammer", lambda: c.weapon == "heavy")
    key("d", True)
    yield from wait("stone wall", lambda: w.x == 521)
    yield from wait("able to jump", lambda: not c.hurt and not c.freeze)
    key("space", True)
    yield from wait("atop stone", lambda: w.x >= 540)
    key("space", False)
    yield from stop("d")
    yield from wait("land on step", lambda: w.support and w.support.name == "landing")
    if w.x > 550:
        key("a", True)
        yield from wait("hammer spacing", lambda: w.x <= 550)
        yield from stop("a")
    for _ in range(5):
        if gun.hp == 0:
            break
        yield from wait("hammer ready", lambda: not c.hurt and not c.attack and not c.freeze)
        key("d", True)
        tap("j")
        yield from wait("begin hammer", lambda: c.attack == "breaker")
        key("d", False)
        yield from wait("resolve hammer", lambda: not c.attack or not gun.hp)
    assert gun.hp == 0, "rivet guard survived"
    yield from wait("free", lambda: not c.attack)
    key("d", True)
    yield from wait("gantry", lambda: w.x == 724)
    tap("k")
    yield from wait("past beam", lambda: w.x >= 823)
    key("d", False)
    # Read the opponent and find space after each rush. Only normal key presses move the player.
    start = monotonic()
    while ram.hp and c.hp:
        if monotonic() - start > 24:
            raise AssertionError(
                f"ram duel {ram.hp}, player={w.x}, foe={ram.x}, {list(c.events)[-6:]}"
            )
        if not c.hurt and not c.attack and not c.freeze and w.roll_age < 0:
            delta = ram.x - w.x
            facing = 1 if delta >= 0 else -1
            if abs(delta) > 52:
                key("a", facing < 0)
                key("d", facing > 0)
            elif abs(delta) < 25 and ram.state not in ("active", "warn"):
                key("a", facing > 0)
                key("d", facing < 0)
            else:
                key("a", facing < 0)
                key("d", facing > 0)
                tap("j")
        else:
            key("a", False)
            key("d", False)
        yield
    key("d", False)
    key("a", False)
    assert c.cleared and c.hp > 0, "first run should clear the quay"
    snap("clear")
    rounds.append(list(c.events))
    tap("r")
    yield from wait("clear restart", lambda: window.combat is not c)
    c, w = window.combat, window.walker
    yield from approach_hook(w, c)
    yield from wait("late tell", lambda: c.foes[0].age >= 34)
    tap("k")
    yield from wait("roll evaded live hook", lambda: any(v["kind"] == "evade" for v in c.events))
    snap("evade")
    tap("esc")
    yield from wait("paused", lambda: window.paused)
    assert not w.invulnerable
    tick = c.tick
    for i, ch in enumerate(("f1", "f2", "f3", "f4")):
        tap(ch)
        yield from wait("feedback setting", lambda: window.battle_view.levels[i] == 3)
    snap("pause")
    assert c.tick == tick
    tap("esc")
    yield from wait("resumed", lambda: not window.paused)
    # Remaining exposed proves the real damage -> interruption -> death -> restart path.
    yield from wait("death from enemy attacks", lambda: not c.hp, timeout=22)
    yield from wait("death pose", lambda: c.death_age >= 55)
    snap("death")
    rounds.append(list(c.events))
    tap("r")
    yield from wait("fresh run", lambda: window.combat is not c)
    c, w = window.combat, window.walker
    assert c.hp == 100 and all(e.hp == e.spec.hp for e in c.foes)
    assert not c.attack and not c.immune and not c.bolts and not c.buffer and not w.invulnerable
    assert not window.battle_view.particles
    resolutions = [(1280, 720), (1366, 768), (1920, 1080)]
    for size in resolutions:
        window.set_size(*size)
        yield from wait("framebuffer resize", lambda: window.get_framebuffer_size() == size)
        yield
        check_pixels(picture())
    traces = {}
    for hz in (30, 60, 144):
        window.combat = Encounter()
        window.walker = Walker(x=329)
        window.clear_input()
        window.scroll = window.lift = 0.0
        window.battle_view.reset()
        window.combat.foes[0].x = 369
        trace = []
        for block in range(9):
            if block in (0, 1, 2, 3):
                window.on_key_press(arcade.key.J, 0)
                window.on_key_release(arcade.key.J, 0)
            for _ in range(hz // 6):
                window.on_update(1 / hz)
            sim = window.combat
            trace.append((sim.attack, sim.age, sim.hp, sim.foes[0].hp, window.walker.x, sim.freeze))
        traces[hz] = trace
    assert traces[30] == traces[60] == traces[144] and traces[60][-1][3] == 0
    frames[0].save(
        OUT / "combat.gif", save_all=True, append_images=frames[1:], duration=90, loop=0, disposal=2
    )
    report = dict(
        os=platform.platform(),
        python=platform.python_version(),
        arcade=arcade.__version__,
        gpu=pyglet.gl.gl_info.get_renderer(),
        opengl=pyglet.gl.gl_info.get_version(),
        capture_size=[1280, 720],
        resolutions=resolutions,
        snaps=sorted(captured),
        matched_update_hz=list(traces),
        sampled_trace=traces[60],
        audio_players_observed=sorted(audio_seen),
        restarts=2,
        rounds=rounds,
        reissued_keys=reissued,
    )
    (OUT / "combat.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("native combat route passed", [(len(r), r[-1]["kind"]) for r in rounds], sorted(captured))
    finished = True


route = play()


def update(dt):
    global last_frame
    c = window.combat
    # Losing desktop focus intentionally releases held controls in the game.
    # Reissue the driver's intended hold through the same native input path.
    for ch in tuple(keys):
        if (
            ch in ("a", "d", "space")
            and getattr(arcade.key, ch.upper()) not in window.keys
            and not window.paused
        ):
            keys.remove(ch)
            key(ch, True)
            reissued.append((c.tick, ch))
    for s, p in window.battle_view.players:
        if s.is_playing(p):
            audio_seen.update(k for k, v in window.battle_view.sounds.items() if v is s)
    if (
        c.freeze
        and c.attack
        and any(e["kind"] == "hit" and e["attack_id"] == c.serial for e in c.events)
    ):
        if c.attack in ("cut", "breaker"):
            snap(c.attack + "-hit")
    for e in c.foes[1:]:
        if e.state == "warn" and e.age > e.spec.windup * 0.6:
            snap(e.kind + "-warn")
    if c.bolts:
        snap("bolt")
    if monotonic() - last_frame >= 0.082:
        frames.append(picture().resize((640, 360), Image.Resampling.NEAREST))
        last_frame = monotonic()
    try:
        next(route)
    except StopIteration:
        window.close()


if __name__ == "__main__":
    pyglet.clock.schedule_interval(update, 1 / 120)
    arcade.run()
    if not finished:
        raise RuntimeError("closed early")
