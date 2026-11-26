param(
    [string]$Repo = "zapret-ru",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$description = "Zapret RU - self-contained Windows DPI bypass with its own WinDivert engine: SNI split, QUIC to TCP, large iOS-style UI and auto-selection. No winws, no ads, no telemetry."
$topics = @(
    "zapret", "dpi-bypass", "anti-censorship", "windows", "russia", "tspu",
    "youtube", "discord", "quic", "sni", "tls", "windivert", "pywebview",
    "nuitka", "desync", "network", "gui"
)

foreach ($tool in @("git", "gh")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Не найден $tool. Установите Git и GitHub CLI."
    }
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "Сначала выполните: gh auth login"
}

if (-not (Test-Path ".git")) {
    git init -b main
}

git add .
if (git diff --cached --quiet) {
    Write-Host "[OK] Нет изменений для коммита."
} else {
    git commit -m "release: Zapret RU 2.0.0"
}

if (-not (git tag --list "v2.0.0")) {
    git tag -a "v2.0.0" -m "Zapret RU 2.0.0"
}

$hasOrigin = (git remote 2>$null) -contains "origin"
if (-not $hasOrigin) {
    $visibilityFlag = "--$Visibility"
    gh repo create $Repo $visibilityFlag --source . --remote origin --push
} else {
    git push -u origin main
}
git push origin --tags

$owner = gh api user --jq .login
$fullName = "$owner/$Repo"
gh repo edit $fullName --description $description
foreach ($topic in $topics) {
    gh repo edit $fullName --add-topic $topic
}

if (Test-Path "dist\ZapretRU.exe") {
    $hash = (Get-FileHash "dist\ZapretRU.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  ZapretRU.exe" | Set-Content "dist\SHA256SUMS.txt" -Encoding ascii
}

Write-Host ""
Write-Host "Репозиторий: https://github.com/$fullName"
Write-Host "Тема: DPI bypass Windows"
Write-Host "Теги: $($topics -join ', ')"
Write-Host "Release workflow запустится после пуша тега v2.0.0."
Write-Host "Загрузите docs/social-preview.png в Settings -> Social preview."
