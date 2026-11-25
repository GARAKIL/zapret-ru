import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.manager import WinwsManager


@unittest.skipUnless(os.name == "nt", "Windows-only process manager")
class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workdir = Path(self.temp.name)
        self.state_events = []
        self.manager = WinwsManager(
            executable=Path(sys.executable),
            working_dir=self.workdir,
            on_state_change=lambda: self.state_events.append(True),
        )
        self.addCleanup(self.manager.shutdown)

    def test_start_capture_and_stop(self):
        command = [
            "-u",
            "-c",
            "import sys, time; print('hello-zapret'); print('stderr-line', file=sys.stderr); "
            "sys.stdout.flush(); time.sleep(5)",
        ]
        result = self.manager.start(
            command,
            {"preset_id": "general", "mode": "list", "game_filter": False},
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.manager.is_running())
        self.assertGreater(len(self.manager.status()["command"]), 0)

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            logs = self.manager.logs_after(0)["entries"]
            if any("hello-zapret" in entry["text"] for entry in logs) and any(
                "stderr-line" in entry["text"] for entry in logs
            ):
                break
            time.sleep(0.05)
        messages = [entry["text"] for entry in self.manager.logs_after(0)["entries"]]
        self.assertTrue(any("hello-zapret" in message for message in messages))
        self.assertTrue(any("stderr-line" in message for message in messages))

        stopped = self.manager.stop("test stop")
        self.assertTrue(stopped["ok"])
        self.assertFalse(self.manager.is_running())
        self.assertIsNotNone(stopped["status"]["last_exit_code"])
        self.assertTrue(self.state_events)

    def test_immediate_failure_is_reported(self):
        result = self.manager.start(
            ["-c", "import sys; print('failure-marker'); sys.exit(4)"],
            {"preset_id": "general", "mode": "list", "game_filter": False},
        )
        self.assertFalse(result["ok"])
        self.assertFalse(self.manager.is_running())
        self.assertIsNotNone(result["error"])
        messages = [entry["text"] for entry in self.manager.logs_after(0)["entries"]]
        self.assertTrue(any("failure-marker" in message for message in messages))
        self.assertTrue(any("код 4" in message for message in messages))

    def test_clear_logs(self):
        self.manager.append_system_log("first")
        self.manager.append_system_log("second")
        self.assertGreaterEqual(len(self.manager.logs_after(0)["entries"]), 2)
        self.manager.clear_logs()
        self.assertEqual(self.manager.logs_after(0)["entries"], [])


if __name__ == "__main__":
    unittest.main()
