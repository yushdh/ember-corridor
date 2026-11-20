import unittest
from dataclasses import replace
from random import Random
from unittest.mock import patch

from game.foundry import ledge
from game.routes import (
    ALTERNATES,
    ATTEMPTS,
    CLASSIC,
    candidate,
    connected,
    generate,
    supported,
    walk_template,
)


def broken_gallery():
    original = CLASSIC[3]
    high = ledge("isolated", 650, 760, 334)
    return replace(
        original,
        room=replace(original.room, valve=(705, 334), surfaces=(*original.room.surfaces, high)),
    )


class RouteTests(unittest.TestCase):
    def test_v1_seed_replay_and_variety(self):
        expected = ["gate", "gallery-west", "pump-steps", "sluice-twins", "bell"]
        self.assertEqual(generate(17).record()["templates"], expected)
        rng = Random(71)
        for _ in range(800):
            rng.random()
        self.assertEqual(generate(17).record()["templates"], expected)
        self.assertNotEqual(generate(18).rooms, generate(17).rooms)
        self.assertEqual(generate(0).seed, 0)
        self.assertEqual(generate(2**32 - 1).seed, 2**32 - 1)
        for seed in (-1, 2**32):
            with self.assertRaises(ValueError):
                generate(seed)

    def test_exit_chain_and_real_landings(self):
        self.assertTrue(all(walk_template(t) for t in (*CLASSIC, *ALTERNATES)))
        self.assertFalse(connected((CLASSIC[0], CLASSIC[0], *CLASSIC[2:])))
        self.assertFalse(connected(CLASSIC[::-1]))
        broken = broken_gallery()
        self.assertTrue(supported(broken.room, *broken.room.valve))
        self.assertFalse(walk_template(broken))
        # A solid wall splits the path even though all objective markers have a floor.
        wall = replace(CLASSIC[0].room.surfaces[-1], left=535, right=559, top=354)
        room = replace(CLASSIC[0].room, surfaces=(*CLASSIC[0].room.surfaces, wall))
        self.assertFalse(walk_template(replace(CLASSIC[0], room=room)))
        pump = CLASSIC[1]
        kind, x, y, _ = pump.room.guards[0]
        bad_patrol = ((kind, x, y, (400, 580)), *pump.room.guards[1:])
        self.assertFalse(walk_template(replace(pump, room=replace(pump.room, guards=bad_patrol))))

    def test_invalid_candidate_retries_then_falls_back(self):
        bad = (*CLASSIC[:3], broken_gallery(), CLASSIC[-1])
        good = candidate(Random(17))
        with patch("game.routes.candidate", side_effect=[bad, good]):
            route = generate(17)
            self.assertEqual((route.attempts, route.rooms, route.fallback), (2, good, False))
        with patch("game.routes.candidate", return_value=bad) as choose:
            route = generate(17)
        self.assertEqual((choose.call_count, route.attempts), (ATTEMPTS, ATTEMPTS))
        self.assertTrue(route.fallback)
        self.assertEqual(route.rooms, generate(None).rooms)
        self.assertEqual(route.seed, 17)
