# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.3.x | yes |
| < 1.2 | no |

## Report a vulnerability

Do not publish exploit details in a public issue. Use **GitHub → Security → Report a vulnerability** in this repository. Include reproduction steps, the affected version, and the Windows build number. Do not include live credentials or personal data.

## What Zapret RU is

Zapret RU is a self-contained Windows DPI-evasion client. Its own packet engine
uses the signed [WinDivert](https://github.com/basil00/WinDivert) driver through
the [PyDivert](https://github.com/ffalcinelli/pydivert) binding. It does **not**
start `winws.exe`, `cygwin1.dll`, zapret `.bin` payloads or any other bypass
process. It is not a VPN, does not proxy traffic, and cannot guarantee bypass on
every provider or every destination.

The application has **no telemetry, no ads, no auto-downloads and no embedded
remote code**. The only outbound requests made by the application itself are the
explicit connectivity checks to YouTube, Discord and Cloudflare. They are
triggered by the user: by starting protection (one automatic check) or by
pressing the check button. There are no background probes.

## Threat model

- The app must run as administrator because WinDivert needs elevated packet access. Any local administrator can inspect and modify an unsigned local executable.
- Nuitka native compilation reduces casual Python source extraction. It is **not** DRM, cryptographic protection, or a guarantee against reverse engineering. No client-side anti-tamper can be made unbreakable.
- Trust is based on the source repository, reproducible build steps, reviewable profile data and SHA-256 release checksums.
- WinDivert and PyDivert are third-party components under LGPL/GPL. Their
  signatures, driver behavior and trust model are outside the control of this
  project. See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
- The release is unsigned by an Authenticode certificate. SmartScreen may warn.

## Supply-chain guidance

- Download release binaries only from the official repository's Releases page.
- Verify `SHA256SUMS.txt` from the same release:

```powershell
Get-FileHash .\ZapretRU.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

- Do not use random repacks of the executable. The bundled driver is the official
  signed WinDivert 2.2 binary from PyDivert 4.0.1.
- Do not disable security software permanently. Add an exclusion only if you
  understand the risk of a kernel packet driver.

## Application hardening in this repository

- Profiles are data-only: `split` is `"sni"` or an integer 1–512, and
  `block_quic` is a boolean. Arbitrary commands, paths and shell fragments are
  rejected by the preset parser.
- No child process is started by the application. The engine runs in-process.
- Packet processing is limited to outbound TCP 80/443 and, optionally, UDP 443.
  Every other packet is reinjected unchanged.
- Domain policy is checked against the include/exclude lists before a packet is
  split; unknown hosts in list mode pass through untouched.
- File writes are limited to the two known list files, `presets.json` migration,
  and validated settings/usage JSON files.
- The UI uses a restrictive CSP. `'unsafe-eval'` is required by PyWebView's local
  JS bridge; no remote resources are loaded.
- External links are allow-listed.
- All parsed user-visible text is inserted with `textContent`, not HTML.
- CI runs unit tests and a onefile build; tagged releases publish a SHA-256
  checksum. CodeQL and Dependabot are enabled.
- The hidden `--engine-smoke` mode is only used by maintainers to validate a
  compiled binary; it writes a local JSON report and exits.

## Not in scope

- The effectiveness of a DPI strategy against a particular provider.
- WinDivert driver vulnerabilities.
- Third-party copies or modified builds of Zapret RU.
- People with local administrator access modifying their own installation.
- ISP blocking by IP, DNS manipulation, ECH, or UDP voice/game protocols.
