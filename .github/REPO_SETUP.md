# Repository setup

This file is a checklist for publishing the project. It is written in Russian
for the maintainer and is not used by the application.

**Status:** published at <https://github.com/GARAKIL/zapret-ru> with release
`v1.1.0`, topics and description. Only the social preview upload remains manual.

## Suggested repository name

`zapret-ru`

## About / description

> Zapret RU — открытый Windows-лаунчер для оригинального bol-van/zapret: YouTube,
> Discord, QUIC, автоподбор стратегий, логи и трей. Без рекламы и телеметрии.

## Suggested topics

```text
zapret
dpi-bypass
anti-censorship
windows
russia
tspu
youtube
discord
quic
windivert
pywebview
nuitka
desync
network
gui
```

## First publication

```powershell
# once
gh auth login
gh auth status

# create a public repository and push the current branch
gh repo create zapret-ru --public --source . --remote origin --push

# apply metadata
gh repo edit zapret-ru `
  --description "Zapret RU — open-source Windows launcher for bol-van/zapret: YouTube, Discord and QUIC DPI bypass with presets, live logs, tray and auto-selection. No ads, no telemetry." `
  --add-topic zapret `
  --add-topic dpi-bypass `
  --add-topic anti-censorship `
  --add-topic windows `
  --add-topic russia `
  --add-topic tspu `
  --add-topic youtube `
  --add-topic discord `
  --add-topic quic `
  --add-topic windivert `
  --add-topic pywebview `
  --add-topic nuitka `
  --add-topic desync `
  --add-topic network
```

After pushing a tag, `.github/workflows/release.yml` builds the onefile exe and
attaches `ZapretRU.exe` plus `SHA256SUMS.txt` to the GitHub Release.

## Social preview

Upload `docs/social-preview.png` in GitHub:
**Settings → General → Social preview → Edit → Upload an image**.

## Important

Do not add zapret binaries (`winws.exe`, WinDivert, `.bin` payloads) to this
repository unless you have checked their licenses and source. The launcher
intentionally keeps them outside the repository. The release executable alone
will show a clear missing-files message until the user copies official zapret
components into `bin`.
