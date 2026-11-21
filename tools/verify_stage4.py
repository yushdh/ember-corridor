"""Drive the production campaign with native window messages; retain framebuffer evidence."""
import argparse
import ctypes
import json
import platform
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from time import monotonic
import arcade
import pyglet
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.campaign import CampaignWindow
from game.foundry import Bellkeeper, RELEASE
from game.motion import GRAVITY, JUMP_SPEED
from game.terrain import GROUND_Y
from pixel_check import check_pixels


class Route:
    def __init__(self, window, out, *, blade_detour=False):
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
        self.blade_detour = blade_detour
        self.unclaimed = set()
        self.detour = {}

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

    def detour_target(self, c, p):
        if "refused" not in self.detour:
            if c.near(p, c.room.door):
                self.hold(set())
                if "pressed" not in self.detour:
                    assert c.hp and not c.attack and not c.hurt and c.cast_age < 0 and not c.flame.busy
                    self.snap("locked-door")
                    self.tap("e")
                    self.detour["pressed"] = c.tick
                elif c.tick >= self.detour["pressed"] + 8:
                    assert self.w.index == 3 and c.cleared and not c.valve_open
                    self.detour["refused"] = c.tick
                    self.tap("esc")
                return None
            return c.room.door
        if "locked-objective" not in self.snaps:
            if self.w.paused:
                self.snap("locked-objective")
                self.tap("esc")
            return None
        if self.w.paused:
            return None
        if "landing" not in self.detour:
            step = self.w.route.rooms[self.w.index].steps[0]
            if not (p.support and abs(p.x - step[0]) < 28 and p.y == step[1]):
                return step
            self.snap("west-step")
            self.detour["landing"] = c.tick
        return c.room.valve

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
            if self.blade_detour:
                assert w.kills == 10 and not c.loadout.ranks and not w.store.data.shell_known
            self.snap("victory")
            self.victory_time = w.elapsed_ticks / 120
            self.hold(set())
            self.tap("r")
            self.run = 2
            return
        if self.run == 2 and self.check_defeat_restart():
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
        if self.blade_detour:
            assert c.weapon == "light" and not c.loadout.ranks and not c.crate_taken
            if c.crate:
                self.unclaimed.add(w.index + 1)
            if c.room.valve and c.valve_open:
                self.snap("valve-open")
        elif c.room.valve and not c.valve_open and all(g.kind == "ram" for g in enemies):
            e = None
        if e:
            direction = 1 if e.x >= p.x else -1
            target_x = e.x - direction * 36
            target_y = e.y
        else:
            target = c.room.door if c.valve_open else c.room.valve
            if self.blade_detour and not c.valve_open:
                target = self.detour_target(c, p)
                if target is None:
                    return
            target_x, target_y = target
            if target in (c.room.door, c.room.valve) and abs(p.x - target_x) <= 25 and abs(p.y - target_y) <= 20:
                self.hold(set())
                if not c.valve_open:
                    self.snap("winch")
                if self.counter % 4 == 0:
                    self.tap("e")
                return
        # Climb the template's intermediate landing when its upper deck needs two jumps.
        for sx, sy in w.route.rooms[w.index].steps:
            if p.y < sy - 3 and target_y - GROUND_Y > JUMP_SPEED ** 2 / (2 * GRAVITY):
                target_x, target_y = sx, sy
                break
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
            if not self.blade_detour and c.weapon != "heavy":
                self.tap("2")
            if e and not c.attack and c.cast_age < 0 and not c.hurt:
                if isinstance(e, Bellkeeper) and e.state == "warn" and e.age >= e.windup - 46:
                    # A late hammer wind-up leaves the driver committed when the bell lands.
                    # Roll through the sweep or leave the locked steam column at release.
                    if e.age >= e.windup - 14 and p.support and not p.recharge:
                        self.tap("k")
                    return
                # Let both telegraphs finish at least once in each phase.
                study = isinstance(e, Bellkeeper) and (("vent", e.phase) not in self.seen_phases)
                if study:
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

    def check_defeat_restart(self):
        assert self.w.index == 0, "victory restart"
        return True

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
        if self.blade_detour:
            assert self.unclaimed == {1, 2, 3, 4} and "refused" in self.detour
            gates = [ev for ev in self.events if ev["room"] == 4 and ev["kind"] == "gate"]
            assert any(ev["tick"] > self.detour["refused"] for ev in gates)
            actions = {ev["action"] for ev in self.events if ev["kind"] == "hit"}
            assert "cut" in actions and "breaker" not in actions
            record = json.loads(self.w.record.path.read_bytes())
            assert record["source"] == "automated" and record["outcome"] == "won"
            assert record["attempts"] == 1 and record["forge_ms"] == 0 and record["pause_ms"] > 0
            assert [row["room"] for row in record["rooms"]] == [t.room.name for t in self.w.route.rooms]
            report.update(unclaimed_crate_rooms=sorted(self.unclaimed), locked_door=self.detour,
                          hit_actions=sorted(actions), source="automated")
            (self.out / "first-victory.json").write_bytes(self.w.record.path.read_bytes())
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
    parser.add_argument("--blade-detour", action="store_true",
                        help="Use the starting blade and seal, leave every crate, and try the locked fourth door.")
    args = parser.parse_args()
    test_profile = TemporaryDirectory()
    if args.blade_detour:
        from game.first_play import FirstPlayWindow
        window = FirstPlayWindow(report_root=Path(test_profile.name), source="automated")
    else:
        window = CampaignWindow(classic=True, save_dir=test_profile.name)
    route = Route(window, args.output, blade_detour=args.blade_detour)
    route.gpu = pyglet.gl.gl_info.get_renderer()
    pyglet.clock.schedule_interval(route.drive, 1 / 60)
    arcade.run()
    route.save()
