# Development

## Architecture at a glance

- Python backend handles BlueZ discovery, RFCOMM transport, protocol framing/parsing, profile logic, typed API, and session ownership.
- Service/controller layers serialize operations and connection lifecycle behavior.
- Frontend bridge emits versioned, JSON-safe payloads for UI integration.
- QML handles presentation and bridge interaction, not protocol logic.

## Key docs

- `/docs/backend-api.md`
- `/docs/backend-cli.md`
- `/docs/frontend-bridge.md`
- `/docs/protocols/OPOv1.md`
- `/docs/omarchy-integration.md`

## Local validation commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tests/run_qml_hover.py
omarchy plugin validate .
```

## Contribution notes

- Keep privacy boundaries intact in diagnostics/output
- Avoid leaking Bluetooth addresses or raw packet content
- Preserve explicit compatibility labeling and evidence standards
- Follow contribution guidance in `/CONTRIBUTING.md`
