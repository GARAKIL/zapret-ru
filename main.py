"""Zapret RU entry point.

The application contains its own WinDivert-based DPI evasion engine. It does
not start winws.exe or download code at runtime. Packet policy comes from
presets.json and is shown in the UI.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from typing import Any

from core import winutils
from core.application import ApplicationCore, ApplicationError
from core.paths import (
    APP_ID,
    APP_MUTEX,
    APP_NAME,
    APP_VERSION,
    AppPaths,
    get_paths,
    is_frozen,
)
from core.presets import PresetError
from core.settings import SettingsError
from core.tray import TrayController

log = logging.getLogger("zapretru")
_MUTEX_HANDLE: Any = None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Запущено планировщиком задач: стартовать свёрнутым в трей",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Открыть инструменты разработчика WebView2 (debug-режим)",
    )
    parser.add_argument(
        "--engine-smoke",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def _elevate(argv: list[str]) -> bool:
    if winutils.is_admin():
        return True

    if is_frozen():
        executable = Path(sys.argv[0]).resolve()
        parameters = subprocess.list2cmdline(argv)
        workdir = executable.parent
    else:
        script = Path(sys.argv[0]).resolve()
        executable = Path(sys.executable).resolve()
        parameters = subprocess.list2cmdline([str(script), *argv])
        workdir = script.parent

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            str(executable),
            parameters,
            str(workdir),
            1,
        )
    except Exception:
        result = 0
    if int(result) <= 32:
        winutils.message_box(
            APP_NAME,
            "Для перехвата трафика через WinDivert требуются права администратора.\n\n"
            "Запуск отменён или Windows отклонила запрос UAC.",
            error=True,
        )
    return False


def _acquire_single_instance() -> bool:
    global _MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, APP_MUTEX)
    if not handle:
        return True
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    _MUTEX_HANDLE = handle
    return True


def _setup_logging(paths: AppPaths) -> None:
    try:
        paths.data_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            paths.data_dir / "launcher.log",
            maxBytes=512 * 1024,
            backupCount=1,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        if sys.stderr is not None:
            stream = logging.StreamHandler()
            stream.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            root.addHandler(stream)
    except OSError:
        pass
    log.info("Starting %s %s", APP_NAME, APP_VERSION)
    log.info("Executable dir: %s", paths.app_dir)
    log.info("Data dir: %s", paths.data_dir)


def _install_dpi_awareness() -> None:
    try:
        # PER_MONITOR_AWARE_V2, best effort on older Windows versions.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


class LauncherApi:
    """The only Python surface exposed to the local HTML page."""

    def __init__(self, app: LauncherApplication) -> None:
        self._app = app
        self._core = app.core

    # --------------------------------------------------------------- wrappers
    def _guard(self, func: Any, *args: Any) -> dict[str, Any]:
        try:
            return func(*args)
        except (ApplicationError, PresetError, SettingsError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            log.exception("UI API call failed: %s", getattr(func, "__name__", func))
            return {"ok": False, "error": f"Внутренняя ошибка: {exc}"}

    # -------------------------------------------------------------------- data
    def bootstrap(self) -> dict[str, Any]:
        return self._guard(self._core.bootstrap)

    def get_status(self) -> dict[str, Any]:
        return self._guard(self._core.get_status)

    def get_logs(self, after_seq: int = 0) -> dict[str, Any]:
        return self._guard(self._core.get_logs, after_seq)

    def clear_logs(self) -> dict[str, Any]:
        return self._guard(self._core.clear_logs)

    def check_connectivity(self) -> dict[str, Any]:
        return self._guard(self._core.check_connectivity)

    def refresh_environment(self) -> dict[str, Any]:
        return self._guard(self._core.refresh_environment)

    # ------------------------------------------------------------------ engine
    def start_bypass(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        result = self._guard(self._core.start_bypass, preset_id, mode, game_filter)
        self._app.tray.refresh()
        return result

    def stop_bypass(self) -> dict[str, Any]:
        result = self._guard(self._core.stop_bypass)
        self._app.tray.refresh()
        return result

    def restart_bypass(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        result = self._guard(self._core.restart_bypass, preset_id, mode, game_filter)
        self._app.tray.refresh()
        return result

    def command_preview(
        self, preset_id: str, mode: str, game_filter: bool
    ) -> dict[str, Any]:
        return self._guard(self._core.command_preview, preset_id, mode, game_filter)

    # ------------------------------------------------------------------ config
    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        return self._guard(self._core.update_setting, key, value)

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        return self._guard(self._core.set_autostart, enabled)

    def get_presets(self) -> dict[str, Any]:
        return self._guard(self._core.get_presets)

    def reload_presets(self) -> dict[str, Any]:
        return self._guard(self._core.reload_presets)

    # ------------------------------------------------------------------- lists
    def read_lists(self) -> dict[str, Any]:
        return self._guard(self._core.read_lists)

    def save_list(self, key: str, content: str) -> dict[str, Any]:
        return self._guard(self._core.save_list, key, content)

    # ---------------------------------------------------------------- window
    def window_minimize(self) -> dict[str, Any]:
        return self._app.minimize_window()

    def window_toggle_maximize(self) -> dict[str, Any]:
        return self._app.toggle_maximize()

    def window_close(self) -> dict[str, Any]:
        return self._app.close_window_from_ui()

    def show_window(self) -> dict[str, Any]:
        self._app.show_window()
        return {"ok": True}

    # ---------------------------------------------------------------- desktop
    def open_folder(self, kind: str) -> dict[str, Any]:
        allowed = {
            "data": self._core.paths.data_dir,
            "engine": self._core.paths.data_dir,
            "bin": self._core.paths.data_dir,
            "lists": self._core.paths.lists_dir,
            "presets": self._core.paths.presets_file,
        }
        target = allowed.get(kind)
        if target is None:
            return {"ok": False, "error": "Неизвестный раздел"}
        if kind in ("data", "engine", "bin"):
            try:
                target.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return {"ok": False, "error": str(exc)}
        if kind == "presets":
            opened = winutils.reveal_in_explorer(target)
        else:
            opened = winutils.open_path(target)
        return {
            "ok": opened,
            "error": None if opened else "Не удалось открыть проводник",
        }

    def copy_text(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str) or len(text) > 1_000_000:
            return {"ok": False, "error": "Слишком большой текст"}
        copied = winutils.copy_text_to_clipboard(text)
        return {"ok": copied, "error": None if copied else "Буфер обмена недоступен"}

    def open_link(self, key: str) -> dict[str, Any]:
        links = {
            "github": "https://github.com/GARAKIL/zapret-ru",
            "releases": "https://github.com/GARAKIL/zapret-ru/releases",
            "driver": "https://github.com/basil00/WinDivert",
            "zapret": "https://github.com/bol-van/zapret",
            "bundle": "https://github.com/bol-van/zapret-win-bundle",
            "webview2": "https://developer.microsoft.com/microsoft-edge/webview2/",
        }
        url = links.get(key)
        if not url:
            return {"ok": False, "error": "Ссылка недоступна"}
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


class LauncherApplication:
    def __init__(self, core: ApplicationCore, paths: AppPaths) -> None:
        self.core = core
        self.paths = paths
        self.window: Any = None
        self._webview: Any = None
        self._closing_lock = threading.RLock()
        self._quitting = False
        self._allow_close = False
        self._maximized = False
        self.tray = TrayController(
            core=core,
            assets_dir=paths.assets_dir,
            show_callback=self.show_window,
            quit_callback=self.quit_application,
        )
        self.api = LauncherApi(self)
        core.set_state_callback(self._on_core_state_changed)

    # ------------------------------------------------------------------ window
    def create_window(self, hidden: bool) -> Any:
        import webview

        self._webview = webview
        window = webview.create_window(
            f"{APP_NAME} {APP_VERSION}",
            url=self.paths.ui_index.as_uri(),
            js_api=self.api,
            width=1120,
            height=800,
            min_size=(960, 680),
            resizable=True,
            fullscreen=False,
            frameless=True,
            easy_drag=False,
            shadow=True,
            focus=True,
            minimized=False,
            on_top=False,
            confirm_close=False,
            background_color="#07080d",
            transparent=False,
            text_select=True,
            zoomable=False,
            hidden=hidden,
        )
        if window is None:
            raise RuntimeError("PyWebView не смог создать окно")
        self.window = window
        window.events.closing += self._on_closing
        window.events.closed += self._on_closed
        return window

    def run(self, debug: bool, start_hidden: bool) -> None:
        import webview

        tray_ok = self.tray.start()
        if not tray_ok:
            log.warning("Tray is unavailable; close will exit the application")
        hidden = bool(start_hidden and tray_ok)
        self.create_window(hidden=hidden)
        icon_path = self.paths.assets_dir / "icon.ico"
        if not icon_path.is_file():
            icon_path = self.paths.assets_dir / "icon.png"
        start_icon = str(icon_path) if icon_path.is_file() else None
        log.info("Starting WebView2 UI")
        webview.start(
            gui="edgechromium",
            debug=debug,
            icon=start_icon,
        )

    def _on_core_state_changed(self) -> None:
        self.tray.refresh()

    def show_window(self) -> None:
        if self.window is None:
            return
        try:
            self.window.restore()
        except Exception:
            pass
        try:
            self.window.show()
        except Exception:
            log.debug("Could not show window", exc_info=True)
            return
        try:
            self.window.evaluate_js("window.zapretOnShow && window.zapretOnShow()")
        except Exception:
            pass

    def minimize_window(self) -> dict[str, Any]:
        if self.window is None:
            return {"ok": False, "error": "Окно ещё не готово"}
        try:
            self.window.minimize()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def toggle_maximize(self) -> dict[str, Any]:
        if self.window is None:
            return {"ok": False, "error": "Окно ещё не готово"}
        try:
            if self._maximized:
                self.window.restore()
                self._maximized = False
            else:
                self.window.maximize()
                self._maximized = True
            return {"ok": True, "maximized": self._maximized}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def close_window_from_ui(self) -> dict[str, Any]:
        settings = self.core.settings.snapshot()
        if settings.get("minimize_to_tray", True) and self.tray.available:
            try:
                self.window.hide()
                return {"ok": True, "action": "tray"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        self._request_close_now()
        return {"ok": True, "action": "close"}

    def _request_close_now(self) -> None:
        with self._closing_lock:
            self._allow_close = True
            self._quitting = True
        window = self.window
        if window is not None:
            try:
                window.destroy()
            except Exception:
                log.exception("Could not destroy window")

    def _on_closing(self) -> bool:
        with self._closing_lock:
            if self._allow_close or self._quitting:
                return True
            if not self.core.settings.snapshot().get("minimize_to_tray", True):
                self._allow_close = True
                self._quitting = True
                return True
            if not self.tray.available:
                self._allow_close = True
                self._quitting = True
                return True
        try:
            self.window.hide()
        except Exception:
            log.debug("Could not hide window on close", exc_info=True)
        return False

    def _on_closed(self) -> None:
        log.info("Main window closed")
        self.tray.stop()

    def quit_application(self) -> None:
        with self._closing_lock:
            if self._quitting:
                # Still make sure a pending window gets closed.
                pass
            self._quitting = True
            self._allow_close = True
        log.info("Application shutdown requested")
        self.tray.stop()
        window = self.window
        if window is not None:
            try:
                window.destroy()
            except Exception:
                log.exception("Could not destroy window during quit")
        # If the window was never created, there is no webview loop to unwind.
        if self.window is None:
            self.shutdown()

    def shutdown(self) -> None:
        with self._closing_lock:
            if getattr(self, "_shutdown_done", False):
                return
            self._shutdown_done = True
            self._quitting = True
            self._allow_close = True
        try:
            self.tray.stop()
        finally:
            try:
                self.core.shutdown()
            finally:
                log.info("Application stopped")


def _run_engine_smoke(paths: AppPaths) -> int:
    """Hidden diagnostic used to validate a compiled onefile build."""
    output = Path(tempfile.gettempdir()) / "zapretru-engine-smoke.json"
    core: ApplicationCore | None = None
    try:
        core = ApplicationCore(paths)
        start = core.start_bypass("smart", "global", False)
        time.sleep(2.0)
        check = core.check_connectivity()
        payload = {
            "ok": bool(start.get("ok")) and bool(check.get("reachable")),
            "start": start,
            "check": check,
            "status": core.get_status(),
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 0 if payload["ok"] else 1
    except Exception as exc:
        output.write_text(
            json.dumps(
                {"ok": False, "error": str(exc), "traceback": traceback.format_exc()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1
    finally:
        if core is not None:
            core.shutdown()


def _show_startup_error(message: str, details: str = "") -> None:
    text = message
    if details:
        text += "\n\n" + details
    winutils.message_box(APP_NAME, text, error=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if os.name != "nt":
        _show_startup_error("Zapret RU предназначен для Windows.")
        return 1

    if not _elevate(sys.argv[1:] if argv is None else argv):
        return 0

    paths = get_paths()
    _setup_logging(paths)
    _install_dpi_awareness()
    winutils.set_app_user_model_id(f"{APP_ID}.Launcher")

    if not _acquire_single_instance():
        if not args.autostart:
            winutils.message_box(
                APP_NAME,
                "Zapret RU уже запущен.\n\nОткройте приложение из области уведомлений.",
            )
        return 0

    if args.engine_smoke:
        return _run_engine_smoke(paths)

    if not paths.ui_index.is_file():
        _show_startup_error(
            "Не найден интерфейс приложения.",
            f"Ожидался файл:\n{paths.ui_index}",
        )
        return 1

    try:
        import webview  # noqa: F401
    except ImportError as exc:
        _show_startup_error(
            "Не установлены зависимости интерфейса.",
            "Выполните в папке проекта:\n\npython -m pip install -r requirements.txt\n\n"
            f"Техническая информация: {exc}",
        )
        return 1

    core: ApplicationCore | None = None
    app: LauncherApplication | None = None
    try:
        core = ApplicationCore(paths)
        app = LauncherApplication(core, paths)
        for note in core.data_notes:
            log.info(note)
        if core.presets_error:
            log.error("Presets: %s", core.presets_error)
        app.run(debug=args.debug, start_hidden=args.autostart)
        return 0
    except Exception as exc:
        log.exception("Unhandled startup/runtime error")
        _show_startup_error(
            "Произошла ошибка при запуске Zapret RU.",
            f"{exc}\n\nПодробности: {paths.data_dir / 'launcher.log'}",
        )
        return 1
    finally:
        if app is not None:
            app.shutdown()
        elif core is not None:
            core.shutdown()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        log.exception("Fatal unhandled error")
        _show_startup_error(
            "Критическая ошибка.",
            traceback.format_exc(limit=4),
        )
        raise SystemExit(1)
