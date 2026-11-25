"""Safe lifecycle management for the winws.exe engine process."""

from __future__ import annotations

import atexit
import logging
import re
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.winutils import CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_MAX_LOG_ENTRIES = 2500
_MAX_LINE_CHARS = 8000
log = logging.getLogger(__name__)


class WinwsManager:
    """Owns exactly one winws.exe process started by this application.

    The manager never searches for and never kills winws processes by image
    name. taskkill is only used with the PID of the child it launched.
    """

    def __init__(
        self,
        executable: Path,
        working_dir: Path,
        on_state_change: Callable[[], None] | None = None,
    ) -> None:
        self._executable = executable
        self._working_dir = working_dir
        self._on_state_change = on_state_change
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._reader_thread: threading.Thread | None = None
        self._waiter_thread: threading.Thread | None = None
        self._expected_stop = False
        self._shutting_down = False
        self._started_at: float | None = None
        self._last_exit_code: int | None = None
        self._last_error: str | None = None
        self._active_config: dict[str, Any] = {}
        self._command: list[str] = []
        self._logs: deque[dict[str, Any]] = deque(maxlen=_MAX_LOG_ENTRIES)
        self._next_seq = 1
        atexit.register(self.shutdown)

    def set_state_callback(self, callback: Callable[[], None] | None) -> None:
        with self._lock:
            self._on_state_change = callback

    # ------------------------------------------------------------------ logs
    def _append_log_locked(self, text: str, kind: str = "output") -> None:
        text = _ANSI_RE.sub("", str(text)).replace("\x00", "").strip("\r\n")
        if not text:
            return
        if len(text) > _MAX_LINE_CHARS:
            text = text[:_MAX_LINE_CHARS] + " …"
        entry = {
            "seq": self._next_seq,
            "time": time.strftime("%H:%M:%S"),
            "ts": time.time(),
            "text": text,
            "kind": kind,
        }
        self._next_seq += 1
        self._logs.append(entry)

    def append_system_log(self, text: str, kind: str = "system") -> None:
        with self._lock:
            self._append_log_locked(text, kind)

    def logs_after(self, after_seq: int = 0) -> dict[str, Any]:
        try:
            after = max(0, int(after_seq))
        except (TypeError, ValueError):
            after = 0
        with self._lock:
            entries = [entry for entry in self._logs if entry["seq"] > after]
            return {
                "ok": True,
                "entries": entries,
                "next_seq": self._next_seq - 1,
            }

    def clear_logs(self) -> dict[str, Any]:
        with self._lock:
            self._logs.clear()
            self._next_seq = 1
        self._notify_state_changed()
        return {"ok": True, "next_seq": 0}

    # ---------------------------------------------------------------- process
    @property
    def process_pid(self) -> int | None:
        with self._lock:
            if self._process is None:
                return None
            return self._process.pid

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_locked()

    def _is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(
        self, command: list[str], active_config: dict[str, Any]
    ) -> dict[str, Any]:
        if not isinstance(command, list) or not command:
            return {
                "ok": False,
                "started": False,
                "error": "Пустая команда запуска",
                "status": self.status(),
            }
        for arg in command:
            if not isinstance(arg, str) or "\x00" in arg or "\r" in arg or "\n" in arg:
                return {
                    "ok": False,
                    "started": False,
                    "error": "Некорректный аргумент winws",
                    "status": self.status(),
                }
        if not self._executable.is_file():
            return {
                "ok": False,
                "started": False,
                "error": f"winws.exe не найден: {self._executable}",
                "status": self.status(),
            }
        if not self._working_dir.is_dir():
            return {
                "ok": False,
                "started": False,
                "error": f"Рабочая папка не найдена: {self._working_dir}",
                "status": self.status(),
            }

        with self._lifecycle_lock:
            with self._lock:
                if self._is_running_locked():
                    return {
                        "ok": False,
                        "started": False,
                        "error": "winws.exe уже запущен",
                        "status": self.status(),
                    }
                self._expected_stop = False
                self._last_exit_code = None
                self._last_error = None
                self._active_config = dict(active_config)
                self._command = list(command)
                self._append_log_locked("Запуск winws.exe", "system")
                self._append_log_locked(
                    subprocess.list2cmdline([str(self._executable), *command]),
                    "command",
                )

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                try:
                    process = subprocess.Popen(
                        [str(self._executable), *command],
                        cwd=str(self._working_dir),
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        bufsize=0,
                        close_fds=True,
                        startupinfo=startupinfo,
                        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
                    )
                except OSError as exc:
                    self._last_error = f"Не удалось запустить winws.exe: {exc}"
                    self._append_log_locked(self._last_error, "error")
                    self._active_config = {}
                    return {
                        "ok": False,
                        "started": False,
                        "error": self._last_error,
                        "status": self.status(),
                    }

                self._process = process
                self._started_at = time.time()
                self._reader_thread = threading.Thread(
                    target=self._read_output,
                    args=(process,),
                    name="winws-output",
                    daemon=True,
                )
                self._waiter_thread = threading.Thread(
                    target=self._wait_for_exit,
                    args=(process,),
                    name="winws-waiter",
                    daemon=True,
                )
                self._reader_thread.start()
                self._waiter_thread.start()
                pid = process.pid
                self._append_log_locked(f"winws.exe запущен, PID {pid}", "system")

            # Give the engine time to initialise WinDivert and validate its
            # command line. Many driver/parameter errors are immediate.
            time.sleep(0.8)
            with self._lock:
                started = self._is_running_locked()
                error = (
                    None
                    if started
                    else (
                        self._last_error or "winws.exe завершился сразу после запуска"
                    )
                )
            self._notify_state_changed()
            return {
                "ok": started,
                "started": started,
                "error": error,
                "status": self.status(),
            }

    def _read_output(self, process: subprocess.Popen[bytes]) -> None:
        stream = process.stdout
        if stream is None:
            return
        try:
            while True:
                line = stream.readline()
                if not line:
                    break
                text = self._decode_line(line)
                for part in text.splitlines() or [text]:
                    with self._lock:
                        self._append_log_locked(part, "output")
        except (OSError, ValueError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    @staticmethod
    def _decode_line(raw: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp866", "cp1251"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _wait_for_exit(self, process: subprocess.Popen[bytes]) -> None:
        return_code = process.wait()
        with self._lock:
            if self._process is not process:
                return
            expected = self._expected_stop or self._shutting_down
            self._process = None
            self._last_exit_code = return_code
            if expected:
                self._append_log_locked(
                    f"winws.exe остановлен (код {return_code})", "system"
                )
                if not self._shutting_down:
                    self._last_error = None
            else:
                self._last_error = (
                    f"winws.exe завершился неожиданно (код {return_code}). "
                    "Проверьте журнал и параметры стратегии."
                )
                self._append_log_locked(self._last_error, "error")
            self._started_at = None
            self._active_config = {}
        self._notify_state_changed()

    def _notify_state_changed(self) -> None:
        with self._lock:
            callback = self._on_state_change
        if callback:
            try:
                callback()
            except Exception:
                log.exception("Winws state callback failed")

    def stop(self, reason: str | None = None) -> dict[str, Any]:
        with self._lifecycle_lock:
            with self._lock:
                process = self._process
                if process is None or process.poll() is not None:
                    return {
                        "ok": True,
                        "started": False,
                        "error": None,
                        "status": self.status(),
                    }
                pid = process.pid
                self._expected_stop = True
                self._append_log_locked(
                    reason or "Остановка обхода по команде пользователя", "system"
                )

            try:
                process.terminate()
            except OSError:
                pass

            try:
                process.wait(timeout=1.2)
            except subprocess.TimeoutExpired:
                with self._lock:
                    self._append_log_locked(
                        f"Штатное завершение не удалось, используется taskkill /F /T /PID {pid}",
                        "system",
                    )
                try:
                    subprocess.run(
                        ["taskkill.exe", "/F", "/T", "/PID", str(pid)],
                        check=False,
                        capture_output=True,
                        timeout=6,
                        creationflags=CREATE_NO_WINDOW,
                    )
                except (OSError, subprocess.SubprocessError):
                    try:
                        process.kill()
                    except OSError:
                        pass
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    with self._lock:
                        self._last_error = (
                            "Не удалось гарантированно завершить winws.exe; "
                            "завершите процесс вручную."
                        )
                        self._append_log_locked(self._last_error, "error")

            waiter = self._waiter_thread
            if waiter is not None:
                waiter.join(timeout=2.0)
            reader = self._reader_thread
            if reader is not None:
                reader.join(timeout=1.0)
            with self._lock:
                if self._process is process and process.poll() is not None:
                    # The waiter normally handles this. This fallback makes
                    # stop() deterministic even under thread scheduling races.
                    self._process = None
                    self._last_exit_code = process.poll()
                    self._started_at = None
                    self._active_config = {}
                    if not self._shutting_down:
                        self._last_error = None
            self._notify_state_changed()
            return {
                "ok": True,
                "started": False,
                "error": None,
                "status": self.status(),
            }

    def shutdown(self) -> None:
        with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True
        try:
            self.stop("Завершение работы приложения")
        except Exception:
            log.exception("Winws shutdown failed")

    # ----------------------------------------------------------------- status
    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self._is_running_locked()
            pid = self._process.pid if running and self._process is not None else None
            uptime = (
                int(time.time() - self._started_at)
                if running and self._started_at
                else 0
            )
            return {
                "running": running,
                "pid": pid,
                "uptime_seconds": max(0, uptime),
                "started_at": self._started_at if running else None,
                "last_exit_code": self._last_exit_code,
                "last_error": self._last_error,
                "active_config": dict(self._active_config) if running else {},
                "command": list(self._command),
                "command_line": subprocess.list2cmdline(
                    [str(self._executable), *self._command]
                ),
                "executable": str(self._executable),
                "log_seq": self._next_seq - 1,
            }
