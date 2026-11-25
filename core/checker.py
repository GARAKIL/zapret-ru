"""Fast, concurrent connectivity diagnostics used by the UI."""

from __future__ import annotations

import queue
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

TIMEOUT_SECONDS = 3.0
_MAX_BODY = 32 * 1024
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class CheckTarget:
    id: str
    label: str
    url: str
    description: str


TARGETS = (
    CheckTarget(
        "youtube",
        "YouTube",
        "https://www.youtube.com/generate_204",
        "Google / видеохостинг",
    ),
    CheckTarget(
        "discord",
        "Discord",
        "https://discord.com/api/v10/gateway",
        "Discord API",
    ),
    CheckTarget(
        "cloudflare",
        "Cloudflare",
        "https://www.cloudflare.com/cdn-cgi/trace",
        "Cloudflare edge",
    ),
)


def _error_text(exc: BaseException) -> tuple[str, str]:
    detail = str(exc).strip()
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "Таймаут", f"Нет ответа за {TIMEOUT_SECONDS:.0f} с"
    if isinstance(exc, socket.gaierror):
        return "Ошибка DNS", detail or "Не удалось разрешить имя"
    if isinstance(exc, ssl.SSLError):
        return "Ошибка TLS", detail or "TLS-соединение не установлено"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, BaseException):
            return _error_text(reason)
        return "Сеть недоступна", str(reason)
    if isinstance(exc, ConnectionResetError):
        return "Сброс соединения", detail or "Соединение разорвано"
    if isinstance(exc, OSError):
        if getattr(exc, "winerror", None) == 10054:
            return "Сброс соединения", detail
        return "Сеть недоступна", detail or "Ошибка сокета"
    return "Ошибка", detail or exc.__class__.__name__


def check_target(target: CheckTarget) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        target.url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context),
    )
    status: int | None = None
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(response.getcode())
            response.read(_MAX_BODY)
        latency = int((time.perf_counter() - started) * 1000)
        ok = 200 <= status < 500
        return {
            "id": target.id,
            "label": target.label,
            "url": target.url,
            "description": target.description,
            "ok": ok,
            "status": status,
            "latency_ms": latency,
            "error": None if ok else f"HTTP {status}",
            "detail": None if ok else "Сервер вернул ошибку",
        }
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        latency = int((time.perf_counter() - started) * 1000)
        # An HTTP status means that DNS, TCP and TLS all succeeded. 4xx is not
        # necessarily a DPI block; 5xx means the endpoint itself is unhealthy.
        ok = 200 <= status < 500
        return {
            "id": target.id,
            "label": target.label,
            "url": target.url,
            "description": target.description,
            "ok": ok,
            "status": status,
            "latency_ms": latency,
            "error": None if ok else f"HTTP {status}",
            "detail": None if ok else "Ошибка на стороне сервиса",
        }
    except Exception as exc:  # network errors are expected and shown in UI
        latency = int((time.perf_counter() - started) * 1000)
        short, detail = _error_text(exc)
        return {
            "id": target.id,
            "label": target.label,
            "url": target.url,
            "description": target.description,
            "ok": False,
            "status": status,
            "latency_ms": latency,
            "error": short,
            "detail": detail,
        }


def check_services() -> dict[str, Any]:
    """Run all checks concurrently and cap the total wait at ~3 seconds.

    Worker threads are daemons. A pathological DNS resolver therefore cannot
    keep the GUI process alive after the user closes it.
    """
    started_at = time.time()
    results: dict[str, dict[str, Any]] = {}
    result_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    workers: list[threading.Thread] = []

    def run(target: CheckTarget) -> None:
        result_queue.put(check_target(target))

    for target in TARGETS:
        worker = threading.Thread(
            target=run,
            args=(target,),
            name=f"check-{target.id}",
            daemon=True,
        )
        workers.append(worker)
        worker.start()

    deadline = time.monotonic() + TIMEOUT_SECONDS + 0.6
    for _ in TARGETS:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            item = result_queue.get(timeout=remaining)
            results[item["id"]] = item
        except queue.Empty:
            break

    for target in TARGETS:
        if target.id not in results:
            results[target.id] = {
                "id": target.id,
                "label": target.label,
                "url": target.url,
                "description": target.description,
                "ok": False,
                "status": None,
                "latency_ms": int(TIMEOUT_SECONDS * 1000),
                "error": "Таймаут",
                "detail": "Проверка не завершилась за отведённое время",
            }

    ordered = [results[target.id] for target in TARGETS]
    reachable = sum(1 for item in ordered if item["ok"])
    return {
        "ok": True,
        "checked_at": started_at,
        "timeout_seconds": TIMEOUT_SECONDS,
        "services": ordered,
        "reachable": reachable,
        "total": len(ordered),
    }
