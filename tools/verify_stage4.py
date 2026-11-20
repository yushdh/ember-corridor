"""Drive the production campaign with native window messages; retain framebuffer evidence."""
import argparse
import ctypes
import json
import platform
import sys
from pathlib import Path
from time import monotonic
import arcade
import pyglet
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow
from game.foundry import Bellkeeper, RELEASE
from pixel_check import check_pixels


class Route:
    def __init__(self, window, out):
        self.w = window
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.held = set()
        self.counter = 0
        self.snaps = set()
        self.frames = []
        self.events = []
        self.sequence = 0
        self.room = None
        self.run = 1
        self.start = monotonic()
        self.finished = False
        self.audio = set()
        self.last_picture = 0
        self.victory_time = None
        self.paused_once = False
        self.pause_tick = 0
        self.seen_phases = set()

    def post(self, key, down):
        vk = {"enter": 13, "space": 32, "esc": 27}.get(key) or ord(key.upper())
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        flags = 1 | (scan << 16) | (0 if down else 0xC0000000)
        if not ctypes.windll.user32.PostMessageW(self.w._hwnd, 0x100 if down else 0x101, vk, flags):
            raise RuntimeError(key)

    def tap(self, key):
        self.post(key, True)
        self.post(key, False)

    def hold(self, keys):
        for k in self.held - keys:
            self.post(k, False)
        for k in keys:
            if k not in self.held or getattr(arcade.key, k.upper()) not in self.w.keys:
                self.post(k, True)
        self.held = keys

    def capture(self, label=None):
        w = self.w
        w.switch_to()
        w.on_draw()
        im = w.ctx.get_framebuffer_image(w.ctx.screen, components=3)
        if label:
            check_pixels(im)
            im.save(self.out / (label + ".png"))
            self.snaps.add(label)
        self.frames.append(im.resize((640, 360), Image.Resampling.NEAREST))
        self.last_picture = monotonic()

    def snap(self, label):
        if label not in self.snaps:
            self.capture(label)

    def observe(self):
        w = self.w
        c = w.combat
        if c is not self.room:
            self.room = c
            self.sequence = 0
            self.jump_until = -1
            self.hold(set())
            print("run", self.run, "room", w.index + 1, flush=True)
        for ev in c.events:
            if ev["id"] > self.sequence:
                self.events.append(dict(room=w.index + 1, run=self.run, **ev))
        self.sequence = c.sequence
        for sound, p in w.battle_view.players:
            if sound.is_playing(p):
                self.audio.update(k for k, s in w.battle_view.sounds.items() if s is sound)
        for e in c.foes:
            if not isinstance(e, Bellkeeper):
                continue
            if e.state == "warn" and e.age > e.windup // 2:
                self.snap(f"{e.move_name}-phase{e.phase}")
                self.seen_phases.add((e.move_name, e.phase))
            if e.state == "active":
                self.snap(e.move_name + "-active")
            if e.state == "phase":
                self.snap("phase-change")
        if RELEASE <= c.cast_age < RELEASE + 9:
            self.snap("seal")
        if self.run == 1 and self.w.walker.x >= 360:
            self.snap(f"room-{w.index+1}")
        if monotonic() - self.last_picture > 0.65:
            self.capture()

    def drive(self, dt):
        self.counter += 1
        w = self.w
        c = w.combat
        p = w.walker
        self.observe()
        if self.counter % 600 == 0:
            print(
                "position",
                w.index + 1,
                round(p.x),
                round(p.y),
                p.action,
                "hp",
                c.hp,
                [(e.kind, e.hp) for e in c.foes],
                "valve",
                c.valve_open,
                flush=True,
            )
        if monotonic() - self.start > 240:
            raise RuntimeError(
                f"route timeout room {w.index+1}, player {p.x} {p.y} {p.action}, hp {c.hp}, guards {[(g.kind,round(g.x),g.hp,g.state) for g in c.foes]}"
            )
        if w.mode == "title":
            self.snap("start")
            self.tap("enter")
            return
        if w.mode == "won":
            self.snap("victory")
            self.victory_time = w.elapsed_ticks / 120
            self.hold(set())
            self.tap("r")
            self.run = 2
            return
        if self.run == 2:
            if w.index != 0:
                raise AssertionError("victory restart")
            if not c.hp and c.death_age > 55:
                self.snap("death")
                self.tap("r")
                self.run = 3
            else:
                self.hold({"d"} if p.x < 341 else set())
            return
        if self.run == 3:
            if c.hp == 100 and w.index == 0:
                assert not c.cooldown and c.cast_age == -1 and not c.bolts and not w.paused
                self.finished = True
                self.hold(set())
                w.close()
            return
        if not c.hp:
            raise RuntimeError(
                f"lost in room {w.index+1} at {p.x}, guards {[(g.kind,g.hp) for g in c.foes]}"
            )
        if not self.paused_once and w.index == 1:
            if not w.paused:
                self.tap("esc")
                self.pause_tick = c.tick
            else:
                if not hasattr(self, "paused_at"):
                    self.paused_at = monotonic()
                    self.pause_tick = c.tick
                elif monotonic() - self.paused_at > 0.18:
                    assert c.tick == self.pause_tick
                    self.snap("pause")
                    self.tap("esc")
                    self.paused_once = True
            return
        enemies = [e for e in c.foes if e.hp]
        e = min(enemies, key=lambda e: abs(e.x - p.x)) if enemies else None
        if c.room.valve and not c.valve_open and all(g.kind == "ram" for g in enemies):
            e = None
        if e:
            direction = 1 if e.x >= p.x else -1
            # Approach the elevated hanging guard via the stone pedestal below it.
            target_x = e.x - direction * 36
            if w.index == 3 and e.y == 203 and p.y < 140 and p.x > 529:
                target_x = 456
            target_y = e.y
        else:
            target_x, target_y = c.room.door if c.valve_open else c.room.valve
            if not c.valve_open and p.y < 141 and p.x >= 530:
                target_x = 455
            if abs(p.x - target_x) <= 25 and abs(p.y - target_y) <= 20:
                self.hold(set())
                if not c.valve_open:
                    self.snap("winch")
                if self.counter % 4 == 0:
                    self.tap("e")
                return
        delta = target_x - p.x
        close = e and abs(e.x - p.x) <= 60 and abs(p.y - e.y) < 37
        axis = 1 if delta > 3 else -1 if delta < -3 else 0
        if close:
            axis = 1 if e.x >= p.x else -1
        keys = {"d"} if axis > 0 else {"a"} if axis < 0 else set()
        if close and p.facing == axis and not c.attack:
            keys = set()
        if c.attack or c.cast_age >= 0:
            keys = set()
        jump = False
        for s in c.surfaces[1:]:
            face_gap = s.left - (p.x + 11) if axis > 0 else p.x - 11 - s.right
            if not s.one_way and s.bottom == 94 and -1 <= face_gap <= 32 and p.y < s.top:
                jump = True
            if (
                s.one_way
                and target_y >= s.top
                and p.y < s.top
                and s.left - 24 <= p.x <= s.right + 24
                and abs(target_x - p.x) < 270
            ):
                jump = True
            if (
                s.name == "泄洪闸"
                and -1 <= face_gap <= 20
                and p.y == 94
                and p.support
                and not p.recharge
            ):
                self.tap("k")
        if jump and p.support and not (p.tucked or c.hurt or c.attack or c.cast_age >= 0):
            if "space" in self.held and self.counter % 8 == 0:
                # A press during hit stun may have been consumed. Release and jump anew.
                self.post("space", False)
                self.held.discard("space")
            self.jump_until = c.tick + 55
        if c.tick < self.jump_until and not close:
            keys.add("space")
        self.hold(keys)
        if self.counter % 5 == 0:
            if c.weapon != "heavy":
                self.tap("2")
            if e and not c.attack and c.cast_age < 0 and not c.hurt:
                # Let both telegraphs finish at least once in each phase.
                study = isinstance(e, Bellkeeper) and (("vent", e.phase) not in self.seen_phases)
                if study:
                    if (
                        close
                        and e.state == "warn"
                        and e.move_name == "sweep"
                        and e.age > e.windup - 22
                    ):
                        self.tap("k")
                    return
                if (
                    not c.cooldown
                    and (e.x - p.x) * p.facing > 0
                    and abs(e.x - p.x) < 132
                    and abs(e.y - p.y) < 22
                ):
                    self.tap("q")
                elif close:
                    self.tap("j")

    def save(self):
        assert self.finished and self.run == 3 and self.paused_once
        kinds = {e["kind"] for e in self.events}
        assert {"seal", "sweep", "vent", "phase", "death", "gate"} <= kinds, kinds
        assert any(e["kind"] == "hit" and e["action"] == "seal" for e in self.events)
        report = dict(
            os=platform.platform(),
            python=platform.python_version(),
            arcade=arcade.__version__,
            renderer=self.gpu,
            window=[1280, 720],
            input="Win32 targeted keyboard messages",
            victory_seconds=self.victory_time,
            restarts=2,
            sounds=sorted(self.audio),
            shots=sorted(self.snaps),
            events=self.events,
        )
        (self.out / "run.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.frames[0].save(
            self.out / "route.gif",
            save_all=True,
            append_images=self.frames[1:],
            duration=140,
            loop=0,
            disposal=2,
        )
        print("verified", self.victory_time, "seconds;", len(self.frames), "captures", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/verification/stage4"))
    args = parser.parse_args()
    window = CampaignWindow()
    route = Route(window, args.output)
    route.gpu = pyglet.gl.gl_info.get_renderer()
    pyglet.clock.schedule_interval(route.drive, 1 / 60)
    arcade.run()
    route.save()
