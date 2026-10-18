# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned (Daily Shipping Roadmap)
- **Day 1**: ANC Cycle CLI command (`./realme-buds anc cycle`) and Hyprland global hotkey integration.
- **Day 2**: 45ms Low Latency Game Mode toggle (`./realme-buds game status|on|off`) and panel switch.
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

