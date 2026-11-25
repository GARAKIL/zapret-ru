"""Read-only environment and dependency diagnostics."""

from __future__ import annotations

import csv
import io
import locale
import os
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from core.paths import AppPaths, is_frozen
from core.winutils import CREATE_NO_WINDOW, is_admin

REQUIRED_FILES = (
    "winws.exe",
    "WinDivert.dll",
    "WinDivert64.sys",
    "cygwin1.dll",
)

OPTIONAL_FAKES = (
    "quic_initial_www_google_com.bin",
    "tls_clienthello_www_google_com.bin",
    "ACTIVE_DISCORD_UDP.bin",
    "ACTIVE_GAME_UDP.bin",
)


def _file_info(base: Path, name: str) -> dict[str, Any]:
    path = base / name
    try:
        stat = path.stat()
        return {
            "name": name,
            "present": path.is_file() and stat.st_size > 0,
            "size": stat.st_size if path.is_file() else 0,
            "path": str(path),
        }
    except OSError:
        return {"name": name, "present": False, "size": 0, "path": str(path)}


def count_list_entries(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith(("#", ";", "/")):
                    count += 1
    except OSError:
        return 0
    return count


def _list_info(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        return {
            "path": str(path),
            "present": path.is_file(),
            "size": stat.st_size if path.is_file() else 0,
            "modified": stat.st_mtime if path.is_file() else None,
            "entries": count_list_entries(path),
        }
    except OSError:
        return {
            "path": str(path),
            "present": False,
            "size": 0,
            "modified": None,
            "entries": 0,
        }


def find_winws_processes(exclude_pids: Iterable[int] = ()) -> list[dict[str, Any]]:
    """Return winws.exe processes not owned by this launcher.

    tasklist is a built-in Windows tool. Failure to inspect the process list is
    non-fatal; the UI simply shows no foreign process.
    """
    excluded = {int(pid) for pid in exclude_pids}
    try:
        encoding = locale.getpreferredencoding(False) or "utf-8"
        result = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq winws.exe", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=6,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        reader = csv.reader(io.StringIO(result.stdout))
        processes: list[dict[str, Any]] = []
        for row in reader:
            if len(row) < 2:
                continue
            image = row[0].strip().strip('"')
            if image.lower() != "winws.exe":
                continue
            try:
                pid = int(row[1])
            except ValueError:
                continue
            if pid not in excluded:
                processes.append({"pid": pid, "name": image})
        return processes
    except (OSError, subprocess.SubprocessError):
        return []


def scan_environment(
    paths: AppPaths, exclude_pids: Iterable[int] = ()
) -> dict[str, Any]:
    required = [_file_info(paths.bin_dir, name) for name in REQUIRED_FILES]
    optional = [_file_info(paths.bin_dir, name) for name in OPTIONAL_FAKES]
    lists = {
        "general": _list_info(paths.general_list),
        "exclude": _list_info(paths.exclude_list),
    }
    missing_required = [item["name"] for item in required if not item["present"]]
    missing_optional = [item["name"] for item in optional if not item["present"]]
    admin = is_admin()
    foreign = find_winws_processes(exclude_pids)
    ready = (
        admin
        and not missing_required
        and lists["general"]["present"]
        and lists["exclude"]["present"]
    )
    if ready and foreign:
        ready = False

    return {
        "admin": admin,
        "frozen": is_frozen(),
        "arch": os.environ.get("PROCESSOR_ARCHITECTURE", ""),
        "bin_dir": str(paths.bin_dir),
        "data_dir": str(paths.data_dir),
        "lists_dir": str(paths.lists_dir),
        "required": required,
        "optional": optional,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "foreign_winws": foreign,
        "lists": lists,
        "ready": ready,
        "checked_at": time.time(),
    }
