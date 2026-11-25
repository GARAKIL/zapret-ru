"""System tray integration built on pystray + Pillow."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.application import ApplicationCore
from core.paths import APP_ID, APP_NAME

log = logging.getLogger(__name__)


class TrayController:
    def __init__(
        self,
        core: ApplicationCore,
        assets_dir: Path,
        show_callback: Callable[[], None],
        quit_callback: Callable[[], None],
    ) -> None:
        self._core = core
        self._assets_dir = assets_dir
        self._show_callback = show_callback
        self._quit_callback = quit_callback
        self._icon: Any = None
        self._pystray: Any = None
        self._lock = threading.RLock()
        self._started = False
        self._stopping = False

    @property
    def available(self) -> bool:
        return self._icon is not None and self._started and not self._stopping

    def start(self) -> bool:
        try:
            import pystray
            from PIL import Image
        except ImportError as exc:
            log.warning("Tray dependencies are unavailable: %s", exc)
            return False

        image = self._load_image(Image)
        self._pystray = pystray
        self._icon = pystray.Icon(
            APP_ID,
            image,
            APP_NAME,
            menu=self._build_menu(),
        )
        try:
            self._icon.run_detached()
            self._started = True
            self.refresh()
        except Exception:
            log.exception("Could not start system tray icon")
            self._icon = None
            return False
        return True

    def _load_image(self, image_module: Any) -> Any:
        icon_path = self._assets_dir / "icon.png"
        try:
            return image_module.open(icon_path).convert("RGBA")
        except Exception:
            log.debug("Bundled tray icon could not be loaded", exc_info=True)

        # Fallback is visually simple but always available if the bundled asset
        # was omitted from a custom build.
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 62, 62), radius=15, fill=(18, 20, 26, 255))
        draw.polygon(
            [(32, 8), (54, 16), (50, 42), (32, 57), (14, 42), (10, 16)],
            fill=(88, 225, 184, 255),
        )
        draw.line([(23, 32), (30, 40), (43, 24)], fill=(8, 20, 16, 255), width=5)
        return image

    def _build_menu(self) -> Any:
        pystray = self._pystray
        if pystray is None:
            return None
        running = self._core.manager.is_running()
        state_text = "Обход активен" if running else "Обход выключен"
        return pystray.Menu(
            pystray.MenuItem(state_text, self._on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Открыть окно", self._on_show),
            pystray.MenuItem("Запустить обход", self._on_start, enabled=not running),
            pystray.MenuItem("Остановить обход", self._on_stop, enabled=running),
            pystray.MenuItem("Проверить доступ", self._on_check),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._on_quit),
        )

    def refresh(self) -> None:
        with self._lock:
            if self._icon is None or self._stopping:
                return
            running = self._core.manager.is_running()
            self._icon.title = (
                f"{APP_NAME} · {'обход активен' if running else 'обход выключен'}"
            )
            try:
                self._icon.menu = self._build_menu()
                self._icon.update_menu()
            except Exception:
                log.debug("Tray menu refresh failed", exc_info=True)

    def notify(self, message: str, title: str = APP_NAME) -> None:
        if not self.available:
            return
        try:
            self._icon.notify(message[:250], title)
        except Exception:
            log.debug("Tray notification is unavailable", exc_info=True)

    def stop(self) -> None:
        with self._lock:
            if self._stopping:
                return
            self._stopping = True
            icon = self._icon
            self._icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                log.debug("Tray icon stop failed", exc_info=True)
        self._started = False

    # --------------------------------------------------------------- callbacks
    def _on_show(self, icon: Any = None, item: Any = None) -> None:
        try:
            self._show_callback()
        except Exception:
            log.exception("Tray show callback failed")

    def _on_start(self, icon: Any = None, item: Any = None) -> None:
        try:
            settings = self._core.settings.snapshot()
            result = self._core.start_bypass(
                settings["preset_id"], settings["mode"], settings["game_filter"]
            )
            if result.get("ok"):
                self.notify("Обход запущен", APP_NAME)
            else:
                self.notify(
                    result.get("error") or "Не удалось запустить обход", APP_NAME
                )
            self.refresh()
        except Exception as exc:
            log.exception("Tray start failed")
            self.notify(str(exc), "Ошибка запуска")
            self.refresh()

    def _on_stop(self, icon: Any = None, item: Any = None) -> None:
        try:
            self._core.stop_bypass()
            self.notify("Обход остановлен", APP_NAME)
            self.refresh()
        except Exception as exc:
            log.exception("Tray stop failed")
            self.notify(str(exc), "Ошибка остановки")

    def _on_check(self, icon: Any = None, item: Any = None) -> None:
        try:
            result = self._core.check_connectivity()
            services = result.get("services", [])
            summary = ", ".join(
                f"{item['label']}: {'OK' if item['ok'] else item.get('error', 'ошибка')}"
                for item in services
            )
            self.notify(summary or "Проверка завершена", "Доступность сервисов")
        except Exception as exc:
            log.exception("Tray connectivity check failed")
            self.notify(str(exc), "Ошибка проверки")

    def _on_quit(self, icon: Any = None, item: Any = None) -> None:
        try:
            self._quit_callback()
        except Exception:
            log.exception("Tray quit callback failed")
