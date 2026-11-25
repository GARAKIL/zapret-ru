"""Application paths and first-run data provisioning."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Zapret RU"
APP_VERSION = "1.1.0"
APP_ID = "ZapretRU"
APP_MUTEX = r"Global\ZapretRU.Launcher.v1"

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_BUNDLED_LISTS = ("list-general.txt", "list-exclude.txt")


def is_frozen() -> bool:
    """Return True for a Nuitka-compiled build."""
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def _project_root() -> Path:
    return _PACKAGE_ROOT


def _executable_dir() -> Path:
    """Folder containing the launcher executable (or main.py in source mode).

    In Nuitka onefile builds sys.argv[0] points at the original executable,
    while __file__ points inside the temporary extraction directory. We need
    the real executable folder for the external WinDivert/zapret binaries.
    """
    argv0 = Path(sys.argv[0]).expanduser()
    try:
        return argv0.resolve().parent
    except OSError:
        return Path.cwd()


def _local_appdata() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


@dataclass(frozen=True)
class AppPaths:
    app_dir: Path
    resource_dir: Path
    data_dir: Path
    bin_dir: Path
    lists_dir: Path
    presets_file: Path
    settings_file: Path
    ui_dir: Path
    ui_index: Path
    assets_dir: Path
    general_list: Path
    exclude_list: Path


def get_paths() -> AppPaths:
    """Compute all paths. In onefile builds mutable data lives in AppData."""
    frozen = is_frozen()
    resource_dir = _project_root()
    app_dir = _executable_dir()
    data_dir = _local_appdata() / APP_ID if frozen else resource_dir
    lists_dir = data_dir / "lists"
    ui_dir = resource_dir / "ui"
    return AppPaths(
        app_dir=app_dir,
        resource_dir=resource_dir,
        data_dir=data_dir,
        bin_dir=app_dir / "bin",
        lists_dir=lists_dir,
        presets_file=data_dir / "presets.json",
        settings_file=data_dir / "settings.json",
        ui_dir=ui_dir,
        ui_index=ui_dir / "index.html",
        assets_dir=resource_dir / "assets",
        general_list=lists_dir / "list-general.txt",
        exclude_list=lists_dir / "list-exclude.txt",
    )


def ensure_data_files(paths: AppPaths) -> list[str]:
    """Create writable data folders and seed bundled files when necessary.

    Existing user files are never overwritten. Returns a list of human-readable
    notes suitable for the application log.
    """
    notes: list[str] = []
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.lists_dir.mkdir(parents=True, exist_ok=True)

    bundled_lists_dir = paths.resource_dir / "lists"
    for name in _BUNDLED_LISTS:
        target = paths.lists_dir / name
        if target.exists():
            continue
        source = bundled_lists_dir / name
        if source.is_file():
            shutil.copyfile(source, target)
            notes.append(f"Создан список по умолчанию: {target}")

    if not paths.presets_file.exists():
        source = paths.resource_dir / "presets.json"
        if source.is_file():
            shutil.copyfile(source, paths.presets_file)
            notes.append(f"Создан файл пресетов: {paths.presets_file}")

    return notes
