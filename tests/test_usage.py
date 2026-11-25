import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.usage import UsageStore  # noqa: E402


class UsageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "usage.json"

    def test_tracks_sessions_and_persists_locally(self):
        usage = UsageStore(self.path)
        usage.start_launcher_session()
        usage.start_bypass()
        time.sleep(0.05)
        usage.end_bypass()
        usage.finish_session()
        snapshot = usage.snapshot()
        self.assertEqual(snapshot["app_launches"], 1)
        self.assertEqual(snapshot["bypass_sessions"], 1)
        self.assertGreaterEqual(snapshot["bypass_seconds"], 0)
        self.assertTrue(snapshot["local_only"])
        self.assertEqual(usage.snapshot(), usage.snapshot())

        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["app_launches"], 1)
        self.assertEqual(persisted["bypass_sessions"], 1)

    def test_new_store_preserves_counters(self):
        first = UsageStore(self.path)
        first.start_launcher_session()
        first.start_bypass()
        first.end_bypass()
        first.finish_session()

        second = UsageStore(self.path)
        second.start_launcher_session()
        snapshot = second.snapshot()
        self.assertEqual(snapshot["app_launches"], 2)
        self.assertEqual(snapshot["bypass_sessions"], 1)

    def test_active_bypass_is_reflected_in_snapshot(self):
        usage = UsageStore(self.path)
        usage.start_launcher_session()
        usage.start_bypass()
        time.sleep(0.03)
        self.assertEqual(usage.snapshot()["active_bypass_seconds"] >= 0, True)
        usage.end_bypass()
        self.assertEqual(usage.snapshot()["active_bypass_seconds"], 0)
        usage.finish_session()

    def test_invalid_file_resets_to_zero(self):
        self.path.write_text("{invalid", encoding="utf-8")
        usage = UsageStore(self.path)
        snapshot = usage.snapshot()
        self.assertEqual(snapshot["app_launches"], 0)
        self.assertEqual(snapshot["bypass_sessions"], 0)
        usage.start_launcher_session()
        self.assertEqual(usage.snapshot()["app_launches"], 1)


if __name__ == "__main__":
    unittest.main()
