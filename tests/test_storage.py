import sqlite3
import unittest
from signalpost.models import Fact, Source
from signalpost.storage import StateStore


class StorageTest(unittest.TestCase):
    def test_refresh_is_idempotent_and_detects_changes(self):
        db = sqlite3.connect(":memory:")
        store = StateStore(":memory:")
        # StateStore opens its own connection, so use a file-backed temp db for the actual test.
        store.close()
        import tempfile
        path = tempfile.mktemp(suffix=".sqlite3")
        store = StateStore(path)
        src = Source("https://example.test", "2026-09-27T00:00:00Z", "test")
        self.assertIsNone(store.record_fact("123456789", Fact("employees", 10, src, "2025-12-31")))
        self.assertIsNone(store.record_fact("123456789", Fact("employees", 10, src, "2025-12-31")))
        change = store.record_fact("123456789", Fact("employees", 11, src, "2025-12-31"))
        self.assertEqual(change["old_value"], 10)
        self.assertEqual(change["new_value"], 11)
        store.close()


if __name__ == "__main__":
    unittest.main()
