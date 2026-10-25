# Getting Started

## Requirements

- Omarchy with Quickshell/Quattro shell modules (`qs.Ui`, `qs.Commons`)
- Python 3.11+ (project tested with newer versions)
- `python-dbus`
- BlueZ service running

From the repository root:

```bash
python3 scripts/check_dependencies.py
systemctl is-active bluetooth
```

## Install

```bash
omarchy plugin add https://github.com/manish0467/Realme-Buds.git realme-buds.control
python3 "$HOME/.config/omarchy/plugins/realme-buds.control/scripts/check_dependencies.py"
omarchy plugin enable realme-buds.control --section right
```

If prompted to enable immediately, run the dependency check first.

## First use

1. Pair and connect earbuds from Omarchy Bluetooth settings.
2. Keep only one compatible realme device connected for bar-widget usage.
3. Hover the icon for battery visibility, click expanded widget for controls.

## Safe CLI coexistence rule

Disable the plugin before running CLI commands that query or control earbuds, then re-enable afterward:

```bash
omarchy plugin disable realme-buds.control
# run CLI commands
omarchy plugin enable realme-buds.control --section right
```

## Remove

```bash
omarchy plugin disable realme-buds.control
omarchy plugin remove realme-buds.control
```
