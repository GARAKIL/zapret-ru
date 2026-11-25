import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.presets import (
    PresetError,
    PresetStore,
    normalize_port_specs,
    parse_port_spec,
)


class PresetStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PresetStore(PROJECT_ROOT / "presets.json")
        cls.lists = PROJECT_ROOT / "lists"
        cls.general = cls.lists / "list-general.txt"
        cls.exclude = cls.lists / "list-exclude.txt"

    def make_bin(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        bin_dir = Path(temp.name)
        for name in (
            "quic_initial_www_google_com.bin",
            "tls_clienthello_www_google_com.bin",
            "ACTIVE_DISCORD_UDP.bin",
            "ACTIVE_GAME_UDP.bin",
        ):
            (bin_dir / name).write_bytes(b"\x00" + name.encode())
        return bin_dir

    def test_has_five_presets(self):
        presets = self.store.public_presets()
        self.assertEqual(
            [preset["id"] for preset in presets],
            ["general", "alt1", "alt2", "alt3", "alt4"],
        )
        self.assertTrue(all(preset["description"] for preset in presets))
        general = self.store.get("general")
        self.assertIn("--dpi-desync=fake,multisplit", general.blocks["tcp"])
        self.assertIn("--dpi-desync-fooling=ts", general.blocks["tcp"])
        self.assertIn(
            "--dpi-desync-fake-quic=@BIN/quic_initial_www_google_com.bin",
            general.blocks["quic"],
        )
        self.assertTrue(
            any("fakedsplit" in arg for arg in self.store.get("alt1").blocks["tcp"])
        )
        self.assertIn(
            "--dpi-desync-fooling=md5sig", self.store.get("alt2").blocks["tcp"]
        )
        self.assertIn(
            "--dpi-desync=syndata,fake,multisplit", self.store.get("alt3").blocks["tcp"]
        )
        self.assertIn("--dpi-desync=multisplit", self.store.get("alt4").blocks["tcp"])
        self.assertFalse(
            any(
                "--dpi-desync-fake" in arg
                for arg in self.store.get("alt4").blocks["tcp"]
            )
        )

    def test_list_mode_and_game_filter_command(self):
        bin_dir = self.make_bin()
        result = self.store.build(
            "general", "list", True, self.general, self.exclude, bin_dir
        )
        command = result.command
        self.assertEqual(command[0], "--wf-tcp=80,443,1024-65535")
        self.assertEqual(command[1], "--wf-udp=443,1024-65535")
        self.assertIn(f"--hostlist={self.general.resolve()}", command)
        self.assertIn(f"--hostlist-exclude={self.exclude.resolve()}", command)
        self.assertIn("--filter-l7=quic", command)
        self.assertIn("--filter-l7=discord,stun", command)
        self.assertIn("--filter-tcp=1024-65535", command)
        self.assertIn("--filter-udp=1024-65535", command)
        self.assertEqual(command.count("--new"), 4)
        self.assertTrue(any("quic_initial" in arg and "@" in arg for arg in command))
        self.assertFalse(result.skipped_files)

    def test_global_mode_omits_include_list(self):
        bin_dir = self.make_bin()
        result = self.store.build(
            "general", "global", False, self.general, self.exclude, bin_dir
        )
        self.assertFalse(any(arg.startswith("--hostlist=") for arg in result.command))
        self.assertTrue(
            any(arg.startswith("--hostlist-exclude=") for arg in result.command)
        )
        self.assertEqual(result.wf_tcp, "80,443")
        self.assertEqual(result.wf_udp, "443,19294-19344,50000-65535")

    def test_missing_bin_files_are_skipped_with_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.store.build(
                "general", "list", False, self.general, self.exclude, Path(temp)
            )
        self.assertIn("quic_initial_www_google_com.bin", result.skipped_files)
        self.assertTrue(
            any("Не найдены .bin-файлы" in warning for warning in result.warnings)
        )
        self.assertFalse(
            any("quic_initial_www_google_com.bin" in arg for arg in result.command)
        )

    def test_every_preset_builds_in_both_modes(self):
        bin_dir = self.make_bin()
        for preset in ("general", "alt1", "alt2", "alt3", "alt4"):
            for mode in ("list", "global"):
                for game in (False, True):
                    result = self.store.build(
                        preset, mode, game, self.general, self.exclude, bin_dir
                    )
                    self.assertTrue(result.command)
                    self.assertTrue(
                        all(isinstance(part, str) and part for part in result.command)
                    )
                    self.assertNotEqual(result.command[0], "--new")
                    for index, argument in enumerate(result.command):
                        if argument == "--new":
                            self.assertLess(index, len(result.command) - 1)
                            self.assertNotEqual(result.command[index + 1], "--new")

    def test_unknown_preset_and_bad_mode(self):
        with self.assertRaises(PresetError):
            self.store.build(
                "nope", "list", False, self.general, self.exclude, PROJECT_ROOT / "bin"
            )
        with self.assertRaises(PresetError):
            self.store.build(
                "general",
                "invalid",
                False,
                self.general,
                self.exclude,
                PROJECT_ROOT / "bin",
            )

    def test_banned_arguments_rejected(self):
        raw = json.loads((PROJECT_ROOT / "presets.json").read_text(encoding="utf-8"))
        raw["presets"][0]["tcp"].append("--new")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_invalid_presets_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "presets.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(PresetError):
                PresetStore(path)

    def test_port_normalization(self):
        self.assertEqual(
            normalize_port_specs(["80,443", "1024-65535"]), "80,443,1024-65535"
        )
        self.assertEqual(normalize_port_specs(["443,1024-65535"]), "443,1024-65535")
        self.assertEqual(
            normalize_port_specs(["50000-65535", "443,19294-19344"]),
            "443,19294-19344,50000-65535",
        )
        with self.assertRaises(PresetError):
            parse_port_spec("80-70")
        with self.assertRaises(PresetError):
            parse_port_spec("0-8")
        with self.assertRaises(PresetError):
            parse_port_spec("abc")


if __name__ == "__main__":
    unittest.main()
