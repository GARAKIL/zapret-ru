"""Local-only usage statistics.

This intentionally never sends anything over the network. It exists so the
settings screen can show how long the launcher and bypass were used on this PC.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "app_launches": 0,
    "bypass_sessions": 0,
    "bypass_seconds": 0,
    "launcher_seconds": 0,
    "first_seen": None,
    "last_seen": None,
}


class UsageStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data = dict(_DEFAULTS)
        self._session_started: float | None = None
        self._bypass_started: float | None = None
        self.load()

    def load(self) -> None:
        with self._lock:
            self._data = dict(_DEFAULTS)
            if not self._path.is_file():
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
                if not isinstance(raw, dict):
                    raise ValueError("usage.json должен быть объектом")
                for key in (
                    "app_launches",
                    "bypass_sessions",
                    "bypass_seconds",
                    "launcher_seconds",
                ):
                    value = raw.get(key, 0)
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError(f"Некорректное поле {key}")
                    self._data[key] = max(0, int(value))
                for key in ("first_seen", "last_seen"):
                    value = raw.get(key)
                    if value is None:
                        continue
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError(f"Некорректное поле {key}")
                    self._data[key] = float(value)
            except (OSError, ValueError, TypeError) as exc:
                log.warning("usage.json is invalid and will be reset: %s", exc)
                self._data = dict(_DEFAULTS)

    def start_launcher_session(self) -> None:
        with self._lock:
            now = time.time()
            if not self._data["first_seen"]:
                self._data["first_seen"] = now
            self._data["app_launches"] += 1
            self._data["last_seen"] = now
            self._session_started = time.monotonic()
            self._save()

    def start_bypass(self) -> None:
        with self._lock:
            if self._bypass_started is not None:
                return
            self._bypass_started = time.monotonic()
            self._data["bypass_sessions"] += 1
            self._data["last_seen"] = time.time()
            self._save()

    def end_bypass(self) -> None:
        with self._lock:
            if self._bypass_started is None:
                return
            elapsed = max(0, int(time.monotonic() - self._bypass_started))
            self._data["bypass_seconds"] += elapsed
            self._bypass_started = None
            self._data["last_seen"] = time.time()
            self._save()

    def finish_session(self) -> None:
        with self._lock:
            self.end_bypass()
            if self._session_started is not None:
                elapsed = max(0, int(time.monotonic() - self._session_started))
                self._data["launcher_seconds"] += elapsed
                self._session_started = None
            self._data["last_seen"] = time.time()
            self._save()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            session_seconds = 0
            if self._session_started is not None:
                session_seconds = max(0, int(time.monotonic() - self._session_started))
            active_bypass = 0
            if self._bypass_started is not None:
                active_bypass = max(0, int(time.monotonic() - self._bypass_started))
            return {
                "app_launches": int(self._data["app_launches"]),
                "bypass_sessions": int(self._data["bypass_sessions"]),
                "bypass_seconds": int(self._data["bypass_seconds"]) + active_bypass,
                "launcher_seconds": int(self._data["launcher_seconds"])
                + session_seconds,
                "session_seconds": session_seconds,
                "active_bypass_seconds": active_bypass,
                "first_seen": self._data["first_seen"],
                "last_seen": self._data["last_seen"],
                "local_only": True,
            }

    def _save(self) -> None:
        if not self._path.parent.is_dir():
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                log.debug("Could not create usage data directory", exc_info=True)
                return
        payload = json.dumps(self._data, ensure_ascii=False, indent=2) + "\n"
        temp_path = ""
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=".usage-", suffix=".tmp", dir=str(self._path.parent)
            )
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
            temp_path = ""
        except OSError:
            log.debug("Could not save usage statistics", exc_info=True)
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
