# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-18

### Added (Day 1 - Completed ✅)
- ANC Cycle CLI command (`./realme-buds anc cycle`) with automatic fast Omarchy shell session reuse and standalone RFCOMM fallback.
- Quickshell IPC endpoint `cycleAnc` on `realme-buds.control` for sub-200ms noise control toggling.
- Hyprland default hotkey binding (`SUPER + ALT + A`) configured in `~/.config/hypr/bindings.lua`.
- `cycle_anc` and `cycle_anc_with_snapshot` methods on `BudsController` and `BudsFrontendBridge`.

### Added (Day 2 - Completed ✅)
- 45ms Low Latency Game Mode support for realme Buds T310 (`063C12.json`).
- CLI commands: `./realme-buds game status`, `./realme-buds game on`, `./realme-buds game off`, and `./realme-buds game toggle`.
- Dedicated "Special Features" section with interactive Game Mode button (`󰊴  Game Mode (45ms)`) in `BarWidget.qml`.
- Quickshell IPC endpoints `setGameMode` and `toggleGameMode` on `realme-buds.control`.
- Global Hyprland hotkey binding (`SUPER + ALT + G`) in `~/.config/hypr/bindings.lua`.

### Added (Day 3 - Completed ✅)
- Low Battery Desktop Notifications policy (`BatteryNotificationPolicy` in `src/realme_buds/notifications.py`) with 20% warning and 10% critical thresholds.
- Anti-spam guard: alerts fire strictly once per discharge cycle and automatically reset when charging begins or battery recovers above 25%.
- Notification coalescing: combines simultaneous left and right earbud low-battery alerts into a single unified desktop notification.
- Discrete monitoring for left earbud, right earbud, charging case, and single-battery fallback devices.
- Integration with Omarchy desktop notification server (`notify-send` / `omarchy notification send`).
- CLI commands: `./realme-buds notify status`, `./realme-buds notify on`, `./realme-buds notify off`, and `./realme-buds notify test`.
- Quickshell IPC endpoints `testNotification`, `setNotifications`, and `notifyStatus`.
- Interactive UI toggle button (`󰂃  Battery Alerts (20% & 10%)`) in the panel.

### Added (Day 4 - Completed ✅)
- In-ear capacitive wear detection support for realme Buds T310 (`063C12.json` with Feature `0x04`).
- Native desktop MPRIS media auto-pause and auto-resume hook (`MprisManager` in `src/realme_buds/mpris.py`):
  - Automatically queries playing media players on `org.mpris.MediaPlayer2.*` via user session D-Bus without external binaries.
  - Pauses playing media when earbuds are placed in charging case or removed.
  - Caches paused player bus names and selectively resumes only previously playing players when earbuds are re-inserted.
- Integrated wear-transition detection tracking charging state changes in `BudsFrontendBridge`.
- CLI commands: `./realme-buds wear status`, `./realme-buds wear on`, `./realme-buds wear off`, `./realme-buds wear toggle`, `./realme-buds wear mpris-on`, `./realme-buds wear mpris-off`, and `./realme-buds wear mpris-status`.
- Quickshell IPC endpoints `setWearDetection`, `wearStatus`, `setMprisHook`, and `mprisHookStatus`.
- Interactive UI toggle buttons in `BarWidget.qml` panel:
  - `󰋋  In-Ear Detection` (enables/disables capacitive wear sensing on firmware).
  - `󰐎  Auto-Pause Media` (enables/disables desktop MPRIS pause/resume hook).

### Added (Day 5 - Completed ✅)
- Dual-Device / Multipoint connection support for realme Buds T310 (`063C12.json` with Feature `0x11` / `FEATURE_MULTIPOINT` via `0x0403` framing).
- Allows simultaneous connection to PC and smartphone with automatic audio handoff.
- CLI commands: `./realme-buds multipoint status`, `./realme-buds multipoint on`, `./realme-buds multipoint off`, `./realme-buds multipoint toggle` (with `./realme-buds dual` shorthand alias).
- Quickshell IPC endpoints `setMultipoint`, `toggleMultipoint`, and `multipointStatus`.
- Interactive UI toggle button in `BarWidget.qml` panel:
  - `󰂌  Dual Connection` (toggles dual-device multipoint pairing on firmware).

