import unittest
from pathlib import Path

from game.first_play import FirstPlayRecord


class FirstPlayTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.record = FirstPlayRecord(Path("."), "automated", lambda: self.now)

    def step(self, seconds, state, room="门廊"):
        self.now = seconds
        return self.record.observe(state, room)

    def test_late_start_retry_pause_and_forge(self):
        self.assertFalse(self.step(0, "title"))
        self.step(20, "play")
        self.step(25, "dead")
        self.step(29, "play")
        self.step(31, "pause")
        self.step(34, "play")
        self.step(35, "play", "泵房")
        self.step(40, "forge", "泵房")
        self.step(44, "play", "泵房")
        self.step(48, "won", "泵房")
        self.assertFalse(self.step(75, "closed"))
        r = self.record.snapshot()
        self.assertEqual((r["wall_ms"], r["play_ms"], r["forge_ms"], r["pause_ms"],
                          r["retry_wait_ms"]), (28000, 17000, 4000, 3000, 4000))
        self.assertEqual((r["attempts"], r["deaths"], r["outcome"]), (2, 1, "won"))
        self.assertEqual([room["engaged_ms"] for room in r["rooms"]], [5000, 3000, 13000])

    def test_exit_from_title_and_early_exit(self):
        self.step(3, "closed")
        self.assertEqual(self.record.snapshot()["outcome"], "closed_before_start")
        self.assertEqual(self.record.snapshot()["attempts"], 0)
        record = FirstPlayRecord(Path("."), clock=lambda: self.now)
        record.observe("play", "门廊")
        self.now += 9
        record.observe("closed", "门廊")
        self.assertEqual(record.snapshot()["play_ms"], 9000)
