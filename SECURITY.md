# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.1.x | yes |
| < 1.1 | no |

## Report a vulnerability

Do not publish exploit details in a public issue. Use **GitHub → Security → Report a vulnerability** in this repository. Include reproduction steps, the affected version, and the Windows build number. Do not include live credentials or personal data.

## What Zapret RU is

Zapret RU is an elevated local launcher around the third-party `winws.exe` from [bol-van/zapret](https://github.com/bol-van/zapret). It modifies network packets through WinDivert. It is not a VPN, does not proxy traffic, and cannot guarantee bypass on every provider or every destination.

The launcher has **no telemetry, no ads, no auto-downloads and no embedded remote code**. The only outbound requests made by the application itself are the explicit connectivity checks to YouTube, Discord and Cloudflare in the diagnostics card.

## Threat model

- The app must run as administrator because WinDivert needs elevated packet access. Any local administrator can inspect and modify an unsigned local executable.
- Nuitka native compilation reduces casual Python source extraction. It is **not** DRM, cryptographic protection, or a guarantee against reverse engineering. No client-side anti-tamper can be made unbreakable.
- Trust is based on the source repository, reproducible build steps, reviewable configuration and SHA-256 release checksums.
- The upstream `winws.exe`, WinDivert and `.bin` payloads are separate third-party components. Their signatures and trust model are outside the control of this project.

## Supply-chain guidance

- Download release binaries only from the official repository's Releases page.
- Verify `SHA256SUMS.txt` from the same release:

```powershell
Get-FileHash .\ZapretRU.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

- Use only official zapret builds for `bin/`. Random repacks may contain malware.
- The current public build is unsigned. Windows SmartScreen or antivirus software may warn about WinDivert and onefile executables. Do not disable security software permanently; add an exclusion only if you understand the risk.

## Application hardening in this repository

- Preset arguments are validated: arbitrary `--new`, `--filter-*`, `--wf-*`, `--hostlist*` and `--ipset*` options are rejected by the generator.
- Child processes are started with an argument list, never through a shell.
- `winws.exe` is stopped by the exact PID owned by this launcher, with `taskkill /F /T` as a fallback. Other `winws.exe` processes are never killed by name.
- File writes are limited to the two known list files and validated settings/usage JSON files.
- The UI uses a restrictive CSP. `'unsafe-eval'` is required by PyWebView's local JS bridge; no remote resources are loaded.
- External links are allow-listed.
- All parsed user-visible text is inserted with `textContent`, not HTML.
- CI runs unit tests and a onefile build; tagged releases publish a SHA-256 checksum.

## Not in scope

- The effectiveness of a DPI strategy against a particular provider.
- WinDivert driver vulnerabilities.
- Third-party copies of zapret.
- People with local administrator access modifying their own installation.
