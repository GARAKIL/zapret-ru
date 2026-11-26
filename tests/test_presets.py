import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.presets import PresetError, PresetStore


class PresetStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PresetStore(PROJECT_ROOT / "presets.json")

    def test_has_native_profiles(self):
        presets = self.store.public_presets()
        self.assertEqual(
            [preset["id"] for preset in presets],
            [
                "smart",
                "sni_start",
                "sni_end",
                "split1",
                "split2",
                "split4",
                "tcp_only",
            ],
        )
        self.assertEqual(self.store.default_id, "smart")
        smart = self.store.get("smart")
        self.assertEqual(smart.split, "sni")
        self.assertTrue(smart.block_quic)
        self.assertFalse(self.store.get("tcp_only").block_quic)
        self.assertEqual(self.store.get("sni_start").split, "sni-start")
        self.assertEqual(self.store.get("sni_end").split, "sni-end")
        self.assertEqual(self.store.get("split4").split, 4)

    def test_profile_public_shape(self):
        item = self.store.get("smart").public()
        for key in ("id", "name", "label", "description", "split", "block_quic"):
            self.assertIn(key, item)
        self.assertTrue(item["description"])

    def test_invalid_split(self):
        raw = json.loads((PROJECT_ROOT / "presets.json").read_text(encoding="utf-8"))
        raw["presets"][0]["split"] = 999
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_invalid_schema(self):
        raw = json.loads((PROJECT_ROOT / "presets.json").read_text(encoding="utf-8"))
        raw["schema_version"] = 1
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_duplicate_id(self):
        raw = json.loads((PROJECT_ROOT / "presets.json").read_text(encoding="utf-8"))
        raw["presets"].append(dict(raw["presets"][0]))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_unknown_profile(self):
        with self.assertRaises(PresetError):
            self.store.get("nope")


if __name__ == "__main__":
    unittest.main()
