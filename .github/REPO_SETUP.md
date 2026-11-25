# Repository setup

This file is a checklist for publishing the project. It is written in Russian
for the maintainer and is not used by the application.

**Status:** published at <https://github.com/GARAKIL/zapret-ru> with release
`v1.2.0`, topics, description and GitHub Pages landing page
<https://garakil.github.io/zapret-ru/>. Only the social preview upload remains
manual.

## Suggested repository name

`zapret-ru`

## About / description

> Zapret RU — self-contained Windows DPI bypass with its own WinDivert engine:
> SNI split, QUIC → TCP, large iOS-style UI, auto-selection. No winws, no ads,
> no telemetry.

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
sni
tls
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
  --description "Zapret RU — self-contained Windows DPI bypass with its own WinDivert engine: SNI split, QUIC to TCP, large iOS-style UI and auto-selection. No winws, no ads, no telemetry." `
  --add-topic zapret `
  --add-topic dpi-bypass `
  --add-topic anti-censorship `
  --add-topic windows `
  --add-topic russia `
  --add-topic tspu `
  --add-topic youtube `
  --add-topic discord `
  --add-topic quic `
  --add-topic sni `
  --add-topic tls `
  --add-topic windivert `
  --add-topic pywebview `
  --add-topic nuitka `
  --add-topic desync `
  --add-topic network
```

After pushing a tag, `.github/workflows/release.yml` builds the onefile exe and
attaches `ZapretRU.exe`, `SHA256SUMS.txt`, third-party notices and the license
archive to the GitHub Release.

## Social preview

Upload `docs/social-preview.png` in GitHub:
**Settings → General → Social preview → Edit → Upload an image**.

## Important

The executable bundles the official signed WinDivert driver and PyDivert from
their Python packages. Do not replace them with random DLLs from the internet.
The licenses and upstream source links are listed in `THIRD_PARTY_NOTICES.txt`
and `licenses/`. No zapret/winws binaries are used or distributed.
