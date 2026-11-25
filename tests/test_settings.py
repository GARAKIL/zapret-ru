import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.settings import DEFAULTS, SettingsError, SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "settings.json"

    def test_defaults_when_missing(self):
        store = SettingsStore(self.path)
        self.assertEqual(store.load(), DEFAULTS)
        self.assertFalse(self.path.exists())

    def test_update_is_atomic_and_validated(self):
        store = SettingsStore(self.path)
        store.load()
        result = store.update({"mode": "global", "game_filter": True, "block_quic": False})
        self.assertEqual(result["mode"], "global")
        self.assertTrue(result["game_filter"])
        self.assertFalse(result["block_quic"])
        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["mode"], "global")

        with self.assertRaises(SettingsError):
            store.update({"mode": "everything"})
        with self.assertRaises(SettingsError):
            store.update({"game_filter": "yes"})
        with self.assertRaises(SettingsError):
            store.update({"unknown": True})

    def test_corrupt_file_is_quarantined(self):
        self.path.write_text("{not valid json", encoding="utf-8")
        store = SettingsStore(self.path)
        loaded = store.load()
        self.assertEqual(loaded, DEFAULTS)
        self.assertIsNotNone(store.load_warning)
        self.assertTrue(list(self.path.parent.glob("settings.corrupt-*.json")))
        self.assertFalse(self.path.exists())

    def test_partial_file_merges_defaults(self):
        self.path.write_text('{"mode": "list", "last_tab": "logs"}', encoding="utf-8")
        store = SettingsStore(self.path)
        loaded = store.load()
        self.assertEqual(loaded["mode"], "list")
        self.assertEqual(loaded["last_tab"], "logs")
        self.assertEqual(loaded["preset_id"], DEFAULTS["preset_id"])


if __name__ == "__main__":
    unittest.main()
