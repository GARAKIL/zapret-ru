# Screenshots

These images are generated from `tests/ui_preview.html` at 1120×800 with the
mock API. The counters in the settings screenshot are demo values, not real
telemetry or global user statistics. Zapret RU has no global counter and never
sends usage data anywhere.

To regenerate them locally:

```powershell
python -m http.server 8765 --bind 127.0.0.1
# open http://127.0.0.1:8765/tests/ui_preview.html
```
