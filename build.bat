@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   ZAPRET RU - native Windows build with Nuitka
echo ============================================================
echo.

if not exist "main.py" goto :missing_source

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not in PATH. Install 64-bit Python 3.11+.
    goto :error
)

python tools\build_prepare.py
if errorlevel 1 goto :error

set "WEBVIEW2_LOADER=build_artifacts\WebView2Loader.dll"
if not exist "%WEBVIEW2_LOADER%" (
    echo [ERROR] build_artifacts\WebView2Loader.dll was not staged.
    goto :error
)

if not exist "assets\icon.ico" (
    echo [ERROR] assets\icon.ico is missing.
    goto :error
)

if not exist "build_artifacts\WinDivert64.dll" (
    echo [ERROR] WinDivert64.dll was not staged.
    goto :error
)
if not exist "build_artifacts\WinDivert64.sys" (
    echo [ERROR] WinDivert64.sys was not staged.
    goto :error
)

echo [BUILD] Compiling Python to a native executable...
echo.

python -m nuitka ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-uac-admin ^
    --python-flag=no_docstrings,no_asserts ^
    --windows-icon-from-ico=assets\icon.ico ^
    --product-name="Zapret RU" ^
    --file-version=2.0.0.0 ^
    --product-version=2.0.0.0 ^
    --company-name="Zapret RU" ^
    --file-description="Zapret RU" ^
    --copyright="Built-in WinDivert engine. WinDivert/PyDivert are LGPL/GPL third-party components." ^
    --output-dir=dist ^
    --output-filename=ZapretRU.exe ^
    --remove-output ^
    --assume-yes-for-downloads ^
    --include-data-dir=ui=ui ^
    --include-data-dir=lists=lists ^
    --include-data-dir=assets=assets ^
    --include-data-files=presets.json=presets.json ^
    --include-package-data=webview ^
    --include-package-data=pythonnet ^
    --include-package-data=clr_loader ^
    --include-package-data=pydivert ^
    --include-data-files="%WEBVIEW2_LOADER%=WebView2Loader.dll" ^
    --include-data-files="build_artifacts\WinDivert64.dll=pydivert/windivert_dll/WinDivert64.dll" ^
    --include-data-files="build_artifacts\WinDivert64.sys=pydivert/windivert_dll/WinDivert64.sys" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Nuitka failed. Review the output above.
    goto :error
)

if not exist "dist\ZapretRU.exe" (
    echo [ERROR] dist\ZapretRU.exe was not produced.
    goto :error
)

if exist "dist\bin" rmdir /s /q "dist\bin"
if exist "README.md" copy /Y "README.md" "dist\README.md" >nul
if exist "LICENSE" copy /Y "LICENSE" "dist\LICENSE.txt" >nul
if exist "THIRD_PARTY_NOTICES.txt" copy /Y "THIRD_PARTY_NOTICES.txt" "dist\THIRD_PARTY_NOTICES.txt" >nul
if exist "ui\fonts\Inter-LICENSE.txt" copy /Y "ui\fonts\Inter-LICENSE.txt" "dist\INTER-LICENSE.txt" >nul
if exist "licenses" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'licenses\*' -DestinationPath 'dist\THIRD_PARTY_LICENSES.zip' -Force" >nul
)
python tools\build_prepare.py checksums
if errorlevel 1 (
    echo [ERROR] Failed to write SHA256SUMS.txt.
    goto :error
)
if exist "build_artifacts" rmdir /s /q "build_artifacts"

echo.
echo ============================================================
echo   Build complete.
echo   Executable: dist\ZapretRU.exe
echo.
echo   Engine: built-in WinDivert packet filter.
echo   No external winws.exe or zapret binaries are required.
echo.
echo   Editable data is stored in:
echo   %%LOCALAPPDATA%%\ZapretRU
echo ============================================================
echo.
if /i not "%~1"=="--no-pause" pause
exit /b 0

:missing_source
echo [ERROR] Run build.bat from the project root.
goto :error

:error
echo.
if /i not "%~1"=="--no-pause" pause
exit /b 1
