"""Build helper: validate the interpreter, stage native WebView2 data and
write release checksums.

Run by build.bat. This intentionally stays outside the application package.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "build_artifacts"
DIST = ROOT / "dist"


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def write_checksums() -> None:
    exe = DIST / "ZapretRU.exe"
    if not exe.is_file():
        fail(f"Не найден {exe}")
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    checksums = DIST / "SHA256SUMS.txt"
    checksums.write_text(f"{digest}  ZapretRU.exe\n", encoding="ascii", newline="\n")
    print(f"[SHA256] {digest}")
    print(f"[SHA256] {checksums}")


def main() -> None:
    if sys.version_info < (3, 11):
        fail("Требуется Python 3.11 или новее")
    if sys.maxsize <= 2**32:
        fail("Требуется 64-битный Python (x64)")

    try:
        import webview
    except ImportError:
        fail(
            "pywebview не установлен. Выполните: python -m pip install -r requirements.txt"
        )
    for module in ("nuitka", "pystray", "PIL"):
        try:
            __import__(module)
        except ImportError:
            fail(
                f"Модуль {module} не установлен. Выполните: python -m pip install -r requirements.txt"
            )

    source = (
        Path(webview.__file__).parent
        / "lib"
        / "runtimes"
        / "win-x64"
        / "native"
        / "WebView2Loader.dll"
    )
    if not source.is_file():
        fail(f"WebView2Loader.dll не найден: {source}")

    STAGE.mkdir(parents=True, exist_ok=True)
    target = STAGE / "WebView2Loader.dll"
    shutil.copy2(source, target)
    print(f"[OK] WebView2Loader: {source}")
    print(f"[OK] Stage: {target}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "checksums":
        write_checksums()
    else:
        main()
