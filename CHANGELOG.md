# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Planned (Daily Shipping Roadmap)
- **Day 3**: Battery threshold notifications (20% warning, 10% critical) with anti-spam discharge tracking.
- **Day 4**: In-ear wear detection toggle and desktop MPRIS auto-pause hook.
- **Day 5**: Dual-device / Multipoint switch support.
- **Day 6**: "Find My Buds" acoustic locator chime.
- **Day 7**: Touch gesture remapping for physical tap controls.

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

