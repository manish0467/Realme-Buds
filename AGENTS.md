# Developer & AI Agent Context (`AGENTS.md`)

This file provides architectural orientation, safety invariants, testing commands, and project conventions for AI agents and human developers maintaining **`realme-buds.control`**.

---

## 1. Project Mission & Summary

* **Project**: `realme-buds.control`
* **Type**: Native desktop status bar plugin and Linux backend service for Omarchy Linux (Hyprland + Quickshell).
* **Current Release**: `v0.2.1`
* **Target Hardware**: Primary reference baseline is **realme Buds T310** (`063C12`, `84:9D:4B:82:AD:80`), with extensible modular support for OnePlus and OPPO OPO-protocol family earbuds.
* **Core Philosophy**: Zero external PyPI dependencies (pure Python standard library + BlueZ D-Bus/RFCOMM), strict hearing safety, and rock-solid desktop stability.

---

## 2. Critical Safety & Architectural Invariants (DO NOT BREAK)

### ⚠️ Invariant 1: Config Storage Path (Prevent Shell Reload Loops)
* **Rule**: User mutable state files (`custom_eq.json`, `gestures.json`) **MUST NEVER** be stored inside the plugin directory (`~/.config/omarchy/plugins/realme-buds.control/`).
* **Why**: Omarchy runs an inotify watcher (`inotifywait`) across `~/.config/omarchy/plugins/`. Writing any file inside that tree forces an immediate full reload of the entire desktop top bar.
* **Standard Path**: Use `_BASE_CONFIG_DIR / "omarchy" / "realme-buds"` (resolving `$XDG_CONFIG_HOME` falling back to `~/.config/omarchy/realme-buds/`).
* **Migration**: Always preserve the automatic legacy migration in `custom_eq.py` and `gestures.py` to move older files from the plugin directory into the safe location.

### ⚠️ Invariant 2: Acoustic Ear Safety Lock (Hearing Protection)
* **Rule**: The "Find My Buds" acoustic locator plays high-penetration sweeps (2.2 kHz → 3.8 kHz) at maximum volume. It **MUST NOT** be triggered with a single accidental click.
* **UI Invariant**: The panel in `BarWidget.qml` requires the user to explicitly type `"realme"` to unlock the ringing action.
* **Volume Ramp Invariant**: `locator.py` **MUST** retain the 2.5-second gradual volume ramp (starting at 15% volume and rising smoothly to 100%) so that if someone accidentally wears the earbud, they get an immediate gentle warning reflex window before full volume is reached.
* **CLI Invariant**: `./realme-buds find` requires typing `"realme"` in interactive terminals unless bypassed explicitly with `-y`, `--yes`, or `--force`.

### ⚠️ Invariant 3: Zero External Dependencies
* **Rule**: Do **NOT** add PyPI package dependencies.
* **Allowed Stack**: Python 3.11+ standard library, system `python-dbus`, and BlueZ (`bluetoothctl` / RFCOMM sockets).

### ⚠️ Invariant 4: Unit Test Config Isolation
* **Rule**: Unit tests must **never** touch the live user config directory.
* **Pattern**: Always patch `CONFIG_PATH` to a `tempfile.TemporaryDirectory` in `setUp()` and clean it up in `tearDown()` (see `tests/test_bridge.py`).

---

## 3. Architecture & File Layout

```text
├── BarWidget.qml            # Main Omarchy status bar widget and expanded popup panel (Qt 6 / Quickshell)
├── Service.qml              # Background Quickshell process runner hosting realme-buds-bridge
├── BarModel.js              # Pure data formatting functions for UI representation
├── BridgeModel.js           # Bridge state reducer and error handler
├── manifest.json            # Omarchy plugin manifest metadata
├── pyproject.toml           # Python package build configuration
├── realme-buds              # CLI entrypoint executable
├── realme-buds-bridge       # Newline-delimited JSON IPC bridge runner
├── src/realme_buds/         # Core Python backend package
│   ├── bridge.py            # BudsFrontendBridge: routes IPC commands and dispatches snapshots
│   ├── bridge_host.py       # StdIO newline-delimited JSON process host
│   ├── controller.py        # BudsController: high-level state coordinator
│   ├── session.py           # OpoSession: RFCOMM socket communication and packet framing
│   ├── profiles.py          # DeviceRegistry and DeviceProfile loader
│   ├── devices/             # Declarative device profile JSON definitions (e.g. 063C12.json)
│   ├── custom_eq.py         # CustomEqStore: 6-band gains persistence and DSP curve mapping
│   ├── gestures.py          # GestureStore: touch tap remapping and OPO gesture frames
│   ├── locator.py           # AcousticLocator: acoustic chime synthesis and audio sink routing
│   ├── notifications.py     # BatteryNotificationPolicy: desktop low battery alert debouncing
│   ├── mpris.py             # MprisManager: native D-Bus MPRIS2 media auto-pause and resume
│   └── cli.py               # Standalone command-line interface
├── tests/                   # Complete automated test suite
│   ├── test_bridge.py       # Bridge IPC tests
│   ├── test_locator.py      # Locator waveform and safety confirmation tests
│   ├── test_custom_eq.py    # Custom EQ persistence and curve mapping tests
│   ├── test_gestures.py     # Touch gesture encoding and decoding tests
│   ├── run_qml_hover.py     # Headless Qt 6 offscreen QML widget test runner
│   └── qml/                 # Mock QML imports and test cases
└── wiki/                    # User documentation and CLI cheat sheets
```

