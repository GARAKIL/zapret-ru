"""Manual end-to-end smoke test for ApplicationCore and the native engine.

Run from an elevated terminal. The script starts protection for a few seconds,
checks the three services and stops. It is a developer tool, not part of the app.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.application import ApplicationCore  # noqa: E402
from core.paths import get_paths  # noqa: E402


def main() -> int:
    core = ApplicationCore(get_paths())
    try:
        boot = core.bootstrap()
        print(
            "BOOT "
            + json.dumps(
                {
                    "ok": boot.get("ok"),
                    "admin": boot.get("environment", {}).get("admin"),
                    "driver_ready": boot.get("environment", {}).get("driver_ready"),
                    "presets": [item["id"] for item in boot.get("presets", [])],
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
        result = core.start_bypass("smart", "global", False)
        print("START " + json.dumps(result, ensure_ascii=True), flush=True)
        time.sleep(2.0)
        print(
            "STATUS " + json.dumps(core.get_status(), ensure_ascii=True), flush=True
        )
        print(
            "CHECK " + json.dumps(core.check_connectivity(), ensure_ascii=True),
            flush=True,
        )
        print("STOP " + json.dumps(core.stop_bypass(), ensure_ascii=True), flush=True)
        return 0 if result.get("ok") else 1
    finally:
        core.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
