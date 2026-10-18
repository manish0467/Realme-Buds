# Troubleshooting

## Widget shows disconnected

- Connect earbuds in Bluetooth settings
- Ensure Bluetooth service is active
- Keep one compatible device connected for bar usage

## CLI or controls fail with busy channel

Another process is using the single control channel:
- Disable the Omarchy plugin before CLI usage
- Close other earbud-control tools

## ANC mode change does not apply

- Remove earbuds from case and wear them
- Retry from panel or CLI
- Use status query to verify actual state after change

## Case battery missing

Some responses omit case battery details. The UI hides unavailable fields.

## Plugin fails to load

- Validate plugin directory layout
- Check shell/plugin logs
- Re-export to a unique source path during development if QML URL caching interferes

## Missing Python D-Bus binding

Use system Python with `python-dbus`. Virtual environments may not expose the system binding.

## Still stuck?

Generate a diagnostics/compatibility report and open an issue with the template:

`https://github.com/Alenbosh/Realme-Buds/issues/new?template=compatibility.md`
