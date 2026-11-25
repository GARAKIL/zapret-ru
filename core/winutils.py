"""Small, dependency-free Windows integration helpers."""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

_MB_ICONERROR = 0x00000010
_MB_ICONINFORMATION = 0x00000040
_MB_TOPMOST = 0x00040000
_MB_SETFOREGROUND = 0x00010000

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def message_box(title: str, text: str, *, error: bool = False) -> None:
    flags = (
        _MB_TOPMOST
        | _MB_SETFOREGROUND
        | (_MB_ICONERROR if error else _MB_ICONINFORMATION)
    )
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception:
        pass


def set_app_user_model_id(app_id: str) -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def open_path(path: Path | str) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    try:
        if target.is_dir():
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            os.startfile(str(target))  # type: ignore[attr-defined]
        return True
    except OSError:
        return False


def reveal_in_explorer(path: Path | str) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    try:
        subprocess.Popen(
            ["explorer.exe", "/select," + str(target)],
            close_fds=True,
        )
        return True
    except OSError:
        return False


def copy_text_to_clipboard(text: str) -> bool:
    if not isinstance(text, str) or len(text) > 2_000_000:
        return False
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    data = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        return False

    opened = False
    for _ in range(6):
        if user32.OpenClipboard(None):
            opened = True
            break
        # Clipboard can be briefly held by another application.
        import time

        time.sleep(0.04)

    if not opened:
        kernel32.GlobalFree(handle)
        return False

    try:
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return False
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        user32.EmptyClipboard()
        if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
            return False
        # Ownership of the global memory block passed to the clipboard.
        handle = None
        return True
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)