### Added (Day 6 - Completed ✅)
- "Find My Buds" acoustic locator chime engine (`AcousticLocator` in `src/realme_buds/locator.py`):
  - In-memory synthesis of high-penetration acoustic chirps (2.2 kHz → 3.8 kHz frequency sweep) without external Python libraries.
  - Channel-specific audio isolation allowing independent ringing of Left earbud only, Right earbud only, or Both.
  - Dynamic discovery and targeted PipeWire / PulseAudio routing directly to the realme Buds T310 Bluetooth audio sink (`bluez_output.84_9D_4B_82_AD_80.*`).
  - Auto-stop safety timeout (default 30 seconds) and instantaneous stop cancellation.
- Hearing safety gate in `BarWidget.qml` panel:
  - Clear user warning: *"⚠️ Earbuds play a loud sound. Do NOT wear them!"*
  - Independent trigger buttons (`Left`, `Right`, `Both`) and immediate `󰓛  Stop Ringing` button.
- CLI commands: `./realme-buds find status`, `./realme-buds find left`, `./realme-buds find right`, `./realme-buds find both`, and `./realme-buds find stop` (with `./realme-buds ring` shorthand alias).
- Quickshell IPC endpoints `ringBuds`, `stopRingBuds`, and `ringStatus`.

### Added (Day 7 - Completed ✅)
- Touch Gesture Remapping for physical earbud tap controls (`src/realme_buds/gestures.py`):
  - Decoded native OPO `0x0108` gesture query and `0x0407` gesture write frames.
  - Independent customization of Left and Right earbud tap triggers:
    - Double Tap (`double_tap`)
    - Triple Tap (`triple_tap`)
    - Touch & Hold / Long Press (`long_press`)
  - Supported action mappings: Play/Pause, Next Track, Previous Track, Voice Assistant, Game Mode Toggle, Noise Control Cycle, Volume Up, Volume Down, Disabled.
  - Long-press noise control cycle customization: option to cycle exclusively between `ANC ↔ Transparency` (skipping Off) or all 3 modes (`ANC ↔ Transparency ↔ Off`).
  - Persistent gesture configuration (`GestureStore`) across earbud reconnects and reboots.
- UI Gesture configuration card in `BarWidget.qml`:
  - Visual selector button (`󰈈  Touch Gestures`).
  - Dropdown ComboBoxes for Double Tap, Triple Tap, and Touch & Hold for Left and Right earbuds.
  - Interactive segmented toggle for Long-Press Noise Modes (`ANC ↔ Transp` vs `+ Off (All 3)`).
- CLI commands:
  - `./realme-buds gesture status` (or `./realme-buds touch status`)
  - `./realme-buds gesture list`
  - `./realme-buds gesture set <side> <trigger> <action>`
  - `./realme-buds gesture anc-modes <modes...>`
  - Automatic fast Omarchy shell session delegation and direct RFCOMM fallback.
- Quickshell IPC endpoints `setGesture`, `setGestureAncModes`, and `gestureStatus`.
- 12 new unit tests in `tests/test_gestures.py` bringing the test suite to 198/198 passing tests.


---

## [0.1.0] - 2026-10-18

### Added
- Native Omarchy status bar widget and interactive panel for realme earbuds.
- Hardware-verified compatibility with realme Buds T310 (`063C12`).
- Battery status monitoring with discrete Left, Right, and Case percentages and charging indicators.
- Active Noise Cancellation (ANC) control with instant switching between Off, Transparency, and Noise Cancellation.
- Native hardware EQ presets (Bass Boost+, Pure Bass, Balanced, Clear Voice) applied directly to earbud DSP.
- Extensible `DeviceRegistry` architecture loading declarative JSON device profiles from `src/realme_buds/devices/`.
- Decoupled `Transport` protocol abstraction with BlueZ D-Bus and RFCOMM socket backends.
- Full test suite with 141 Python unit tests and 8 Qt 6 QML interaction tests.
- Official listing on the Omarchy Plugin Marketplace (`realme-buds.control`).

