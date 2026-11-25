# Contributing

Thanks for helping. This project is intentionally small, auditable and ad-free.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python main.py
```

The built-in engine needs administrator rights because WinDivert is a kernel
packet driver. Tests and UI development work without starting the engine.
`python main.py --engine-smoke` is a hidden maintainer check that writes
`%TEMP%\zapretru-engine-smoke.json`.

## Before opening a pull request

```powershell
python -m unittest discover -s tests -v
python -m compileall -q core main.py tools tests
node --check ui/app.js
```

- Keep the main window at 1120×800 unless the change explicitly discusses layout.
- Do not add telemetry, ads, auto-downloads, third-party JavaScript, or remote fonts.
- Do not add shell execution or arbitrary filesystem APIs to the PyWebView bridge.
- Engine profiles stay data-driven in `presets.json` (schema 2).
- Packet parsing and splitting must remain bounded and defensive; malformed TLS
  or HTTP must pass through unchanged.
- Explain provider-specific behaviour and include logs with personal data removed.
- Use English identifiers and Russian user-facing text.

## Engine contributions

Describe the exact strategy, the Windows build, the provider type and the sites
tested. Do not claim that one strategy works universally. New strategies must
reject arbitrary commands and must not weaken the include/exclude policy.

## Security

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Third-party
licenses and source links are listed in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
