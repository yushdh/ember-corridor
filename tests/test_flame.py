import unittest

from game.combat import Enemy
from game.flame import FULL_CHARGE, RELEASE_FRAME, RECOVERY_FRAME, SWING_ENDS, ROLL_BUFFER_TICKS
from game.foundry import FoundryEncounter, ROOMS
from game.motion import Walker
from game.terrain import FLOOR, Surface


class FlameCutTests(unittest.TestCase):
    def make(self, facing=1):
        c = FoundryEncounter(ROOMS[0])
        w = Walker(x=400, facing=facing)
        e = Enemy("hook", 400 + facing * 93, FLOOR.top, (200, 600))
        e.enter("recover")
        c.foes = [e]
        return c, w, e

    def charge(self, c, w):
        c.step(w, 0, flame_press=True, flame_hold=True)
        for _ in range(FULL_CHARGE):
            c.step(w, 0, flame_hold=True)
        self.assertEqual(c.flame.frame, 3)

    def test_ignition_is_one_shot_while_the_ready_body_loops(self):
        c, w, _ = self.make()
        self.charge(c, w)
        for age in range(54):
            expected = ("fire-ignite", age // 6) if age < 18 else ("firelight", c.flame.frame)
            self.assertEqual(c.flame.light_pose(True), expected)
            self.assertEqual(c.flame.light_pose(False), ("firelight", c.flame.frame))
            c.step(w, 0, flame_hold=True)
        self.assertEqual(sum(e["kind"] == "ignite" for e in c.events), 1)
        c.step(w, 0)
        self.assertEqual(c.flame.light_pose(True), ("firelight", RELEASE_FRAME))

    def test_sweep_hits_once_and_kicks_away_in_both_directions(self):
        for direction in (-1, 1):
            c, w, e = self.make(direction)
            self.charge(c, w)
            self.assertEqual(e.hp, 62)
            old = e.x
            while c.flame.busy:
                c.step(w, 0)
            hits = [ev for ev in c.events if ev["kind"] == "hit"]
            self.assertEqual((len(hits), e.hp), (1, 8))
            self.assertTrue(RELEASE_FRAME <= hits[0]["frame"] < RECOVERY_FRAME)
            self.assertGreater((e.x - old) * direction, 10)
            self.assertEqual(w.x, 400 + direction * 8)

    def test_short_release_and_hurt_cancel_without_releasing(self):
        c, w, e = self.make()
        c.step(w, 0, flame_press=True, flame_hold=True)
        c.step(w, 0)
        self.assertFalse(c.flame.busy)
        self.charge(c, w)
        c.damage_player(w, e, w.x, w.y + 32)
        c.step(w, 0)
        self.assertFalse(c.flame.busy)
        self.assertFalse(any(ev["kind"] == "firecut" for ev in c.events))

    def test_wall_whiff_and_embers_have_no_hitstop_or_damage(self):
        c, w, e = self.make()
        c.surfaces = (FLOOR, Surface("wall", 430, 479, 94, 310))
        self.charge(c, w)
        c.step(w, 0)
        while c.flame.frame < RECOVERY_FRAME:
            c.step(w, 0)
            self.assertEqual(c.freeze, 0)
        e.x = w.x + 20
        while c.flame.busy:
            c.step(w, 0)
        self.assertEqual(e.hp, 62)

    def test_last_six_recovery_steps_remember_one_roll_direction(self):
        for remaining in (1, 4, ROLL_BUFFER_TICKS, ROLL_BUFFER_TICKS+1):
            with self.subTest(remaining=remaining):
                c, w, _ = self.make()
                c.flame.swing = SWING_ENDS[-1] - remaining
                for n in range(remaining):
                    c.step(w, -1 if n == 0 else 0, roll=n == 0)
                    if c.flame.busy:
                        self.assertEqual(w.roll_age, -1)
                queued = remaining <= ROLL_BUFFER_TICKS
                self.assertEqual(w.roll_age, 0 if queued else -1)
                if queued:
                    self.assertEqual(w.facing, -1)
                self.assertEqual(c.flame_roll_direction, 0)

    def test_pending_flame_roll_clears_on_pause_or_damage(self):
        for interruption in ("pause", "hurt"):
            with self.subTest(interruption=interruption):
                c, w, e = self.make()
                c.flame.swing = SWING_ENDS[-1] - 5
                c.step(w, -1, roll=True)
                if interruption == "pause":
                    c.pause()
                else:
                    c.damage_player(w, e, w.x, w.y)
                for _ in range(30):
                    c.step(w, 0)
                    self.assertEqual(w.roll_age, -1)
                self.assertEqual(c.flame_roll_direction, 0)

    def test_heavy_weapon_and_air_cannot_start_charge(self):
        c, w, e = self.make()
        c.weapon = "heavy"
        c.step(w, 0, flame_press=True, flame_hold=True)
        self.assertFalse(c.flame.busy)
        c.weapon = "light"
        w.support = None
        w.y += 16
        c.step(w, 0, flame_press=True, flame_hold=True)
        self.assertFalse(c.flame.busy)
