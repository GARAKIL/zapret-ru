"""Manual smoke test for the built-in engine.

Run from an elevated terminal:

    python tools/engine_smoke.py 20

While it runs, open a few HTTPS sites. The script prints packet counters and
stops automatically. It is intentionally not part of the application.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.engine import EngineConfig, NativeEngine  # noqa: E402


def main() -> int:
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    engine = NativeEngine()
    config = EngineConfig(
        profile_id="smart",
        profile_name="Smart",
        split="sni",
        block_quic=False,
        mode="global",
        include=frozenset(),
        exclude=frozenset(),
    )
    result = engine.start(config, {"profile_id": "smart", "profile_name": "Smart"})
    print("START " + json.dumps(result, ensure_ascii=False), flush=True)
    if not result.get("ok"):
        engine.shutdown()
        return 1
    try:
        for _ in range(max(1, seconds)):
            time.sleep(1)
            print(
                "STATUS " + json.dumps(engine.status(), ensure_ascii=False),
                flush=True,
            )
    finally:
        print("STOP " + json.dumps(engine.stop(), ensure_ascii=False), flush=True)
        engine.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
