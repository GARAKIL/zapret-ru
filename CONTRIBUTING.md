# Contributing

Thanks for helping. This project is intentionally small, auditable and ad-free.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Copy a valid `bin/` from an official zapret Windows distribution before trying to start the bypass. Tests and UI development do not need actual `winws.exe`.

## Before opening a pull request

```powershell
python -m unittest discover -s tests -v
python -m compileall -q core main.py tools tests
node --check ui/app.js
```

- Keep the UI at 440×620 unless the change explicitly discusses layout.
- Do not add telemetry, ads, auto-downloads, third-party JavaScript, or remote fonts.
- Do not add shell execution or arbitrary filesystem APIs to the PyWebView bridge.
- Presets must stay data-driven in `presets.json`.
- Explain provider-specific behaviour and include logs with personal data removed.
- Use English identifiers and Russian user-facing text.

## Preset contributions

Use synthetic descriptions and provider-neutral names. Do not claim that one strategy works universally. Include the exact zapret/winws version tested and confirmation that the syntax uses documented options.

## Security

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability.
