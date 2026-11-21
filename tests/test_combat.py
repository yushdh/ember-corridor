import unittest
import json
from pathlib import Path

from PIL import Image

from game.attacks import STRIKES
from game.combat import Encounter, Enemy, Bolt, FORK_HEIGHT, FORK_REACH
from game.motion import Walker
from game.terrain import GROUND_Y, Surface


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.w = Walker(x=330)
        self.c = Encounter()
        self.e = self.c.foes[0]
        self.e.x = 370
        self.e.enter("recover")

    def step(self, n=1, **kwargs):
        for _ in range(n):
            self.c.step(self.w, 0, **kwargs)

    def test_baked_weapon_and_trail_match_damage_frames_in_both_directions(self):
        assets = Path(__file__).resolve().parents[1] / "assets/combat"
        clips = json.loads((assets / "clips.json").read_text(encoding="utf-8"))
        with Image.open(assets / "walker.png") as actor, Image.open(
            assets / "trails.png"
        ) as trails:
            for name, strike in STRIKES.items():
                for i, frame in enumerate(clips[name]["frames"]):
                    grip, tip = strike.blade(i)
                    ax, ay = frame["anchor"]
                    x, y, _, _ = frame["region"]
                    self.assertEqual(frame["weapon_socket"], [ax + grip[0], ay - grip[1]])
                    self.assertEqual(frame["ticks"], strike.ticks[i])
                    self.assertGreater(actor.getpixel((x + ax + tip[0], y + ay - tip[1]))[3], 0)
                    l, t, w, h = clips["trail_" + name]["frames"][i]["region"]
                    active = i in (3, 4)
                    self.assertEqual(bool(trails.crop((l, t, l + w, t + h)).getbbox()), active)
                    for direction in (-1, 1):
                        with self.subTest(name=name, frame=i, facing=direction):
                            encounter, walker = Encounter(), Walker(x=370, facing=direction)
                            enemy = encounter.foes[0]
                            enemy.x = walker.x + direction * tip[0]
                            enemy.y = walker.y + tip[1] - enemy.spec.height // 2
                            before = enemy.rect
                            encounter.start_attack(walker, name)
                            encounter.age = sum(strike.ticks[:i]) + 1
                            encounter.player_strike(walker)
                            encounter.player_strike(walker)
                            hits = [event for event in encounter.events if event["kind"] == "hit"]
                            self.assertEqual(len(hits), int(active))
                            self.assertEqual(
                                enemy.hp, enemy.spec.hp - (strike.damage if active else 0)
                            )
                            if hits:
                                event = hits[0]
                                self.assertTrue(before[0] <= event["x"] <= before[2])
                                self.assertTrue(before[1] <= event["y"] <= before[3])

    def test_fork_locked_direction_and_first_active_tick(self):
        for facing in (-1, 1):
            c = Encounter([Enemy("fork", 300, GROUND_Y, (240, 360))])
            e = c.foes[0]
            w = Walker(x=e.x + facing * 48)
            c.step_enemy(w, e)
            self.assertEqual((e.state, e.facing), ("warn", facing))
            w.x = e.x - facing * 45
            for _ in range(e.spec.windup - 1):
                c.step_enemy(w, e)
            self.assertEqual((e.facing, c.hp, e.state), (facing, 100, "warn"))
            c.step_enemy(w, e)
            self.assertEqual((c.hp, e.state), (100, "active"))
            w.x = e.x + facing * 48
            for _ in range(e.spec.active):
                c.step_enemy(w, e)
            self.assertEqual((e.state, c.hp), ("recover", 84))
            self.assertEqual([v["y"] for v in c.events if v["kind"] == "hurt"],
                             [GROUND_Y + FORK_HEIGHT])

    def test_fork_reach_jump_and_wall(self):
        wall = Surface("stop", 320, 324, GROUND_Y, GROUND_Y + 55)
        for gap, rise, surfaces, hp in (
            (FORK_REACH + 11, 0, (), 84), (FORK_REACH + 12, 0, (), 100),
            (46, FORK_HEIGHT + 1, (), 100), (46, 0, (wall,), 100)
        ):
            with self.subTest(gap=gap, rise=rise, wall=bool(surfaces)):
                e = Enemy("fork", 300, GROUND_Y, (240, 360), facing=1)
                c = Encounter([e], surfaces)
                e.enter("active")
                c.step_enemy(Walker(x=e.x + gap, y=e.y + rise), e)
                self.assertEqual(c.hp, hp)

    def test_return_chain_only_hits_on_reel_and_spends_once(self):
        for facing in (-1, 1):
            with self.subTest(facing=facing):
                enemy = Enemy("chain", 300, GROUND_Y, (220, 380))
                c = Encounter([enemy], ())
                w = Walker(x=enemy.x + facing * 70)
                c.step_enemy(w, enemy)
                for _ in range(enemy.spec.windup):
                    c.step_enemy(w, enemy)
                self.assertEqual((enemy.facing, enemy.state, c.hp), (facing, "active", 100))
                for _ in range(enemy.spec.active):
                    c.immune = 0
                    c.step_enemy(w, enemy)
                self.assertEqual((enemy.state, c.hp), ("recover", 82))
                self.assertEqual(sum(ev["kind"] == "hurt" for ev in c.events), 1)

    def test_return_chain_clearance_cover_and_interrupt(self):
        wall = Surface("pillar", 330, 335, GROUND_Y, GROUND_Y + 80)
        for tucked, walls, state in ((True, (), "active"), (False, (wall,), "active"), (False, (), "hurt")):
            with self.subTest(tucked=tucked, wall=bool(walls), state=state):
                enemy = Enemy("chain", 300, GROUND_Y, (220, 380), facing=1)
                c = Encounter([enemy], walls)
                w = Walker(x=350, tucked=tucked)
                enemy.enter(state)
                for _ in range(enemy.spec.active):
                    c.step_enemy(w, enemy)
                self.assertEqual(c.hp, 100)
                self.assertFalse(w.invulnerable)

    def test_effective_frames_and_instance_dedup(self):
        self.step(attack=True)
        self.step(sum(STRIKES["cut"].ticks[:3]) - 1)
        self.assertEqual(self.e.hp, 62)
        self.step()
        self.assertEqual(self.e.hp, 46)
        self.step(15)
        hits = [e for e in self.c.events if e["kind"] == "hit"]
        self.assertEqual([(e["frame"], e["attack_id"]) for e in hits], [(3, 1)])
        self.assertEqual(self.e.hp, 46)

    def test_knockback_waits_for_contact_hold_to_end(self):
        contact_x = self.e.x
        self.step(attack=True)
        while not self.c.freeze:
            self.step()
        self.assertEqual(self.e.hp, 46)
        while self.c.freeze:
            self.assertEqual(self.e.x, contact_x)
            self.step()
        self.step()
        self.assertEqual(self.e.x, contact_x + 3)

    def test_duplicate_species_are_individual_targets(self):
        second = Enemy("hook", 370, GROUND_Y, (260, 519))
        self.c.foes.append(second)
        self.step(attack=True)
        self.step(20)
        self.assertEqual((self.e.hp, second.hp), (46, 46))

    def test_buffer_chains_three_strikes_and_mirrors(self):
        self.w.x, self.w.facing, self.e.x = 399, -1, 356
        self.step(attack=True)
        for _ in range(115):
            self.step(attack=self.c.attack in ("cut", "liftcut") and self.c.age == 17)
        hits = [e for e in self.c.events if e["kind"] == "hit"]
        self.assertEqual([e["action"] for e in hits], ["cut", "liftcut", "thrust"])
        self.assertEqual([e["hp"] for e in hits], [46, 27, 0])

    def test_heavy_exposure_and_armor_break(self):
        self.w.x = 898
        armor = self.c.foes[2]
        armor.x = 940
        armor.enter("warn")
        self.step(slot="heavy", attack=True)
        self.step(28, roll=True, slot="light")
        self.assertEqual((self.c.weapon, armor.hp, self.w.roll_age), ("heavy", 98, -1))
        self.step(10)
        self.assertEqual((armor.hp, armor.state), (55, "hurt"))
        self.assertGreater(self.c.freeze, 0)

    def test_light_roll_cancel_only_in_recovery(self):
        self.e.x = 500
        self.step(attack=True)
        self.step(roll=True)
        self.assertEqual((self.c.attack, self.w.roll_age), ("cut", -1))
        self.step(STRIKES["cut"].cancel_tick - 2)
        self.step(roll=True)
        self.assertEqual((self.c.attack, self.w.roll_age), (None, 0))

    def test_wall_and_platform_blocking(self):
        self.w.x = 521
        self.e.x = 549
        self.step(attack=True)
        self.step(35)
        self.assertEqual(self.e.hp, 62)
        # A bolt expires against the stone step before its endpoint reaches the target.
        self.w.x = 500
        self.c.bolts = [Bolt(690, 120, -220, 0)]
        self.c.step_bolts(self.w)
        self.assertEqual((self.c.hp, len(self.c.bolts)), (100, 0))

    def test_roll_evades_once_and_hurt_interrupts(self):
        self.e.x = self.w.x + 25
        self.e.facing = -1
        self.e.enter("active")
        self.w.roll_age = 5
        self.c.step_enemy(self.w, self.e)
        self.assertEqual((self.c.hp, self.c.events[-1]["kind"]), (100, "evade"))
        self.w.roll_age = -1
        self.c.step_enemy(self.w, self.e)
        self.assertEqual(self.c.hp, 100)
        self.c.start_attack(self.w, "breaker")
        self.c.damage_player(self.w, self.e, self.w.x, 120)
        self.assertEqual((self.c.hp, self.c.attack), (87, None))
        self.c.damage_player(self.w, self.e, self.w.x, 120)
        self.assertEqual(self.c.hp, 87)

    def test_death_clears_every_pending_action(self):
        self.c.hp = 8
        self.c.start_attack(self.w, "cut")
        self.c.buffer = 15
        self.c.bolts.append(Bolt(300, 124, 2, 0))
        self.c.damage_player(self.w, self.e, 330, 124)
        self.step(40, attack=True, roll=True)
        self.assertEqual(
            (self.c.hp, self.c.attack, self.c.buffer, self.c.immune, self.c.bolts),
            (0, None, 0, 0, []),
        )
        self.assertFalse(self.w.invulnerable)

    def test_ranged_windup_uses_locked_aim_and_one_projectile(self):
        e = self.c.foes[1]
        self.w.x, self.w.y = 550, 141
        self.c.step_enemy(self.w, e)
        self.assertEqual(e.state, "warn")
        aim = e.aim
        self.w.y += 60
        for _ in range(e.spec.windup - 1):
            self.c.step_enemy(self.w, e)
        self.assertFalse(self.c.bolts)
        for _ in range(8):
            self.c.step_enemy(self.w, e)
        self.assertEqual(len(self.c.bolts), 1)
        self.assertAlmostEqual(self.c.bolts[0].dy, aim[1] * 2.6)

    def test_light_does_not_interrupt_committed_ram(self):
        self.w.x = 898
        e = self.c.foes[2]
        e.x = 940
        e.enter("warn")
        self.step(attack=True)
        self.step(13)
        self.assertEqual((e.state, e.hp), ("warn", 82))