---

## 4. Key Protocol Framing Reference (OPOv1 / OPOv2)

* **Transport**: Bluetooth Classic RFCOMM channel 1 (bound to MAC address).
* **Wire Format**:
  - Magic bytes: `0xAA, 0x55` or OPO header framing.
  - Length byte, command byte, sequence counter, payload, and CRC / checksum byte.
* **Key Command Codes**:
  - `0x0108`: Query Gestures (`QUERY_GESTURE`) / `0x8108`: Response.
  - `0x0407`: Set Gesture (`SET_GESTURE`).
  - `0x010F`: Query Active EQ Preset (`QUERY_EQ`) / `0x810F`: Response.
  - `0x0403`: Set Feature Switch (`SET_FEATURE`) / `0x8403`: Response.
    - Feature `0x04`: In-Ear Wear Detection toggle.
    - Feature `0x06` / `0x28`: Low Latency Game Mode (45ms).
    - Feature `0x11`: Dual-Device / Multipoint toggle.
* **Firmware Note on EQ**:
  - `QUERY_EQ_ALL` (`0x0122`) is ignored by realme Buds T310 firmware. Do not send `0x0122` when `supports_custom` is `false` in the device profile to avoid RFCOMM timeout penalties.

---

## 5. Verification Commands & Quality Gates

Run these commands before committing any changes. All gates must pass with **100% success rate**:

```bash
# 1. Run full Python unit test suite (212+ tests)
PYTHONPATH=src python3 -m unittest discover tests

# 2. Run headless Qt 6 offscreen QML test suite (8 tests)
python3 tests/run_qml_hover.py

# 3. Run QML static linter (must produce 0 warnings)
qmllint BarWidget.qml Service.qml

# 4. Run Omarchy plugin manifest validator
omarchy plugin validate .

# 5. Run runtime dependency check
python3 scripts/check_dependencies.py
```

---

## 6. Release & Version Synchronization Checklist

When releasing a new version (`X.Y.Z`), you must keep all 5 version declarations in sync:

1. [`manifest.json`](manifest.json) — `"version": "X.Y.Z"`
2. [`pyproject.toml`](pyproject.toml) — `version = "X.Y.Z"`
3. [`src/realme_buds/__init__.py`](src/realme_buds/__init__.py) — `__version__ = "X.Y.Z"`
4. [`README.md`](README.md) — `**Status: X.Y.Z.**`
5. [`CHANGELOG.md`](CHANGELOG.md) — Add `## [X.Y.Z] - YYYY-MM-DD` section following Keep a Changelog.

**Build & Release Steps**:
```bash
# Commit and tag
git commit -am "chore: release vX.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z: summary of changes"
git push origin main && git push origin vX.Y.Z

# Compile distribution packages
python3 -m pip wheel --no-deps -w dist .
git archive --format=zip --prefix=realme-buds.control/ -o dist/realme-buds.control-vX.Y.Z.zip vX.Y.Z
git archive --format=tar.gz --prefix=realme-buds.control/ -o dist/realme-buds.control-vX.Y.Z.tar.gz vX.Y.Z

# Publish GitHub release
gh release create vX.Y.Z dist/*X.Y.Z* --title "vX.Y.Z — Title" --notes "Release notes"

# Submit Omarchy Marketplace verification update
# Open issue on omacom/omarchy-plugin-marketplace with template verify-plugin.yml
```

---

## 7. Future Roadmap & Backlog

1. **Context-Aware Automations**: Hyprland window hooks (`hyprctl activewindow`) for automatic Game Mode on games and Transparency/Mic on video conference apps.
2. **Push-to-Talk / Mic Mute**: Map earbud gesture (e.g. Triple Tap Left) to system microphone mute via `wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle`.
3. **PipeWire Parametric DSP EQ**: Optional PipeWire virtual sink filter-chain node for audiophile 10-band parametric equalizing.
4. **Rust Native Daemon Rewrite**: Replace `realme-buds-bridge` with a zero-runtime static binary (`bluer` + `tokio`) under 5 MB RAM footprint.
