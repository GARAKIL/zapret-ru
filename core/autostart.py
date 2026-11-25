"""Windows Task Scheduler autostart integration (schtasks, no shell)."""

from __future__ import annotations

import locale
import subprocess
import sys
from pathlib import Path

from core.paths import is_frozen
from core.winutils import CREATE_NO_WINDOW

TASK_NAME = "Zapret RU Launcher"
SCHTASKS = "schtasks.exe"


class AutostartError(Exception):
    """Raised when Task Scheduler rejects an operation."""


def _run(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    encoding = locale.getpreferredencoding(False) or "utf-8"
    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AutostartError(f"Не удалось вызвать планировщик задач: {exc}") from exc


def _startup_args() -> list[str]:
    if is_frozen():
        exe = Path(sys.argv[0]).resolve()
        return [str(exe), "--autostart"]

    python = Path(sys.executable).resolve()
    pythonw = python.with_name("pythonw.exe")
    runner = pythonw if pythonw.is_file() else python
    script = Path(sys.argv[0]).resolve()
    return [str(runner), str(script), "--autostart"]


def task_command_line() -> str:
    """Human-readable command stored in the scheduled task."""
    return subprocess.list2cmdline(_startup_args())


def is_enabled() -> bool:
    result = _run([SCHTASKS, "/Query", "/TN", TASK_NAME])
    return result.returncode == 0


def set_enabled(enabled: bool) -> bool:
    if enabled:
        command = task_command_line()
        result = _run(
            [
                SCHTASKS,
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                command,
                "/SC",
                "ONLOGON",
                "/RL",
                "HIGHEST",
                "/F",
            ]
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise AutostartError(
                details or "Планировщик задач отклонил создание задачи"
            )
        if not is_enabled():
            raise AutostartError("Задача создана, но не найдена при проверке")
        return True

    if not is_enabled():
        return False
    result = _run([SCHTASKS, "/Delete", "/TN", TASK_NAME, "/F"])
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise AutostartError(details or "Не удалось удалить задачу автозапуска")
    return False
