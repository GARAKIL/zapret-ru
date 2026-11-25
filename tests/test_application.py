import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.application import ApplicationCore, ApplicationError
from core.paths import AppPaths


@unittest.skipUnless(sys.platform == "win32", "Windows-only application core")
class ApplicationCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = AppPaths(
            app_dir=root,
            resource_dir=PROJECT_ROOT,
            data_dir=root,
            bin_dir=root / "bin",
            lists_dir=root / "lists",
            presets_file=root / "presets.json",
            settings_file=root / "settings.json",
            ui_dir=root,
            ui_index=root / "index.html",
            assets_dir=root,
            general_list=root / "lists" / "list-general.txt",
            exclude_list=root / "lists" / "list-exclude.txt",
        )
        patcher = patch("core.environment.is_admin", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher2 = patch("core.environment.find_winws_processes", return_value=[])
        patcher2.start()
        self.addCleanup(patcher2.stop)
        self.core = ApplicationCore(self.paths)
        self.addCleanup(self.core.shutdown)

    def test_bootstrap_seeds_data_and_is_ready(self):
        with patch("core.application.autostart.is_enabled", return_value=False):
            result = self.core.bootstrap()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["presets"]), 5)
        self.assertEqual(result["app"]["engine"], "native")
        self.assertTrue(result["environment"]["ready"])
        self.assertEqual(result["environment"]["engine"], "native")
        self.assertTrue(self.paths.general_list.is_file())
        self.assertTrue(self.paths.exclude_list.is_file())
        self.assertTrue(self.paths.presets_file.is_file())

    def test_settings_and_lists(self):
        result = self.core.update_setting("mode", "global")
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.settings.snapshot()["mode"], "global")
        self.assertTrue(self.core.update_setting("block_quic", False)["ok"])
        self.assertFalse(self.core.settings.snapshot()["block_quic"])
        with self.assertRaises(ApplicationError):
            self.core.update_setting("mode", "bad")
        with self.assertRaises(ApplicationError):
            self.core.update_setting("unknown", True)

        lists = self.core.read_lists()
        self.assertTrue(lists["ok"])
        self.assertIn("youtube.com", lists["lists"]["general"]["content"])

        saved = self.core.save_list("exclude", "ru\r\nxn--p1ai\r\ngosuslugi.ru")
        self.assertTrue(saved["ok"])
        content = self.paths.exclude_list.read_text(encoding="utf-8")
        self.assertEqual(content, "ru\nxn--p1ai\ngosuslugi.ru\n")
        self.assertTrue(self.paths.exclude_list.with_suffix(".txt.bak").is_file())
        self.assertEqual(saved["entries"], 3)

        with self.assertRaises(ApplicationError):
            self.core.save_list("general", "line\x00with-null")
        with self.assertRaises(ApplicationError):
            self.core.save_list("other", "ru")

    def test_start_bypass_builds_native_config(self):
        with patch("core.application.autostart.is_enabled", return_value=False):
            self.core.bootstrap()
        fake_status = {
            "running": True,
            "pid": None,
            "uptime_seconds": 0,
            "started_at": None,
            "last_exit_code": None,
            "last_error": None,
            "active_config": {
                "preset_id": "smart",
                "mode": "global",
                "engine": "native",
            },
            "command": [],
            "command_line": "Умный: split SNI · QUIC → TCP · все программы",
            "executable": "встроенный движок",
            "log_seq": 0,
        }
        with patch.object(
            self.core.manager,
            "start",
            return_value={
                "ok": True,
                "started": True,
                "error": None,
                "status": fake_status,
            },
        ) as start_mock:
            result = self.core.start_bypass("smart", "global", False)
        self.assertTrue(result["ok"])
        config = start_mock.call_args.args[0]
        active = start_mock.call_args.args[1]
        self.assertEqual(config.profile_id, "smart")
        self.assertEqual(config.split, "sni")
        self.assertTrue(config.block_quic)
        self.assertEqual(config.mode, "global")
        self.assertGreater(len(config.exclude), 0)
        self.assertEqual(active["engine"], "native")
        self.assertEqual(self.core.settings.snapshot()["preset_id"], "smart")

    def test_start_requires_admin(self):
        with patch("core.environment.is_admin", return_value=False):
            with self.assertRaises(ApplicationError) as caught:
                self.core.start_bypass("smart", "global", False)
        self.assertIn("администратора", str(caught.exception))

    def test_start_without_driver_fails(self):
        fake_env = {
            "admin": True,
            "engine_error": None,
            "missing_required": ["WinDivert64.dll"],
            "lists": {
                "general": {"present": True},
                "exclude": {"present": True},
            },
        }
        with patch("core.application.scan_environment", return_value=fake_env):
            with self.assertRaises(ApplicationError) as caught:
                self.core.start_bypass("smart", "global", False)
        self.assertIn("драйвер", str(caught.exception))

    def test_save_list_hot_updates_engine(self):
        with patch.object(self.core.manager, "is_running", return_value=True):
            with patch.object(self.core.manager, "update_policy") as update_mock:
                self.core.save_list("general", "youtube.com\n")
        update_mock.assert_called_once()
        include, exclude = update_mock.call_args.args
        self.assertIn("youtube.com", include)

    def test_reload_presets(self):
        with patch("core.application.autostart.is_enabled", return_value=False):
            self.core.bootstrap()
        result = self.core.reload_presets()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["presets"]), 5)

    def test_legacy_presets_are_migrated(self):
        legacy = {
            "schema_version": 1,
            "presets": [{"id": "general", "name": "old"}],
        }
        self.paths.presets_file.write_text(
            json.dumps(legacy), encoding="utf-8"
        )
        from core.paths import ensure_data_files

        ensure_data_files(self.paths)
        loaded = json.loads(self.paths.presets_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], 2)
        self.assertTrue(list(self.paths.data_dir.glob("presets.legacy-*.json")))


if __name__ == "__main__":
    unittest.main()
