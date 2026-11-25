"""Application service layer shared by the web UI and the tray."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import autostart
from core.autostart import AutostartError
from core.checker import check_services
from core.environment import scan_environment
from core.manager import WinwsManager
from core.paths import APP_NAME, APP_VERSION, AppPaths, ensure_data_files
from core.presets import PresetError, PresetStore
from core.settings import SettingsError, SettingsStore
from core.usage import UsageStore

_LIST_FILES = {
    "general": ("list-general.txt", "Список обхода"),
    "exclude": ("list-exclude.txt", "Список исключений"),
}
_MAX_LIST_BYTES = 4 * 1024 * 1024
log = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Friendly, user-facing service error."""


class ApplicationCore:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.data_notes = ensure_data_files(paths)
        self.settings = SettingsStore(paths.settings_file)
        self.settings.load()
        self.preset_store: PresetStore | None = None
        self.presets_error: str | None = None
        self.presets_updated = ""
        try:
            self._load_presets()
        except PresetError as exc:
            self.presets_error = str(exc)
        self._state_callback: Callable[[], None] | None = None
        self.usage = UsageStore(paths.data_dir / "usage.json")
        self.usage.start_launcher_session()
        self.manager = WinwsManager(
            executable=paths.bin_dir / "winws.exe",
            working_dir=paths.bin_dir,
            on_state_change=self._manager_state_changed,
        )
        self._normalise_selected_preset()

    # ---------------------------------------------------------------- startup
    def _load_presets(self) -> None:
        store = PresetStore(self.paths.presets_file)
        self.preset_store = store
        self.presets_updated = store.updated
        self.presets_error = None

    def _normalise_selected_preset(self) -> None:
        if not self.preset_store:
            return
        available = {item["id"] for item in self.preset_store.public_presets()}
        current = self.settings.snapshot().get("preset_id")
        if current not in available and available:
            fallback = next(iter(available))
            try:
                self.settings.update({"preset_id": fallback})
            except SettingsError:
                pass

    def _manager_state_changed(self) -> None:
        if not self.manager.is_running():
            self.usage.end_bypass()
        callback = self._state_callback
        if callback:
            try:
                callback()
            except Exception:
                log.exception("Application state callback failed")

    def set_state_callback(self, callback: Callable[[], None] | None) -> None:
        self._state_callback = callback

    def bootstrap(self) -> dict[str, Any]:
        warnings: list[str] = list(self.data_notes)
        if self.settings.load_warning:
            warnings.append(self.settings.load_warning)
        presets = []
        if self.preset_store:
            presets = self.preset_store.public_presets()
        if self.presets_error:
            warnings.append(self.presets_error)

        autostart_enabled = False
        autostart_error: str | None = None
        try:
            autostart_enabled = autostart.is_enabled()
        except AutostartError as exc:
            autostart_error = str(exc)
            warnings.append(f"Не удалось проверить автозапуск: {exc}")
        self._apply_autostart_snapshot(autostart_enabled, autostart_error is None)

        environment = self.refresh_environment()
        return {
            "ok": True,
            "app": {
                "name": APP_NAME,
                "version": APP_VERSION,
                "task_name": autostart.TASK_NAME,
                "task_command": autostart.task_command_line(),
            },
            "settings": self.settings.snapshot(),
            "presets": presets,
            "presets_updated": self.presets_updated,
            "presets_error": self.presets_error,
            "environment": environment,
            "status": self.manager.status(),
            "usage": self.usage.snapshot(),
            "autostart": autostart_enabled,
            "autostart_error": autostart_error,
            "warnings": warnings,
            "paths": self._public_paths(),
        }

    def _apply_autostart_snapshot(self, enabled: bool, succeeded: bool) -> None:
        if not succeeded:
            return
        if self.settings.snapshot().get("autostart") != enabled:
            try:
                self.settings.update({"autostart": enabled})
            except SettingsError:
                pass

    def _public_paths(self) -> dict[str, str]:
        return {
            "bin": str(self.paths.bin_dir),
            "data": str(self.paths.data_dir),
            "lists": str(self.paths.lists_dir),
            "presets": str(self.paths.presets_file),
            "general_list": str(self.paths.general_list),
            "exclude_list": str(self.paths.exclude_list),
        }

    def refresh_environment(self) -> dict[str, Any]:
        environment = scan_environment(
            self.paths,
            exclude_pids=[self.manager.process_pid] if self.manager.process_pid else [],
        )
        environment["session"] = {
            "admin": environment.get("admin", False),
            "manager_running": self.manager.is_running(),
        }
        return environment

    def _require_preset_store(self) -> PresetStore:
        if self.preset_store is None:
            raise ApplicationError(self.presets_error or "Пресеты не загружены")
        return self.preset_store

    def get_presets(self) -> dict[str, Any]:
        store = self.preset_store
        return {
            "ok": True,
            "presets": store.public_presets() if store else [],
            "updated": self.presets_updated,
            "error": self.presets_error,
        }

    def reload_presets(self) -> dict[str, Any]:
        try:
            self._load_presets()
        except PresetError as exc:
            self.presets_error = str(exc)
            return {
                "ok": False,
                "error": str(exc),
                "presets": self.get_presets()["presets"],
            }
        self._normalise_selected_preset()
        return self.get_presets()

    # ------------------------------------------------------------------ engine
    def start_bypass(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        if not isinstance(preset_id, str) or not isinstance(mode, str):
            raise ApplicationError("Некорректные параметры запуска")
        if not isinstance(game_filter, bool):
            raise ApplicationError("game_filter должен быть логическим значением")
        if mode not in ("list", "global"):
            raise ApplicationError("Неизвестный режим обхода")
        if self.manager.is_running():
            raise ApplicationError("Обход уже запущен. Сначала остановите его.")

        store = self._require_preset_store()
        environment = self.refresh_environment()
        if not environment.get("admin"):
            raise ApplicationError(
                "winws.exe требует прав администратора. Перезапустите приложение от имени администратора."
            )
        if environment.get("missing_required"):
            missing = ", ".join(environment["missing_required"])
            raise ApplicationError(
                f"В папке bin не хватает обязательных файлов: {missing}. "
                "Скопируйте их из оригинального zapret для Windows."
            )
        foreign = environment.get("foreign_winws") or []
        if foreign:
            pids = ", ".join(str(item["pid"]) for item in foreign)
            raise ApplicationError(
                f"Обнаружен другой процесс winws.exe (PID: {pids}). "
                "Остановите его, чтобы избежать конфликта фильтров WinDivert."
            )

        try:
            build = store.build(
                preset_id=preset_id,
                mode=mode,
                game_filter=game_filter,
                general_list=self.paths.general_list,
                exclude_list=self.paths.exclude_list,
                bin_dir=self.paths.bin_dir,
            )
        except PresetError as exc:
            raise ApplicationError(str(exc)) from exc

        try:
            self.settings.update(
                {
                    "preset_id": preset_id,
                    "mode": mode,
                    "game_filter": game_filter,
                }
            )
        except SettingsError as exc:
            raise ApplicationError(str(exc)) from exc

        result = self.manager.start(build.command, build.active_config())
        if result["ok"] and self.manager.is_running():
            self.usage.start_bypass()
        status = result["status"]
        return {
            "ok": bool(result["ok"]),
            "error": result.get("error"),
            "started": bool(result.get("started")),
            "status": status,
            "usage": self.usage.snapshot(),
            "config": build.active_config(),
            "command_line": build.command_line,
            "warnings": build.warnings,
            "skipped_files": build.skipped_files,
            "environment": self.refresh_environment(),
        }

    def stop_bypass(self) -> dict[str, Any]:
        result = self.manager.stop("Остановка обхода из интерфейса")
        self.usage.end_bypass()
        return {
            "ok": bool(result["ok"]),
            "error": result.get("error"),
            "status": result["status"],
            "usage": self.usage.snapshot(),
            "environment": self.refresh_environment(),
        }

    def restart_bypass(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        if self.manager.is_running():
            self.manager.stop("Перезапуск для применения новой стратегии")
            self.usage.end_bypass()
        return self.start_bypass(preset_id, mode, game_filter)

    def get_status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "status": self.manager.status(),
            "settings": self.settings.snapshot(),
            "usage": self.usage.snapshot(),
        }

    def get_logs(self, after_seq: int = 0) -> dict[str, Any]:
        return self.manager.logs_after(after_seq)

    def clear_logs(self) -> dict[str, Any]:
        return self.manager.clear_logs()

    def check_connectivity(self) -> dict[str, Any]:
        return check_services()

    def command_preview(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        store = self._require_preset_store()
        try:
            build = store.build(
                preset_id=preset_id,
                mode=mode,
                game_filter=game_filter,
                general_list=self.paths.general_list,
                exclude_list=self.paths.exclude_list,
                bin_dir=self.paths.bin_dir,
            )
        except PresetError as exc:
            return {"ok": False, "error": str(exc), "command_line": ""}
        return {
            "ok": True,
            "command_line": build.command_line,
            "warnings": build.warnings,
            "skipped_files": build.skipped_files,
            "wf_tcp": build.wf_tcp,
            "wf_udp": build.wf_udp,
        }

    # ------------------------------------------------------------------ config
    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        if key not in (
            "preset_id",
            "mode",
            "game_filter",
            "minimize_to_tray",
            "last_tab",
        ):
            raise ApplicationError("Эта настройка недоступна для изменения")
        if key == "preset_id":
            store = self._require_preset_store()
            ids = {preset["id"] for preset in store.public_presets()}
            if value not in ids:
                raise ApplicationError("Неизвестный пресет")
        try:
            settings = self.settings.update({key: value})
        except SettingsError as exc:
            raise ApplicationError(str(exc)) from exc
        return {"ok": True, "settings": settings}

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ApplicationError("Некорректное значение автозапуска")
        try:
            actual = autostart.set_enabled(enabled)
        except AutostartError as exc:
            try:
                actual = autostart.is_enabled()
            except AutostartError:
                actual = False
            return {
                "ok": False,
                "error": f"Не удалось изменить автозапуск: {exc}",
                "autostart": actual,
            }
        try:
            self.settings.update({"autostart": actual})
        except SettingsError:
            pass
        return {
            "ok": True,
            "autostart": actual,
            "task_name": autostart.TASK_NAME,
            "task_command": autostart.task_command_line(),
        }

    # ------------------------------------------------------------------- lists
    def _list_path(self, key: str) -> Path:
        if key not in _LIST_FILES:
            raise ApplicationError("Неизвестный список")
        return self.paths.lists_dir / _LIST_FILES[key][0]

    def read_lists(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ok": True, "lists": {}}
        for key, (filename, title) in _LIST_FILES.items():
            path = self._list_path(key)
            try:
                if not path.is_file():
                    result["ok"] = False
                    result["lists"][key] = {
                        "content": "",
                        "path": str(path),
                        "title": title,
                        "filename": filename,
                        "missing": True,
                        "entries": 0,
                    }
                    continue
                if path.stat().st_size > _MAX_LIST_BYTES:
                    raise ApplicationError(f"{filename} превышает 4 МБ")
                content = path.read_text(encoding="utf-8-sig")
                result["lists"][key] = {
                    "content": content,
                    "path": str(path),
                    "title": title,
                    "filename": filename,
                    "missing": False,
                    "entries": _count_entries(content),
                }
            except (OSError, UnicodeDecodeError) as exc:
                result["ok"] = False
                result["lists"][key] = {
                    "content": "",
                    "path": str(path),
                    "title": title,
                    "filename": filename,
                    "missing": not path.exists(),
                    "entries": 0,
                    "error": f"Не удалось прочитать {filename}: {exc}",
                }
        return result

    def save_list(self, key: str, content: str) -> dict[str, Any]:
        path = self._list_path(key)
        if not isinstance(content, str):
            raise ApplicationError("Содержимое списка должно быть текстом")
        if len(content.encode("utf-8", errors="surrogatepass")) > _MAX_LIST_BYTES:
            raise ApplicationError("Список слишком большой (максимум 4 МБ)")
        if "\x00" in content:
            raise ApplicationError("Список содержит недопустимые нулевые символы")
        try:
            content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ApplicationError(
                "Список содержит символы, которые нельзя сохранить в UTF-8"
            ) from exc
        content = content.lstrip("\ufeff")
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        if content and not content.endswith("\n"):
            content += "\n"

        path.parent.mkdir(parents=True, exist_ok=True)
        backup = path.with_suffix(path.suffix + ".bak")
        tmp_path = ""
        try:
            if path.is_file():
                shutil.copy2(path, backup)
            fd, tmp_path = tempfile.mkstemp(
                prefix=f".{path.name}-", suffix=".tmp", dir=str(path.parent)
            )
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            tmp_path = ""
        except OSError as exc:
            raise ApplicationError(f"Не удалось сохранить {path.name}: {exc}") from exc
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        entries = _count_entries(content)
        return {
            "ok": True,
            "key": key,
            "path": str(path),
            "backup": str(backup) if backup.exists() else None,
            "entries": entries,
            "saved_at": time.time(),
            "message": "Список сохранён. winws автоматически перечитает изменённый файл.",
        }

    # --------------------------------------------------------------- shutdown
    def shutdown(self) -> None:
        self.usage.end_bypass()
        self.manager.shutdown()
        self.usage.finish_session()
        self._state_callback = None


def _count_entries(content: str) -> int:
    count = 0
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", ";", "/")):
            count += 1
    return count
