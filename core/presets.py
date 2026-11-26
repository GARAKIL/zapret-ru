"""Data-driven engine profiles.

A profile only describes how the built-in engine should split traffic. It never
contains executable paths, shell fragments or zapret arguments. This keeps the
UI and the engine policy small and auditable.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$")
_SPLIT_VALUES = ("sni", "sni-start", "sni-end")


class PresetError(Exception):
    """Raised for invalid profile data."""


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    label: str
    description: str
    badge: str | None
    caution: str | None
    split: int | str
    block_quic: bool

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "badge": self.badge,
            "caution": self.caution,
            "split": self.split,
            "block_quic": self.block_quic,
        }


def _validate_text(value: Any, field_name: str, *, max_len: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PresetError(f"{field_name} должен быть непустой строкой")
    value = value.strip()
    if len(value) > max_len or any(ch in value for ch in "\r\n\x00"):
        raise PresetError(f"{field_name} содержит недопустимые символы")
    return value


def _validate_split(value: Any, preset_id: str) -> int | str:
    if isinstance(value, bool):
        raise PresetError(f"{preset_id}.split должен быть числом или «sni»")
    if isinstance(value, int):
        if not 1 <= value <= 512:
            raise PresetError(f"{preset_id}.split должен быть в диапазоне 1–512")
        return value
    if isinstance(value, str) and value.strip().lower() in _SPLIT_VALUES:
        return value.strip().lower()
    raise PresetError(
        f"{preset_id}.split должен быть числом, «sni», «sni-start» или «sni-end»"
    )


class PresetStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._presets: dict[str, Preset] = {}
        self._updated = ""
        self._loaded_at = 0.0
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def updated(self) -> str:
        return self._updated

    @property
    def loaded_at(self) -> float:
        return self._loaded_at

    def load(self) -> None:
        with self._lock:
            if not self._path.is_file():
                raise PresetError(f"Файл профилей не найден: {self._path}")
            try:
                size = self._path.stat().st_size
                if size > 1_000_000:
                    raise PresetError("Файл presets.json слишком большой")
                raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
            except PresetError:
                raise
            except (OSError, ValueError) as exc:
                raise PresetError(f"Не удалось прочитать presets.json: {exc}") from exc
            if not isinstance(raw, dict):
                raise PresetError("Корень presets.json должен быть объектом")
            if raw.get("schema_version") != SCHEMA_VERSION:
                raise PresetError("Неподдерживаемая версия presets.json")
            presets_raw = raw.get("presets")
            if not isinstance(presets_raw, list) or not presets_raw:
                raise PresetError("В presets.json нет ни одного профиля")
            presets: dict[str, Preset] = {}
            for item in presets_raw:
                preset = self._parse_preset(item)
                if preset.id in presets:
                    raise PresetError(f"Дублирующийся профиль: {preset.id}")
                presets[preset.id] = preset
            self._presets = presets
            self._updated = str(raw.get("updated", "")).strip()
            self._loaded_at = time.time()

    def _parse_preset(self, raw: Any) -> Preset:
        if not isinstance(raw, dict):
            raise PresetError("Профиль должен быть объектом")
        preset_id = _validate_text(raw.get("id"), "presets[].id", max_len=60)
        if not _ID_RE.fullmatch(preset_id):
            raise PresetError(f"Некорректный id профиля: {preset_id}")
        name = _validate_text(raw.get("name"), f"{preset_id}.name", max_len=80)
        label = _validate_text(raw.get("label"), f"{preset_id}.label", max_len=120)
        description = _validate_text(
            raw.get("description"), f"{preset_id}.description", max_len=1200
        )
        badge = raw.get("badge")
        if badge is not None:
            badge = _validate_text(badge, f"{preset_id}.badge", max_len=40)
        caution = raw.get("caution")
        if caution is not None:
            caution = _validate_text(caution, f"{preset_id}.caution", max_len=500)
        block_quic = raw.get("block_quic", True)
        if not isinstance(block_quic, bool):
            raise PresetError(f"{preset_id}.block_quic должен быть bool")
        return Preset(
            id=preset_id,
            name=name,
            label=label,
            description=description,
            badge=badge,
            caution=caution,
            split=_validate_split(raw.get("split"), preset_id),
            block_quic=block_quic,
        )

    def public_presets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [preset.public() for preset in self._presets.values()]

    def get(self, preset_id: str) -> Preset:
        with self._lock:
            try:
                return self._presets[preset_id]
            except KeyError as exc:
                raise PresetError(f"Профиль «{preset_id}» не найден") from exc

    @property
    def default_id(self) -> str:
        with self._lock:
            return next(iter(self._presets))
