import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.application import ApplicationCore, ApplicationError
from core.environment import REQUIRED_FILES
from core.paths import AppPaths


@unittest.skipUnless(sys.platform == "win32", "Windows-only application core")
class ApplicationCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bin_dir = root / "bin"
        self.bin_dir.mkdir()
        for name in REQUIRED_FILES:
            (self.bin_dir / name).write_bytes(b"stub")
        for name in (
            "quic_initial_www_google_com.bin",
            "tls_clienthello_www_google_com.bin",
            "ACTIVE_DISCORD_UDP.bin",
            "ACTIVE_GAME_UDP.bin",
        ):
            (self.bin_dir / name).write_bytes(b"stub")
        self.paths = AppPaths(
            app_dir=root,
            resource_dir=PROJECT_ROOT,
            data_dir=root,
            bin_dir=self.bin_dir,
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
        self.assertTrue(result["environment"]["ready"])
        self.assertTrue(self.paths.general_list.is_file())
        self.assertTrue(self.paths.exclude_list.is_file())
        self.assertTrue(self.paths.presets_file.is_file())

    def test_settings_and_lists(self):
        result = self.core.update_setting("mode", "global")
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.settings.snapshot()["mode"], "global")
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

    def test_start_bypass_builds_command_and_uses_manager(self):
        with patch("core.application.autostart.is_enabled", return_value=False):
            self.core.bootstrap()
        fake_status = {
            "running": True,
            "pid": 1234,
            "uptime_seconds": 0,
            "started_at": None,
            "last_exit_code": None,
            "last_error": None,
            "active_config": {
                "preset_id": "general",
                "mode": "list",
                "game_filter": True,
            },
            "command": [],
            "command_line": "winws.exe ...",
            "executable": str(self.bin_dir / "winws.exe"),
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
            result = self.core.start_bypass("general", "list", True)
        self.assertTrue(result["ok"])
        args, kwargs = start_mock.call_args
        command = args[0]
        self.assertTrue(
            any(arg.startswith("--wf-tcp=80,443,1024-65535") for arg in command)
        )
        self.assertIn("--dpi-desync=fake,multisplit", command)
        self.assertIn("--filter-l7=discord,stun", command)
        self.assertTrue(any(arg.startswith("--hostlist=") for arg in command))
        self.assertEqual(self.core.settings.snapshot()["game_filter"], True)

    def test_start_without_engine_files_fails(self):
        for name in REQUIRED_FILES:
            (self.bin_dir / name).unlink()
        with self.assertRaises(ApplicationError) as caught:
            self.core.start_bypass("general", "list", False)
        self.assertIn("bin", str(caught.exception))

    def test_reload_presets(self):
        with patch("core.application.autostart.is_enabled", return_value=False):
            self.core.bootstrap()
        result = self.core.reload_presets()
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["presets"]), 5)


if __name__ == "__main__":
    unittest.main()
