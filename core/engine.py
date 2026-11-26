"""Built-in DPI evasion engine.

The engine is our own packet-processing logic. It uses the signed WinDivert
driver bundled with PyDivert to intercept outbound packets; it does not start
winws.exe or any other zapret process.

Strategy: split the first TCP segments that carry a TLS ClientHello or an HTTP
Host header. For TLS the split is placed inside the SNI hostname, so a DPI that
only inspects one TCP segment cannot read the domain. QUIC/UDP 443 can be
dropped to force browsers to fall back to TCP.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    import pydivert
    from pydivert import Packet, WinDivert
    from pydivert.consts import Direction, Layer
except Exception as exc:  # noqa: BLE001  # pragma: no cover - handled at runtime
    pydivert = None
    Packet = None  # type: ignore[assignment]
    WinDivert = None  # type: ignore[assignment]
    Direction = None  # type: ignore[assignment]
    Layer = None  # type: ignore[assignment]
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None

log = logging.getLogger(__name__)

_MAX_LOG_ENTRIES = 2500
_MAX_LINE_CHARS = 8000
_MAX_FLOWS = 8192
_FLOW_TTL = 120.0


class EngineError(Exception):
    """Friendly engine start or runtime error."""


@dataclass(frozen=True)
class HostInfo:
    host: str
    start: int
    length: int
    kind: str


@dataclass(frozen=True)
class EngineConfig:
    profile_id: str
    profile_name: str
    split: int | str
    block_quic: bool
    mode: str
    include: frozenset[str]
    exclude: frozenset[str]

    def describe(self) -> str:
        split = "SNI" if self.split in ("sni", "smart") else str(self.split)
        quic = "QUIC off" if self.block_quic else "QUIC on"
        return f"{self.profile_name}: split {split}, {quic}, {self.mode}"


def _u16(data: bytes | memoryview, offset: int) -> int:
    return (data[offset] << 8) | data[offset + 1]


def normalize_host(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    if value.count(":") == 1:
        value = value.split(":", 1)[0]
    return value


def _domain_matches(host: str, rule: str) -> bool:
    rule = normalize_host(rule)
    if not rule:
        return False
    if rule.startswith("*."):
        suffix = rule[2:]
        return host == suffix or host.endswith("." + suffix)
    return host == rule or host.endswith("." + rule)


def domain_allowed(host: str, config: EngineConfig) -> bool:
    host = normalize_host(host)
    if not host:
        return False
    for rule in config.exclude:
        if _domain_matches(host, rule):
            return False
    if config.mode == "global":
        return True
    return any(_domain_matches(host, rule) for rule in config.include)


def parse_tls_client_hello(payload: bytes | bytearray | memoryview) -> HostInfo | None:
    """Return the SNI hostname and its byte range from a TLS ClientHello."""
    data = bytes(payload)
    if len(data) < 50 or data[0] != 0x16 or data[1] != 0x03 or data[5] != 0x01:
        return None
    handshake_len = int.from_bytes(data[6:9], "big")
    body_end = min(len(data), 9 + handshake_len)
    try:
        pos = 9 + 2 + 32  # legacy_version + random
        session_len = data[pos]
        pos += 1 + session_len
        cipher_len = _u16(data, pos)
        pos += 2 + cipher_len
        compression_len = data[pos]
        pos += 1 + compression_len
        if pos + 2 > body_end:
            return None
        extensions_len = _u16(data, pos)
        pos += 2
        extensions_end = min(pos + extensions_len, body_end)
        while pos + 4 <= extensions_end:
            ext_type = _u16(data, pos)
            ext_len = _u16(data, pos + 2)
            ext_start = pos + 4
            ext_end = ext_start + ext_len
            if ext_end > extensions_end:
                break
            if ext_type == 0 and ext_len >= 5:
                list_len = _u16(data, ext_start)
                entry = ext_start + 2
                list_end = min(entry + list_len, ext_end)
                while entry + 3 <= list_end:
                    name_type = data[entry]
                    name_len = _u16(data, entry + 1)
                    name_start = entry + 3
                    name_end = name_start + name_len
                    if name_end > list_end:
                        break
                    if name_type == 0 and name_len:
                        host = normalize_host(
                            data[name_start:name_end].decode("ascii", "ignore")
                        )
                        if host:
                            return HostInfo(host, name_start, name_len, "tls")
                    entry = name_end
            pos = ext_end
    except (IndexError, ValueError):
        return None
    return None


def parse_http_host(payload: bytes | bytearray | memoryview) -> HostInfo | None:
    data = bytes(payload[:4096])
    header_end = data.find(b"\r\n\r\n")
    if header_end >= 0:
        data = data[:header_end]
    lowered = data.lower()
    index = lowered.find(b"host:")
    if index < 0:
        return None
    if index > 0 and data[index - 1] not in (10, 13):
        return None
    start = index + 5
    while start < len(data) and data[start] in (32, 9):
        start += 1
    end = start
    while end < len(data) and data[end] not in (13, 10):
        end += 1
    if end <= start:
        return None
    raw = data[start:end].strip()
    host = normalize_host(raw.decode("ascii", "ignore"))
    if not host or " " in host:
        return None
    return HostInfo(host, start, end - start, "http")


def extract_host(payload: bytes | bytearray | memoryview) -> HostInfo | None:
    if not payload:
        return None
    if payload[0] == 0x16:
        return parse_tls_client_hello(payload)
    return parse_http_host(payload)


def split_position(payload: bytes, host: HostInfo | None, strategy: int | str) -> int:
    """Choose a byte offset that is strictly inside the payload."""
    if len(payload) < 2:
        return 0
    host_strategy = isinstance(strategy, str) and strategy in (
        "sni",
        "sni-start",
        "sni-end",
        "host",
        "smart",
    )
    if host is not None and host_strategy:
        if strategy == "sni-start":
            offset = host.start + 1
        elif strategy == "sni-end":
            offset = host.start + max(1, host.length - 1)
        else:
            offset = host.start + max(1, host.length // 2)
    elif isinstance(strategy, int):
        offset = strategy
    else:
        offset = 1
    return min(max(1, offset), len(payload) - 1)


class NativeEngine:
    """Threaded WinDivert engine with a winws-like status/log interface."""

    def __init__(self, on_state_change: Callable[[], None] | None = None) -> None:
        self._on_state_change = on_state_change
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._handle: Any = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._running = False
        self._shutting_down = False
        self._started_at: float | None = None
        self._config: EngineConfig | None = None
        self._active_config: dict[str, Any] = {}
        self._last_error: str | None = None
        self._logs: deque[dict[str, Any]] = deque(maxlen=_MAX_LOG_ENTRIES)
        self._next_seq = 1
        self._stats: dict[str, int] = {
            "packets": 0,
            "split_packets": 0,
            "quic_dropped": 0,
            "passed": 0,
        }
        self._flows: dict[tuple[Any, ...], float] = {}

    # ------------------------------------------------------------------ logs
    def _append_log_locked(self, text: str, kind: str = "system") -> None:
        text = str(text).replace("\x00", "").strip("\r\n")
        if not text:
            return
        if len(text) > _MAX_LINE_CHARS:
            text = text[:_MAX_LINE_CHARS] + " …"
        self._logs.append(
            {
                "seq": self._next_seq,
                "time": time.strftime("%H:%M:%S"),
                "ts": time.time(),
                "text": text,
                "kind": kind,
            }
        )
        self._next_seq += 1

    def append_system_log(self, text: str, kind: str = "system") -> None:
        with self._lock:
            self._append_log_locked(text, kind)

    def logs_after(self, after_seq: int = 0) -> dict[str, Any]:
        try:
            after = max(0, int(after_seq))
        except (TypeError, ValueError):
            after = 0
        with self._lock:
            return {
                "ok": True,
                "entries": [entry for entry in self._logs if entry["seq"] > after],
                "next_seq": self._next_seq - 1,
            }

    def clear_logs(self) -> dict[str, Any]:
        with self._lock:
            self._logs.clear()
            self._next_seq = 1
        self._notify_state_changed()
        return {"ok": True, "next_seq": 0}

    # --------------------------------------------------------------- lifecycle
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def process_pid(self) -> int | None:
        return None

    def start(
        self, config: EngineConfig, active_config: dict[str, Any]
    ) -> dict[str, Any]:
        if _IMPORT_ERROR is not None:
            return {
                "ok": False,
                "started": False,
                "error": "Встроенный драйвер WinDivert не загрузился: "
                + str(_IMPORT_ERROR),
                "status": self.status(),
            }
        with self._lifecycle_lock:
            with self._lock:
                if self._running:
                    return {
                        "ok": False,
                        "started": False,
                        "error": "Обход уже запущен",
                        "status": self.status(),
                    }
                self._stop_event.clear()
                self._ready.clear()
                self._last_error = None
                self._config = config
                self._active_config = dict(active_config)
                self._stats = {
                    "packets": 0,
                    "split_packets": 0,
                    "quic_dropped": 0,
                    "passed": 0,
                }
                self._flows.clear()
                self._running = True
                self._started_at = time.time()
                self._append_log_locked(
                    "Запуск встроенного движка: " + config.describe(), "system"
                )
                self._thread = threading.Thread(
                    target=self._worker,
                    name="zapret-native-engine",
                    daemon=True,
                )
                self._thread.start()

            if not self._ready.wait(timeout=4.0):
                with self._lock:
                    self._last_error = "Движок не успел открыть WinDivert за 4 секунды."
                    self._running = False
                return {
                    "ok": False,
                    "started": False,
                    "error": self._last_error,
                    "status": self.status(),
                }
            with self._lock:
                error = self._last_error
                running = self._running
            self._notify_state_changed()
            return {
                "ok": running and error is None,
                "started": running,
                "error": error,
                "status": self.status(),
            }

    def _build_filter(self, config: EngineConfig) -> str:
        parts = ["tcp.DstPort == 80", "tcp.DstPort == 443"]
        if config.block_quic:
            parts.append("udp.DstPort == 443")
        return "outbound and (" + " or ".join(parts) + ")"

    def _worker(self) -> None:
        config = self._config
        if config is None:
            return
        try:
            with WinDivert(self._build_filter(config), layer=Layer.NETWORK) as handle:
                with self._lock:
                    self._handle = handle
                    self._append_log_locked(
                        "WinDivert подключён. Слушаем TCP 80/443"
                        + (" и блокируем QUIC/UDP 443." if config.block_quic else "."),
                        "system",
                    )
                self._ready.set()
                for packet in handle:
                    if self._stop_event.is_set():
                        break
                    try:
                        self._handle_packet(handle, packet)
                    except Exception:
                        log.exception("Packet processing failed")
                        try:
                            handle.send(packet)
                        except Exception:
                            log.debug("Could not reinject packet", exc_info=True)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                if not self._stop_event.is_set():
                    self._last_error = self._friendly_error(exc)
                    self._append_log_locked(self._last_error, "error")
                self._ready.set()
        finally:
            with self._lock:
                self._handle = None
                self._running = False
                self._started_at = None
                self._active_config = {}
            self._notify_state_changed()

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        text = str(exc)
        code = getattr(exc, "winerror", None)
        if code in (5, 13) or "Access is denied" in text or "отказано" in text.lower():
            return (
                "Windows отклонила доступ к WinDivert. Запустите приложение "
                "от имени администратора и разрешите UAC."
            )
        if "The system cannot find the file" in text or "Не удается найти" in text:
            return (
                "Не найден драйвер WinDivert. Переустановите приложение из "
                "официального релиза."
            )
        return f"Движок остановлен: {text or exc.__class__.__name__}"

    def update_policy(self, include: frozenset[str], exclude: frozenset[str]) -> None:
        with self._lock:
            if self._config is None:
                return
            self._config = EngineConfig(
                profile_id=self._config.profile_id,
                profile_name=self._config.profile_name,
                split=self._config.split,
                block_quic=self._config.block_quic,
                mode=self._config.mode,
                include=include,
                exclude=exclude,
            )
            self._append_log_locked(
                "Списки обновлены: "
                f"{len(include)} доменов в обходе, {len(exclude)} в исключениях.",
                "system",
            )

    def _handle_packet(self, handle: Any, packet: Any) -> None:
        with self._lock:
            config = self._config
            self._stats["packets"] += 1
        if config is None:
            handle.send(packet)
            return
        udp = packet.udp
        if udp is not None:
            if config.block_quic and packet.dst_port == 443:
                with self._lock:
                    self._stats["quic_dropped"] += 1
                return
            handle.send(packet)
            return
        tcp = packet.tcp
        if tcp is None:
            handle.send(packet)
            return
        payload = packet.payload or b""
        if not payload:
            handle.send(packet)
            return

        host_info = extract_host(payload)
        host = host_info.host if host_info else ""
        if host and not domain_allowed(host, config):
            with self._lock:
                self._stats["passed"] += 1
            handle.send(packet)
            return
        if not host and config.mode == "list":
            with self._lock:
                self._stats["passed"] += 1
            handle.send(packet)
            return

        key = (
            packet.src_addr,
            packet.src_port,
            packet.dst_addr,
            packet.dst_port,
        )
        now = time.monotonic()
        with self._lock:
            self._purge_flows_locked(now)
            seen = self._flows.get(key)
            if host_info is None and seen is not None:
                self._stats["passed"] += 1
                handle.send(packet)
                return
            self._flows[key] = now

        position = split_position(payload, host_info, config.split)
        if position <= 0:
            handle.send(packet)
            return
        self._send_split(handle, packet, position)

    def _purge_flows_locked(self, now: float) -> None:
        if len(self._flows) <= _MAX_FLOWS:
            return
        cutoff = now - _FLOW_TTL
        for key, seen in list(self._flows.items()):
            if seen < cutoff:
                del self._flows[key]
        if len(self._flows) > _MAX_FLOWS:
            self._flows.clear()

    def _send_split(self, handle: Any, packet: Any, position: int) -> None:
        payload = packet.payload or b""
        if position <= 0 or position >= len(payload):
            handle.send(packet)
            return
        raw = packet.raw.tobytes()
        first = Packet(
            raw,
            interface=packet.interface,
            direction=Direction.OUTBOUND,
            timestamp=packet.timestamp,
            loopback=packet.loopback,
        )
        second = Packet(
            raw,
            interface=packet.interface,
            direction=Direction.OUTBOUND,
            timestamp=packet.timestamp,
            loopback=packet.loopback,
        )
        first.payload = payload[:position]
        second.payload = payload[position:]
        second.tcp.seq_num = (packet.tcp.seq_num + position) & 0xFFFFFFFF
        if first.ipv4 is not None and second.ipv4 is not None:
            ident = first.ipv4.ident
            first.ipv4.ident = ident
            second.ipv4.ident = (ident + 1) & 0xFFFF
        handle.send(first)
        handle.send(second)
        with self._lock:
            self._stats["split_packets"] += 1

    def stop(self, reason: str | None = None) -> dict[str, Any]:
        with self._lifecycle_lock:
            with self._lock:
                if not self._running:
                    return {
                        "ok": True,
                        "started": False,
                        "error": None,
                        "status": self.status(),
                    }
                self._stop_event.set()
                self._append_log_locked(reason or "Остановка обхода", "system")
                handle = self._handle
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    log.debug("WinDivert close failed", exc_info=True)
            thread = self._thread
            if thread is not None:
                thread.join(timeout=4.0)
            with self._lock:
                still_running = self._running
                if still_running:
                    self._last_error = "WinDivert не завершился за 4 секунды."
                    self._append_log_locked(self._last_error, "error")
                else:
                    self._last_error = None
            self._notify_state_changed()
            return {
                "ok": not still_running,
                "started": still_running,
                "error": self._last_error,
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
            log.exception("Engine shutdown failed")

    def _notify_state_changed(self) -> None:
        with self._lock:
            callback = self._on_state_change
        if callback:
            try:
                callback()
            except Exception:
                log.exception("Engine state callback failed")

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = self._running
            uptime = (
                int(time.time() - self._started_at)
                if running and self._started_at
                else 0
            )
            config = self._config
            active = dict(self._active_config) if running else {}
            return {
                "running": running,
                "pid": None,
                "uptime_seconds": max(0, uptime),
                "started_at": self._started_at if running else None,
                "last_exit_code": None,
                "last_error": self._last_error,
                "active_config": active,
                "command": [config.describe()] if config else [],
                "command_line": config.describe() if config else "",
                "executable": "встроенный движок",
                "engine": "native",
                "profile_id": config.profile_id if config else None,
                "profile_name": config.profile_name if config else None,
                "strategy": config.split if config else None,
                "block_quic": config.block_quic if config else None,
                "stats": dict(self._stats),
                "log_seq": self._next_seq - 1,
            }
