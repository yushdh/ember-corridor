import unittest

from game.combat import Enemy
from game.foundry import COOLDOWN, FoundryEncounter, ROOMS
from game.motion import Walker


class GearTests(unittest.TestCase):
    def test_crate_requires_clearance_distance_and_single_claim(self):
        c = FoundryEncounter(ROOMS[0])
        w = Walker(x=c.room.door[0] - 102)
        self.assertIsNone(c.interact(w))
        self.assertFalse(c.claim(w, "tooth"))
        for e in c.foes:
            e.hp = 0
        w.x -= 100
        self.assertFalse(c.claim(w, "tooth"))
        w.x += 100
        self.assertEqual(c.interact(w), "crate")
        self.assertTrue(c.claim(w, "tooth"))
        self.assertFalse(c.claim(w, "tooth"))
        next_room = FoundryEncounter(ROOMS[1], c)
        self.assertEqual(next_room.melee_damage(16), 22)
        self.assertIsNone(FoundryEncounter(ROOMS[-1]).crate)
        fresh = FoundryEncounter(ROOMS[0], shell_known=True)
        self.assertIsNone(fresh.loadout.equipped)
        self.assertEqual(fresh.loadout.ranks, {})

    def test_equipping_changes_melee_skill_and_mitigation(self):
        c = FoundryEncounter(ROOMS[0], shell_known=True)
        w = Walker(x=400)
        enemy = Enemy("hook", 432, 94, (300, 500))
        c.foes = [enemy]
        c.loadout.fit("tooth")
        c.loadout.fit("tooth")
        c.start_attack(w, "cut")
        c.age = 11
        c.player_strike(w)
        self.assertEqual(enemy.hp, 62 - 16 - 12)
        c.interrupt()
        c.freeze = 0
        c.loadout.fit("tide")
        self.assertEqual(c.melee_damage(16), 16)
        c.step(w, 0, skill=True)
        self.assertEqual(c.cooldown, COOLDOWN - 72)
        c.loadout.fit("shell")
        c.damage_player(w, enemy, w.x, w.y + 24)
        self.assertEqual(c.hp, 100 - enemy.spec.damage + 3)
        self.assertEqual(c.loadout.ranks, {"tooth": 2, "tide": 1, "shell": 1})

    def test_locked_recipe_cannot_be_selected_this_run(self):
        c = FoundryEncounter(ROOMS[0])
        with self.assertRaises(ValueError):
            c.loadout.fit("shell")
        self.assertFalse(c.loadout.ranks)

    def test_preview_preserves_spent_ranks_and_active_equipment(self):
        build = FoundryEncounter(ROOMS[0]).loadout
        build.fit("tooth")
        build.fit("tide")
        for _ in range(3):
            offer = build.after_fit("tooth")
            self.assertEqual((offer.melee_damage(16), offer.seal_period), (28, COOLDOWN))
        self.assertEqual(build.ranks, {"tooth": 1, "tide": 1})
        self.assertEqual((build.equipped, build.seal_period), ("tide", COOLDOWN - 72))
        with self.assertRaises(ValueError):
            build.after_fit("shell")
