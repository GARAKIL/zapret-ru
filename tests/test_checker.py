import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import checker


class CheckerTests(unittest.TestCase):
    def test_services_are_collected_concurrently(self):
        def fake_check(target):
            return {
                "id": target.id,
                "label": target.label,
                "url": target.url,
                "description": target.description,
                "ok": target.id != "discord",
                "status": 200 if target.id != "discord" else None,
                "latency_ms": 12,
                "error": None if target.id != "discord" else "Таймаут",
                "detail": None,
            }

        with patch("core.checker.check_target", side_effect=fake_check):
            result = checker.check_services()

        self.assertTrue(result["ok"])
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["reachable"], 2)
        self.assertEqual(
            [item["id"] for item in result["services"]],
            ["youtube", "discord", "cloudflare"],
        )

    def test_error_classification(self):
        self.assertEqual(checker._error_text(TimeoutError())[0], "Таймаут")
        self.assertEqual(
            checker._error_text(ConnectionResetError())[0], "Сброс соединения"
        )
        self.assertEqual(checker.TIMEOUT_SECONDS, 3.0)


if __name__ == "__main__":
    unittest.main()
