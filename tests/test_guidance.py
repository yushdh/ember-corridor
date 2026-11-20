import json
import unittest
from tempfile import TemporaryDirectory

from game.guidance import DEFAULT_KEYS, FADE, LIFETIME, Guidance
from game.profile import ProfileStore


class LessonTests(unittest.TestCase):
    def test_timeout_left_zone_scene_change_and_success(self):
        guide = Guidance()
        guide.observe(["move"], [])
        for i in range(660):
            guide.advance(1 / 60)
            guide.observe(["move"], [])
        self.assertIsNone(guide.active)
        guide.observe(["jump"], [])
        guide.observe([], [])
        guide.observe(["jump"], [])
        self.assertIsNone(guide.active)
        guide.observe(["attack"], [])
        guide.observe(["roll", "attack"], [])
        self.assertEqual(guide.active, "roll")
        guide.observe(["roll"], ["roll"])
        self.assertAlmostEqual(guide.remaining, FADE)
        guide.advance(FADE)
        guide.clear()
        guide.observe(["jump", "attack", "roll", "move"], [])
        self.assertIsNone(guide.active)

    def test_only_key_pulses_twice(self):
        guide = Guidance()
        guide.observe(["move"], [])
        dips = []
        previous = False
        for _ in range(130):
            dip = guide.key_opacity < 240
            if dip and not previous:
                dips.append(guide.age)
            previous = dip
            self.assertEqual(guide.opacity, 255)
            guide.advance(0.01)
        self.assertEqual(len(dips), 2)
        guide.advance(LIFETIME)
        self.assertIsNone(guide.active)

    def test_migrate_old_progress_and_merge_mastery(self):
        with TemporaryDirectory() as tmp:
            a = ProfileStore(tmp)
            a.main.write_text(json.dumps(dict(version=1, shell_known=True, levels=[1, 3, 0, 2])))
            a, b = ProfileStore(tmp), ProfileStore(tmp)
            self.assertEqual(a.data.learned, ())
            a.update(learned=["jump"], bindings=("H", *DEFAULT_KEYS[1:]))
            b.update(learned=["roll"])
            current = ProfileStore(tmp).data
            self.assertEqual(current.bindings[0], "H")
            self.assertEqual(current.learned, ("jump", "roll"))
            self.assertTrue(current.shell_known)
            self.assertEqual(current.levels, (1, 3, 0, 2))
            guide = Guidance(current.learned)
            guide.observe(["jump", "roll"], [])
            self.assertIsNone(guide.active)
