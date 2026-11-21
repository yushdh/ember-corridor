import unittest

from game.motion import (
    Walker,
    STEP,
    GRACE_TICKS,
    DROP_CHORD_TICKS,
    BUFFER_TICKS,
    INVULN_START,
    INVULN_END,
    ROLL_TICKS,
    ROLL_RECHARGE,
    BODY_HALF_WIDTH,
    STAND_HEIGHT,
)
from game.terrain import GROUND_Y, FLOOR, SURFACES, Surface

FACES = {s.name: s for s in SURFACES}


def tick(actor, count, axis=0, **keys):
    for _ in range(count):
        actor.step(axis, **keys)


class MovementTests(unittest.TestCase):
    def test_running_exhaustion_and_recovery(self):
        w = Walker(x=35)
        for _ in range(760):
            w.step(1, surfaces=(FLOOR,))
        self.assertTrue(w.winded)
        self.assertLess(w.speed, 154)
        for _ in range(165):
            w.step(0, surfaces=(FLOOR,))
        self.assertFalse(w.winded)
        self.assertGreater(w.stamina, 30)

    def test_stamina_cost_requires_ground_displacement(self):
        w = Walker(x=100)
        for _ in range(120):
            w.step(1, surfaces=(FLOOR,))
        self.assertAlmostEqual(w.stamina, 84)
        w.step(1, jump=True, held=True, surfaces=(FLOOR,))
        self.assertAlmostEqual(w.stamina, 84)
        w = Walker(x=100, stamina=70)
        wall = Surface("wall", 111, 121, GROUND_Y, GROUND_Y + 100)
        w.step(1, surfaces=(FLOOR,wall))
        self.assertGreater(w.stamina, 70)

    def test_hold_and_release(self):
        def height(hold_ticks):
            w = Walker()
            peak = w.y
            for i in range(150):
                w.step(0, jump=i == 0, held=i < hold_ticks)
                peak = max(peak, w.y)
            self.assertEqual((w.support, w.y), (FLOOR, GROUND_Y))
            return peak - GROUND_Y

        self.assertGreater(height(120) - height(2), 45)

    def test_grace_last_tick_and_expiry(self):
        for delay, allowed in [(GRACE_TICKS - 1, True), (GRACE_TICKS, False)]:
            s = FACES["sling"]
            w = Walker(x=s.right + BODY_HALF_WIDTH - 0.1, y=s.top, support=s, speed=154)
            w.step(1)
            self.assertIsNone(w.support)
            self.assertEqual(w.grace, GRACE_TICKS)
            tick(w, delay, 1)
            w.step(1, jump=True, held=True)
            self.assertEqual(w.vy > 0, allowed)

    def test_jump_buffer_near_and_far(self):
        for y, expect in [(100, True), (160, False)]:
            w = Walker(y=y, vy=-130, support=None)
            w.step(0, jump=True, held=True)
            rose = False
            for _ in range(80):
                w.step(0, held=True)
                rose |= w.vy > 0
            self.assertEqual(rose, expect)

    def test_no_air_rejump_or_wall_grace(self):
        w = Walker()
        w.step(0, jump=True, held=True)
        tick(w, 18, held=True)
        old = w.vy
        w.step(0, jump=True, held=True)
        self.assertLess(w.vy, old)
        self.assertEqual(w.grace, 0)

    def test_stacked_one_way_drop_ignores_only_current_deck(self):
        upper = Surface("upper", 250, 350, 155, 165, True)
        lower = Surface("lower", 250, 350, 125, 134, True)
        w = Walker(x=286, y=165, support=upper)
        world = (FLOOR, upper, lower)
        w.step(0, jump=True, drop=True, surfaces=world)
        tick(w, 80, surfaces=world)
        self.assertIs(w.support, lower)
        self.assertIsNone(w.ignore)

    def test_drop_chord_last_tick_and_expiry(self):
        deck = FACES["sling"]
        for gap, expected in ((DROP_CHORD_TICKS, FLOOR), (DROP_CHORD_TICKS + 1, deck)):
            w = Walker(x=(deck.left + deck.right) / 2, y=deck.top, support=deck)
            world = (FLOOR, deck)
            w.step(0, jump=True, held=True, surfaces=world)
            tick(w, gap - 1, held=True, surfaces=world)
            w.step(0, held=True, drop=True, surfaces=world)
            tick(w, 120, surfaces=world)
            self.assertIs(w.support, expected)

    def test_buffered_drop_at_landing_and_solid_floor(self):
        deck = FACES["sling"]
        w = Walker(x=(deck.left + deck.right) / 2, y=deck.top + 1, vy=-200, support=None)
        world = (FLOOR, deck)
        w.step(0, jump=True, held=True, drop=True, surfaces=world)
        tick(w, 120, surfaces=world)
        self.assertIs(w.support, FLOOR)
        w.step(0, jump=True, held=True, drop=True, surfaces=world)
        self.assertGreater(w.vy, 0)

    def test_ceiling_sweep_walls_and_flush_corner(self):
        beam = FACES["weighbridge"]
        w = Walker(x=202)
        w.move_y(180, SURFACES)
        self.assertEqual(w.y, beam.bottom - STAND_HEIGHT)
        thin = Surface("iron-sheet", 410, 411, GROUND_Y, GROUND_Y + 80)
        for start, travel, stop in [(300, 240, 399), (510, -240, 422)]:
            w = Walker(x=start)
            w.move_x(travel, (thin,))
            self.assertEqual(w.x, stop)
        s = FACES["landing"]
        for start, dx, stop in [
            (505, 400, s.left - BODY_HALF_WIDTH),
            (695, -400, s.right + BODY_HALF_WIDTH),
        ]:
            w = Walker(x=start)
            w.move_x(dx, (s,))
            self.assertEqual(w.x, stop)
        w = Walker(x=s.left - BODY_HALF_WIDTH, y=s.top)
        w.move_x(5, (s,))
        w.move_y(-27, (s,))
        self.assertIs(w.support, s)

    def test_roll_timing_cooldown_lock_and_recovery(self):
        w = Walker(x=310)
        for i in range(ROLL_TICKS):
            w.step(0 if i == 0 else -1, roll=i == 0, jump=i == 10, held=True)
            self.assertEqual(w.invulnerable, INVULN_START <= i < INVULN_END)
            self.assertEqual((w.action, w.facing), ("roll", 1))
        w.step(0, roll=True)
        self.assertFalse(w.invulnerable)
        self.assertEqual(w.roll_age, -1)
        tick(w, ROLL_RECHARGE - ROLL_TICKS - 1)
        w.step(0, roll=True)
        self.assertEqual(w.roll_age, 0)
        tick(w, INVULN_START)
        w.clear_transients()
        self.assertFalse(w.invulnerable)

    def test_roll_wall_and_clearance(self):
        s = FACES["landing"]
        w = Walker(x=s.left - 25)
        w.step(1, roll=True)
        tick(w, 50, 1)
        self.assertEqual(w.x, s.left - BODY_HALF_WIDTH)
        roof = FACES["gantry"]
        w = Walker(x=roof.left - 60)
        w.step(1, roll=True)
        tick(w, ROLL_TICKS, 1)
        self.assertEqual(w.action, "tuck")
        self.assertFalse(w.invulnerable)
        tick(w, 130, 1)
        self.assertGreater(w.x, roof.right + BODY_HALF_WIDTH)
        self.assertFalse(w.tucked)
        self.assertEqual(w.height, STAND_HEIGHT)

    def test_hz_consistency_with_timed_controls(self):
        def simulate(hz):
            w = Walker()
            remaining = 0
            ticks = 0
            trace = []
            for _ in range(2 * hz):
                remaining += 1 / hz
                while remaining + 1e-12 >= STEP:
                    w.step(
                        1 if ticks < 170 else -1,
                        jump=ticks == 20,
                        held=20 <= ticks < 52,
                        roll=ticks == 128,
                    )
                    trace.append((w.x, w.y, w.vy, w.action, w.invulnerable))
                    ticks += 1
                    remaining -= STEP
            return trace

        self.assertEqual(simulate(30), simulate(60))
        self.assertEqual(simulate(144), simulate(60))
