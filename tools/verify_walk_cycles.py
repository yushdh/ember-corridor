"""Play all movement cycles, with both weapons and facings, in the game window."""
import argparse
import json
import sys
from pathlib import Path

import arcade
import pyglet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.combat import Encounter
from game.motion import Walker, STEP
from game.window import QuayWindow


class Cycles(QuayWindow):
    def __init__(self):
        self.ready = False
        super().__init__()
        self.cases = iter(
            (weapon, facing, move)
            for weapon in ("light", "heavy")
            for facing in (1, -1)
            for move in ("idle", "run", "jump", "roll")
        )
        self.seen = {}
        self.t = 0
        self.done = False
        self.ready = True

    def on_update(self, dt):
        pass

    def on_draw(self):
        if not self.ready or self.done:
            return
        if self.t == 0:
            case = next(self.cases, None)
            if case is None:
                self.done = True
                pyglet.clock.schedule_once(lambda dt: self.close(), 0)
                return
            self.weapon, self.facing, self.move = case
            self.combat = Encounter()
            # Keep enemies out of range while checking uninterrupted clips.
            for enemy in self.combat.foes:
                enemy.x = 1100
                enemy.patrol = (1050, 1180)
            self.walker = Walker(x=306, facing=self.facing)
            self.clear_input()
            self.battle_view.reset()
            self.scroll = self.lift = 0
            if self.weapon == "heavy":
                self.on_key_press(arcade.key.KEY_2, 0)
            button = {
                "run": arcade.key.D if self.facing == 1 else arcade.key.A,
                "jump": arcade.key.SPACE,
                "roll": arcade.key.K,
            }.get(self.move)
            if button is not None:
                self.on_key_press(button, 0)
        # Present every other simulation tick, as in normal 60 Hz gameplay.
        super().on_update(2 * STEP)
        super().on_draw()
        action = self.walker.action
        bank = self.clips if self.weapon == "light" else self.battle_view.clips
        name = action if self.weapon == "light" else "hammer_" + action
        clip = bank[name]
        frame = next(
            i
            for i, f in enumerate(clip.frames)
            if self.actor.texture is (f.right if self.facing == 1 else f.left)
        )
        key = f"{self.weapon}/{self.facing}/{action}"
        self.seen.setdefault(key, set()).add(frame)
        self.t = (self.t + 1) % 68

    def save(self, path):
        assert self.done
        for weapon in ("light", "heavy"):
            for facing in (1, -1):
                for name, clip in self.clips.items():
                    key = f"{weapon}/{facing}/{name}"
                    assert self.seen.get(key) == set(range(len(clip.frames))), (
                        key,
                        self.seen.get(key),
                    )
        path.write_text(
            json.dumps({k: sorted(v) for k, v in self.seen.items()}, indent=1), encoding="utf-8"
        )
        print("Complete movement clips:", len(self.seen))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    output = parser.parse_args().report
    window = Cycles()
    arcade.run()
    window.save(output)
