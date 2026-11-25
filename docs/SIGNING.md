# Code signing (optional)

Public builds are currently unsigned. Nuitka compilation and SHA-256 checksums
improve reviewability but do not replace Authenticode. This guide is for the
maintainer if a certificate becomes available.

## Requirements

- A trusted Authenticode code-signing certificate (EV or OV).
- Windows SDK `signtool.exe`.
- The certificate private key must never be committed to this repository.

## Sign

```powershell
$exe = "dist\ZapretRU.exe"

signtool sign `
  /fd SHA256 `
  /tr http://timestamp.digicert.com `
  /td SHA256 `
  /f "C:\secure\codesign.pfx" `
  /p "<password-from-secret-store>" `
  $exe

signtool verify /pa /v $exe
```

Use a trusted RFC 3161 timestamp service. Without a timestamp, the signature
expires when the certificate expires.

## Recompute the release checksum

```powershell
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  ZapretRU.exe" | Set-Content dist\SHA256SUMS.txt -Encoding ascii
```

Attach the signed exe and the new checksum to the GitHub Release. Never reuse a
checksum from an earlier build.

## CI secrets

If signing is automated later, keep the certificate in GitHub Actions Secrets as
base64 and inject it only into the release job. Do not print the certificate or
password, and do not build untrusted pull requests with signing secrets.

## What signing does and does not do

- It confirms the publisher identity and detects tampering of the signed file.
- It does not make DPI bypass work better.
- It does not make reverse engineering impossible.
- It does not guarantee that Microsoft SmartScreen will immediately trust a new
  certificate.
