import unittest

from game.combat import Bolt, Enemy
from game.foundry import Bellkeeper, CAST_TICKS, COOLDOWN, FoundryEncounter, RELEASE, ROOMS
from game.motion import Walker
from game.terrain import FLOOR, Surface


class FoundryTests(unittest.TestCase):
    def test_valve_requires_platform_and_live_player(self):
        c = FoundryEncounter(ROOMS[3])
        p = Walker(x=705)
        for e in c.foes:
            e.hp = 0
        self.assertIsNone(c.interact(p))
        p.x, p.y = c.room.door
        self.assertIsNone(c.interact(p))
        p.x, p.y = c.room.valve
        self.assertEqual(c.interact(p), "valve")
        self.assertIsNone(c.interact(p))
        p.x, p.y = c.room.door
        self.assertEqual(c.interact(p), "exit")
        c.hp = 0
        self.assertIsNone(c.interact(p))

    def test_wave_has_one_release_and_respects_cooldown(self):
        for facing in (-1, 1):
            c = FoundryEncounter(ROOMS[0])
            w = Walker(x=350, facing=facing)
            enemy = Enemy("hook", 350 + 100 * facing, 94, (215, 485))
            c.foes = [enemy]
            c.step(w, 0, skill=True)
            for _ in range(RELEASE - 1):
                c.step(w, 0)
            self.assertEqual(enemy.hp, 62)
            c.step(w, 0)
            self.assertEqual(enemy.hp, 30)
            for _ in range(sum(CAST_TICKS)):
                c.step(w, 0, skill=True)
            self.assertEqual(len([e for e in c.events if e["kind"] == "seal"]), 1)
            self.assertGreater(c.cooldown, 0)

    def test_seal_blockers_projectiles_and_interruption(self):
        c = FoundryEncounter(ROOMS[0])
        c.surfaces = (FLOOR, Surface("test", 429, 456, 94, 195))
        w = Walker(x=380)
        enemy = Enemy("rivet", 468, 94, (456, 498))
        c.foes = [enemy]
        c.bolts = [Bolt(411, 126, 0, 0, owner=enemy), Bolt(477, 126, 0, 0, owner=enemy)]
        c.pulse(w)
        self.assertEqual((enemy.hp, c.wave_length, len(c.bolts)), (48, 49, 1))
        c.step(w, 0, skill=True)
        c.damage_player(w, enemy, w.x, w.y + 30)
        c.step(w, 0)
        self.assertEqual(c.cast_age, -1)

    def test_boss_telegraphs_lock_and_phase_two(self):
        c = FoundryEncounter(ROOMS[-1])
        boss = c.foes[0]
        self.assertIsInstance(boss, Bellkeeper)
        p = Walker(x=boss.x - 50)
        boss.turn = 1
        boss.advance(c, p)
        self.assertEqual((boss.state, boss.targets), ("warn", (p.x,)))
        p.x -= 100
        for _ in range(boss.windup):
            boss.advance(c, p)
        self.assertEqual((boss.state, c.hp), ("active", 100))
        boss.hp = boss.spec.hp // 2
        boss.advance(c, p)
        self.assertEqual((boss.state, boss.phase), ("phase", 2))
        boss.enter("idle")
        boss.turn = 3
        boss.advance(c, p)
        self.assertEqual(len(boss.zones()), 2)
        boss.enter("active")
        for _ in range(12):
            boss.advance(c, p)
        self.assertEqual(c.hp, 79)

    def test_room_transfer_carries_only_intended_state(self):
        c = FoundryEncounter(ROOMS[0])
        c.weapon, c.hp, c.cooldown = "heavy", 66, COOLDOWN
        c.hurt, c.immune, c.cast_age = 12, 42, 12
        nxt = FoundryEncounter(ROOMS[1], c)
        self.assertEqual((nxt.weapon, nxt.hp, nxt.cooldown), ("heavy", 84, COOLDOWN))
        self.assertEqual((nxt.hurt, nxt.immune, nxt.cast_age, nxt.bolts), (0, 0, -1, []))
