import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from game.profile import ProfileStore, atomic_write


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_learning_while_previous_write_is_blocked(self):
        store = ProfileStore(self.root)
        entered, release = Event(), Event()

        def slow_write(path, data):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("gameplay waited for the lesson writer")
            atomic_write(path, data)

        try:
            with patch("game.profile.atomic_write", side_effect=slow_write):
                store.remember({"attack"})
                self.assertTrue(entered.wait(5))
                store.remember({"roll"})
                store.poll()
                self.assertEqual(set(store.data.learned), {"roll", "attack"})
                release.set()
                store.update(setting=(0, 0))
                store.remember({"move"})
        finally:
            release.set()
            store.close()
        data = ProfileStore(self.root).data
        self.assertEqual(data.levels[0], 0)
        self.assertEqual(set(data.learned), {"attack", "roll", "move"})

    def test_failed_lesson_write_retries_and_merges_on_close(self):
        store = ProfileStore(self.root)
        try:
            with patch("game.profile.atomic_write", side_effect=PermissionError):
                store.remember({"roll"})
                store.poll(wait=True)
            self.assertTrue(store.notice)
            self.assertEqual(store.data.learned, ("roll",))
            ProfileStore(self.root).update(unlock=True)
        finally:
            store.close()
        reopened = ProfileStore(self.root).data
        self.assertEqual(reopened.learned, ("roll",))
        self.assertTrue(reopened.shell_known)

    def test_two_windows_merge_updates_and_backup_recovers(self):
        first, second = ProfileStore(self.root), ProfileStore(self.root)
        first.update(unlock=True)
        second.update(setting=(0, 1))
        first.update(setting=(2, 0))
        self.assertEqual(first.data.levels, (1, 2, 0, 2))
        self.assertTrue(second.data.shell_known)
        first.main.write_bytes(b"broken")
        backup = first.backup.read_bytes()
        recovered = ProfileStore(self.root)
        self.assertIn("备份", recovered.notice)
        self.assertTrue(recovered.data.shell_known)
        self.assertEqual(recovered.data.levels, (1, 2, 2, 2))
        self.assertEqual(first.main.read_bytes(), backup)
        self.assertEqual(first.backup.read_bytes(), backup)

    def test_corrupt_or_newer_files_are_preserved(self):
        for main, backup in [(b"[", b"NaN"), (b'{"version":3}', b"{}")]:
            store = ProfileStore(self.root)
            store.main.write_bytes(main)
            store.backup.write_bytes(backup)
            session = ProfileStore(self.root)
            self.assertTrue(session.notice)
            session.update(unlock=True)
            self.assertTrue(session.data.shell_known)
            self.assertEqual(
                (session.main.read_bytes(), session.backup.read_bytes()), (main, backup)
            )

    def test_failed_replace_leaves_main_readable_and_retries_pending_change(self):
        store = ProfileStore(self.root)
        store.update(setting=(3, 1))
        good = store.main.read_bytes()

        def fail_main(path, data):
            if path == store.main:
                raise PermissionError
            atomic_write(path, data)

        with patch("game.profile.atomic_write", side_effect=fail_main):
            store.update(unlock=True)
        self.assertEqual(store.main.read_bytes(), good)
        self.assertTrue(store.notice)
        store.update(setting=(0, 1))
        reopened = ProfileStore(self.root)
        self.assertTrue(reopened.data.shell_known)
        self.assertEqual(reopened.data.levels, (1, 2, 2, 1))
        self.assertEqual(
            set(json.loads(store.main.read_bytes())), {"version", "shell_known", "levels", "learned", "bindings"}
        )

    def test_type_validation_and_missing_primary(self):
        store = ProfileStore(self.root)
        store.update(setting=(1, 0))
        raw = store.main.read_bytes()
        for levels in ([False, 2, 2, 2], [2, 2, 2], [2, 4, 2, 2]):
            store.main.write_text(json.dumps(dict(version=1, shell_known=False, levels=levels)))
            self.assertIn("备份", ProfileStore(self.root).notice)
            self.assertEqual(store.main.read_bytes(), raw)
        store.main.unlink()
        self.assertIn("备份", ProfileStore(self.root).notice)
