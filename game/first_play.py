"""Local, opt-in timing for a fresh playthrough of the five handmade rooms."""
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
from tempfile import mkdtemp
from time import monotonic

from .campaign import CampaignWindow
from .profile import atomic_write


class FirstPlayRecord:
    def __init__(self, directory, source="unclassified", clock=monotonic):
        self.path = directory / "session.json"
        self.source = source
        self.clock = clock
        self.start = None
        self.events = []
        self.attempt = 1
        self.finished = False

    def observe(self, state, room):
        if self.finished or (not self.events and state == "title"):
            return False
        if self.events:
            previous = self.events[-1]
            if (previous["state"], previous["room"]) == (state, room):
                return False
            if previous["state"] == "dead" and state == "play":
                self.attempt += 1
        now = self.clock()
        if self.start is None:
            self.start = now
        self.events.append(dict(at_ms=round(1000 * (now - self.start)),
                                attempt=self.attempt, room=room, state=state))
        self.finished = state in {"won", "closed"}
        return True

    def snapshot(self):
        totals = Counter()
        rooms = {}
        for first, second in zip(self.events, self.events[1:]):
            duration = second["at_ms"] - first["at_ms"]
            state = first["state"]
            totals[state] += duration
            if state in {"play", "forge"}:
                key = (first["attempt"], first["room"])
                rooms[key] = rooms.get(key, 0) + duration
        last = self.events[-1]
        outcome = last["state"] if self.finished else "in_progress"
        if len(self.events) == 1 and outcome == "closed":
            outcome = "closed_before_start"
        return dict(version=1, route="classic", source=self.source, outcome=outcome,
                    wall_ms=last["at_ms"], play_ms=totals["play"], forge_ms=totals["forge"],
                    pause_ms=totals["pause"], retry_wait_ms=totals["dead"],
                    attempts=self.attempt if outcome != "closed_before_start" else 0,
                    deaths=sum(e["state"] == "dead" for e in self.events),
                    rooms=[dict(attempt=a, room=r, engaged_ms=t) for (a, r), t in rooms.items()],
                    transitions=self.events)

    def save(self):
        atomic_write(self.path, json.dumps(self.snapshot(), ensure_ascii=False, indent=2).encode("utf8"))


class FirstPlayWindow(CampaignWindow):
    def __init__(self, *, report_root=None, source="unclassified"):
        if report_root is None:
            report_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EmberCorridor-Playtests"
        report_root.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now().strftime("%Y%m%d-%H%M%S-")
        directory = Path(mkdtemp(dir=report_root, prefix=prefix))
        self.record = FirstPlayRecord(directory, source)
        self.report_pending = False
        super().__init__(classic=True, save_dir=directory / "profile")

    def note(self, state):
        room = self.combat.room.name
        if self.record.observe(state, room) or (self.report_pending and state == "closed"):
            try:
                self.record.save()
            except OSError:
                if not self.report_pending:
                    self.set_caption("余烬回廊 · 试玩记录写入失败，请检查目录权限或磁盘空间")
                self.report_pending = True
            else:
                if self.report_pending and state != "closed":
                    self.set_caption("余烬回廊 · 首次试玩")
                self.report_pending = False

    def observe_game(self):
        if self.mode in {"title", "won", "forge"}:
            self.note(self.mode)
        elif not self.combat.hp:
            self.note("dead")
        else:
            self.note("pause" if self.paused else "play")

    def on_key_press(self, key, modifiers):
        super().on_key_press(key, modifiers)
        self.observe_game()

    def on_update(self, dt):
        super().on_update(dt)
        if not self.closed:
            self.observe_game()

    def close(self):
        if hasattr(self, "combat") and self.combat is not None:
            self.note("closed")
        super().close()
