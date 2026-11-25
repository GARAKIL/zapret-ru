"""Persistent, validated application settings."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

VALID_MODES = ("list", "global")
VALID_TABS = ("home", "lists", "logs", "settings")

DEFAULTS: dict[str, Any] = {
    "preset_id": "general",
    "mode": "list",
    "game_filter": False,
    "minimize_to_tray": True,
    "autostart": False,
    "last_tab": "home",
}


class SettingsError(Exception):
    """Raised when settings cannot be read or validated."""


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._values = dict(DEFAULTS)
        self.load_warning: str | None = None

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self._path.exists():
                self._values = dict(DEFAULTS)
                return self.snapshot()

            try:
                raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
                if not isinstance(raw, dict):
                    raise ValueError("settings.json должен содержать JSON-объект")
                values = dict(DEFAULTS)
                values.update(self._validate(raw, partial=True))
                self._values = values
                self.load_warning = None
            except (OSError, ValueError, SettingsError) as exc:
                self._quarantine_broken_file()
                self._values = dict(DEFAULTS)
                self.load_warning = f"Настройки сброшены: {exc}"
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict):
            raise SettingsError("Ожидается объект настроек")
        unknown = set(patch) - set(DEFAULTS)
        if unknown:
            raise SettingsError(f"Неизвестные настройки: {', '.join(sorted(unknown))}")
        with self._lock:
            values = dict(self._values)
            values.update(self._validate(patch, partial=True))
            self._values = values
            self._write(values)
            return dict(values)

    @staticmethod
    def _validate(raw: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in raw.items():
            if key not in DEFAULTS:
                continue
            if key == "preset_id":
                if not isinstance(value, str) or not value.strip() or len(value) > 80:
                    raise SettingsError("Некорректный идентификатор пресета")
                result[key] = value.strip()
            elif key == "mode":
                if value not in VALID_MODES:
                    raise SettingsError("Режим должен быть list или global")
                result[key] = value
            elif key in ("game_filter", "minimize_to_tray", "autostart"):
                if not isinstance(value, bool):
                    raise SettingsError(f"{key} должен быть логическим значением")
                result[key] = value
            elif key == "last_tab":
                if value not in VALID_TABS:
                    raise SettingsError("Неизвестная вкладка")
                result[key] = value
        if not partial:
            merged = dict(DEFAULTS)
            merged.update(result)
            return merged
        return result

    def _write(self, values: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(values, ensure_ascii=False, indent=2) + "\n"
        fd = -1
        temp_path = ""
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=".settings-", suffix=".tmp", dir=str(self._path.parent)
            )
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                fd = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
        finally:
            if fd != -1:
                os.close(fd)
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _quarantine_broken_file(self) -> None:
        try:
            if self._path.exists():
                suffix = time.strftime("%Y%m%d-%H%M%S")
                self._path.replace(
                    self._path.with_name(f"settings.corrupt-{suffix}.json")
                )
        except OSError:
            pass
