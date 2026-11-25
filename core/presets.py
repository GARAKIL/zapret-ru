"""Data-driven winws argument generation.

The UI never constructs a winws command by hand. Every profile comes from
presets.json, which keeps strategies easy to audit and update. Mode filters,
protocol filters, port sets and the executable path are owned by the generator
so that "list" and "global" semantics cannot accidentally leak between modes.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
_BLOCK_NAMES = ("tcp", "quic", "discord", "game_tcp", "game_udp")
_FILE_TOKEN = re.compile(r"@BIN/([A-Za-z0-9._-]+)")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$")
_BANNED_ARG_PREFIXES = (
    "--new",
    "--skip",
    "--filter-",
    "--wf-",
    "--hostlist",
    "--ipset",
)


class PresetError(Exception):
    """Raised for invalid preset data or an invalid generation request."""


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    label: str
    description: str
    badge: str | None
    caution: str | None
    blocks: dict[str, tuple[str, ...]]

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "badge": self.badge,
            "caution": self.caution,
        }


@dataclass(frozen=True)
class Defaults:
    tcp_ports: str
    udp_ports: str
    discord_udp_ports: str
    game_tcp_ports: str
    game_udp_ports: str


@dataclass
class BuildResult:
    command: list[str]
    preset: Preset
    mode: str
    game_filter: bool
    wf_tcp: str
    wf_udp: str
    skipped_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def command_line(self) -> str:
        return subprocess.list2cmdline(self.command)

    def active_config(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset.id,
            "preset_name": self.preset.name,
            "preset_label": self.preset.label,
            "mode": self.mode,
            "game_filter": self.game_filter,
            "wf_tcp": self.wf_tcp,
            "wf_udp": self.wf_udp,
        }


def _validate_text(value: Any, field_name: str, *, max_len: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PresetError(f"{field_name} должен быть непустой строкой")
    value = value.strip()
    if len(value) > max_len or any(ch in value for ch in "\r\n\x00"):
        raise PresetError(f"{field_name} содержит недопустимые символы")
    return value


def _validate_args(raw: Any, block_name: str, preset_id: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise PresetError(f"{preset_id}.{block_name}: ожидается массив аргументов")
    result: list[str] = []
    for index, arg in enumerate(raw):
        if not isinstance(arg, str) or not arg.strip():
            raise PresetError(f"{preset_id}.{block_name}[{index}]: пустой аргумент")
        arg = arg.strip()
        if len(arg) > 1200 or any(ch in arg for ch in "\r\n\x00"):
            raise PresetError(
                f"{preset_id}.{block_name}[{index}]: недопустимый аргумент"
            )
        if not arg.startswith("--"):
            raise PresetError(
                f"{preset_id}.{block_name}[{index}]: аргумент должен начинаться с --"
            )
        if arg.startswith(_BANNED_ARG_PREFIXES):
            raise PresetError(
                f"{preset_id}.{block_name}[{index}]: фильтры и --new управляются приложением"
            )
        if "@BIN/" in arg:
            without_tokens = _FILE_TOKEN.sub("", arg)
            if "@BIN/" in without_tokens or any(part in arg for part in ("..", "\t")):
                raise PresetError(
                    f"{preset_id}.{block_name}[{index}]: некорректный @BIN"
                )
        result.append(arg)
    return tuple(result)


def parse_port_spec(spec: str, field_name: str = "порты") -> list[tuple[int, int]]:
    """Parse and validate a winws-style port list into inclusive ranges."""
    if not isinstance(spec, str) or not spec.strip():
        raise PresetError(f"{field_name}: пустой список портов")
    ranges: list[tuple[int, int]] = []
    for token in spec.split(","):
        token = token.strip()
        match = re.fullmatch(r"(\d{1,5})(?:-(\d{1,5}))?", token)
        if not match:
            raise PresetError(f"{field_name}: некорректный порт «{token}»")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if not (1 <= start <= end <= 65535):
            raise PresetError(f"{field_name}: порт вне диапазона 1-65535")
        ranges.append((start, end))
    return ranges


def normalize_port_specs(specs: Iterable[str], field_name: str = "порты") -> str:
    ranges: list[tuple[int, int]] = []
    for spec in specs:
        ranges.extend(parse_port_spec(spec, field_name))
    if not ranges:
        raise PresetError(f"{field_name}: пустой список портов")
    ranges.sort()
    merged: list[list[int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in merged)


class PresetStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._presets: dict[str, Preset] = {}
        self._defaults: Defaults | None = None
        self._updated = ""
        self._loaded_at = 0.0
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        with self._lock:
            if not self._path.is_file():
                raise PresetError(f"Файл пресетов не найден: {self._path}")
            try:
                size = self._path.stat().st_size
                if size > 2_000_000:
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
            defaults_raw = raw.get("defaults")
            if not isinstance(defaults_raw, dict):
                raise PresetError("В presets.json отсутствует секция defaults")
            try:
                defaults = Defaults(
                    tcp_ports=normalize_port_specs(
                        [str(defaults_raw["tcp_ports"])], "defaults.tcp_ports"
                    ),
                    udp_ports=normalize_port_specs(
                        [str(defaults_raw["udp_ports"])], "defaults.udp_ports"
                    ),
                    discord_udp_ports=normalize_port_specs(
                        [str(defaults_raw["discord_udp_ports"])],
                        "defaults.discord_udp_ports",
                    ),
                    game_tcp_ports=normalize_port_specs(
                        [str(defaults_raw["game_tcp_ports"])], "defaults.game_tcp_ports"
                    ),
                    game_udp_ports=normalize_port_specs(
                        [str(defaults_raw["game_udp_ports"])], "defaults.game_udp_ports"
                    ),
                )
            except (KeyError, TypeError) as exc:
                raise PresetError(
                    "Некорректная секция defaults в presets.json"
                ) from exc

            presets_raw = raw.get("presets")
            if not isinstance(presets_raw, list) or not presets_raw:
                raise PresetError("В presets.json нет ни одного пресета")
            presets: dict[str, Preset] = {}
            for item in presets_raw:
                preset = self._parse_preset(item)
                if preset.id in presets:
                    raise PresetError(f"Дублирующийся пресет: {preset.id}")
                presets[preset.id] = preset
            if not presets:
                raise PresetError("В presets.json нет пресетов")

            self._presets = presets
            self._defaults = defaults
            self._updated = str(raw.get("updated", "")).strip()
            self._loaded_at = time.time()

    def _parse_preset(self, raw: Any) -> Preset:
        if not isinstance(raw, dict):
            raise PresetError("Пресет должен быть объектом")
        preset_id = _validate_text(raw.get("id"), "presets[].id", max_len=60)
        if not _ID_RE.fullmatch(preset_id):
            raise PresetError(f"Некорректный id пресета: {preset_id}")
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
        blocks = {
            block: _validate_args(raw.get(block), block, preset_id)
            for block in _BLOCK_NAMES
        }
        if not blocks["tcp"]:
            raise PresetError(f"{preset_id}: TCP-профиль не может быть пустым")
        return Preset(
            id=preset_id,
            name=name,
            label=label,
            description=description,
            badge=badge,
            caution=caution,
            blocks=blocks,
        )

    def public_presets(self) -> list[dict[str, Any]]:
        with self._lock:
            return [preset.public() for preset in self._presets.values()]

    @property
    def updated(self) -> str:
        return self._updated

    @property
    def loaded_at(self) -> float:
        return self._loaded_at

    def get(self, preset_id: str) -> Preset:
        with self._lock:
            try:
                return self._presets[preset_id]
            except KeyError as exc:
                raise PresetError(f"Пресет «{preset_id}» не найден") from exc

    def build(
        self,
        preset_id: str,
        mode: str,
        game_filter: bool,
        general_list: Path,
        exclude_list: Path,
        bin_dir: Path,
    ) -> BuildResult:
        if mode not in ("list", "global"):
            raise PresetError("Неизвестный режим обхода")
        if not isinstance(game_filter, bool):
            raise PresetError("game_filter должен быть bool")
        if mode == "list" and not general_list.is_file():
            raise PresetError(f"Не найден список обхода: {general_list}")
        if not exclude_list.is_file():
            raise PresetError(f"Не найден список исключений: {exclude_list}")
        if not bin_dir.is_dir():
            raise PresetError(f"Не найдена папка bin: {bin_dir}")

        general_list = general_list.resolve()
        exclude_list = exclude_list.resolve()
        bin_dir = bin_dir.resolve()
        preset = self.get(preset_id)
        with self._lock:
            defaults = self._defaults
            if defaults is None:
                raise PresetError("Пресеты не загружены")

        wf_tcp = normalize_port_specs(
            [defaults.tcp_ports, defaults.game_tcp_ports]
            if game_filter
            else [defaults.tcp_ports],
            "wf-tcp",
        )
        udp_specs = [defaults.udp_ports]
        if game_filter:
            udp_specs.append(defaults.game_udp_ports)
        wf_udp = normalize_port_specs(udp_specs, "wf-udp")

        scope = self._scope_args(mode, general_list, exclude_list)
        skipped: set[str] = set()

        profiles: list[list[str]] = []

        if preset.blocks["quic"]:
            profile = ["--filter-udp=443", "--filter-l7=quic"]
            profile.extend(scope)
            profile.extend(self._expand_args(preset.blocks["quic"], bin_dir, skipped))
            profiles.append(profile)

        if preset.blocks["discord"]:
            profile = [
                f"--filter-udp={defaults.discord_udp_ports}",
                "--filter-l7=discord,stun",
            ]
            profile.extend(
                self._expand_args(preset.blocks["discord"], bin_dir, skipped)
            )
            profiles.append(profile)

        tcp_profile = [f"--filter-tcp={defaults.tcp_ports}"]
        tcp_profile.extend(scope)
        tcp_profile.extend(self._expand_args(preset.blocks["tcp"], bin_dir, skipped))
        profiles.append(tcp_profile)

        if game_filter and preset.blocks["game_tcp"]:
            game_tcp = [f"--filter-tcp={defaults.game_tcp_ports}"]
            game_tcp.extend(
                self._expand_args(preset.blocks["game_tcp"], bin_dir, skipped)
            )
            profiles.append(game_tcp)

        if game_filter and preset.blocks["game_udp"]:
            game_udp = [f"--filter-udp={defaults.game_udp_ports}"]
            game_udp.extend(
                self._expand_args(preset.blocks["game_udp"], bin_dir, skipped)
            )
            profiles.append(game_udp)

        command: list[str] = [f"--wf-tcp={wf_tcp}", f"--wf-udp={wf_udp}"]
        for index, profile in enumerate(profiles):
            if index:
                command.append("--new")
            command.extend(profile)

        warnings: list[str] = []
        skipped_sorted = sorted(skipped)
        if skipped_sorted:
            warnings.append(
                "Не найдены .bin-файлы: "
                + ", ".join(skipped_sorted)
                + ". Соответствующие параметры пропущены; zapret использует встроенные "
                "фейковые пакеты."
            )
        if preset.caution:
            warnings.append(preset.caution)

        return BuildResult(
            command=command,
            preset=preset,
            mode=mode,
            game_filter=game_filter,
            wf_tcp=wf_tcp,
            wf_udp=wf_udp,
            skipped_files=skipped_sorted,
            warnings=warnings,
        )

    @staticmethod
    def _scope_args(mode: str, general_list: Path, exclude_list: Path) -> list[str]:
        args = [f"--hostlist-exclude={exclude_list}"]
        if mode == "list":
            args.insert(0, f"--hostlist={general_list}")
        return args

    @staticmethod
    def _expand_args(
        args: tuple[str, ...], bin_dir: Path, skipped: set[str]
    ) -> list[str]:
        result: list[str] = []
        for arg in args:
            names = _FILE_TOKEN.findall(arg)
            missing = [name for name in names if not (bin_dir / name).is_file()]
            if missing:
                skipped.update(missing)
                continue
            if names:
                arg = _FILE_TOKEN.sub(
                    lambda match: "@" + str(bin_dir / match.group(1)), arg
                )
            else:
                arg = arg.replace("@BIN", str(bin_dir))
            result.append(arg)
        return result
