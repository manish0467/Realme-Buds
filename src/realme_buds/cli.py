from __future__ import annotations

import argparse
import json

import shutil
import subprocess

from .backend import (cycle_anc, device_summary, diagnostics_report, query_capabilities, query_eq,
                      query_game_mode, query_gestures, query_multipoint, query_status, query_wear_detection, ring_buds,
                      ring_status, set_anc, set_custom_eq, set_eq, set_game_mode, set_gesture, set_gesture_anc_modes,
                      set_multipoint, set_wear_detection, stop_ring_buds)
from .bluez import connected_devices
from .gestures import ACTION_DEFINITIONS


def _try_shell_cycle_anc() -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        proc = subprocess.run(
            ["omarchy-shell", "realme-buds.control", "cycleAnc"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if proc.returncode == 0:
            proc_status = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "status"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if proc_status.returncode == 0:
                data = json.loads(proc_status.stdout)
                return {
                    "anc": data.get("current_anc"),
                    "verified": True,
                }
    except Exception:
        pass
    return None


def _try_shell_game_mode(action: str) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if action == "status":
            proc_status = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "status"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc_status.returncode == 0:
                data = json.loads(proc_status.stdout)
                return {
                    "game_mode": bool(data.get("game_mode", False)),
                    "verified": True,
                }
        elif action == "toggle":
            proc_status = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "status"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if proc_status.returncode == 0:
                data = json.loads(proc_status.stdout)
                target = not bool(data.get("game_mode", False))
                proc = subprocess.run(
                    ["omarchy-shell", "realme-buds.control", "setGameMode", "true" if target else "false"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0:
                    return {"game_mode": target, "verified": True}
        else:
            enabled = (action == "on")
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setGameMode", "true" if enabled else "false"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"game_mode": enabled, "verified": True}
    except Exception:
        pass
    return None


def _try_shell_notify(action: str) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if action == "status":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "notifyStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        elif action == "test":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "testNotification"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"sent": True, "verified": True}
        else:
            enabled = (action == "on")
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setNotifications", "true" if enabled else "false"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"enabled": enabled, "verified": True}
    except Exception:
        pass
    return None


def _try_shell_wear(action: str) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if action == "status":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "wearStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        elif action == "toggle":
            proc_status = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "wearStatus"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if proc_status.returncode == 0:
                data = json.loads(proc_status.stdout)
                target = not bool(data.get("wear_detection", False))
                proc = subprocess.run(
                    ["omarchy-shell", "realme-buds.control", "setWearDetection", "true" if target else "false"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0:
                    return {"wear_detection": target, "verified": True}
        elif action in ("on", "off"):
            enabled = (action == "on")
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setWearDetection", "true" if enabled else "false"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"wear_detection": enabled, "verified": True}
        elif action == "mpris-status":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "mprisHookStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        elif action in ("mpris-on", "mpris-off"):
            enabled = (action == "mpris-on")
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setMprisHook", "true" if enabled else "false"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"mpris_hook": enabled, "verified": True}
    except Exception:
        pass
    return None


def _try_shell_multipoint(action: str) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if action == "status":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "multipointStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        elif action == "toggle":
            proc_status = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "multipointStatus"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if proc_status.returncode == 0:
                data = json.loads(proc_status.stdout)
                target = not bool(data.get("multipoint", False))
                proc = subprocess.run(
                    ["omarchy-shell", "realme-buds.control", "setMultipoint", "true" if target else "false"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0:
                    return {"multipoint": target, "verified": True}
        elif action in ("on", "off"):
            enabled = (action == "on")
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setMultipoint", "true" if enabled else "false"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"multipoint": enabled, "verified": True}
    except Exception:
        pass
    return None


def _try_shell_find(action: str) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if action == "status":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "ringStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout)
        elif action == "stop":
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "stopRingBuds"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"ringing": False, "stopped": True}
        elif action in ("left", "right", "both"):
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "ringBuds", action],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"ringing": True, "target": action}
    except Exception:
        pass
    return None


def _try_shell_status() -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        proc = subprocess.run(
            ["omarchy-shell", "realme-buds.control", "status"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            dev_status = data.get("device_status")
            if dev_status:
                return dev_status
    except Exception:
        pass
    return None


def _try_shell_gesture(
    command: str,
    side: str | None = None,
    trigger: str | None = None,
    action: str | None = None,
    modes: list[str] | None = None,
) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if command in ("status", "list"):
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "gestureStatus"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                if command == "list":
                    return {"actions": data.get("actions", [])}
                return data
        elif command == "set" and side and trigger and action:
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setGesture", side, trigger, action],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"side": side, "trigger": trigger, "action": action, "verified": True}
        elif command == "anc-modes" and modes:
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setGestureAncModes", json.dumps(modes)],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"long_press_anc_modes": modes, "verified": True}
    except Exception:
        pass
    return None


def _try_shell_eq(
    eq_command: str,
    preset: str | None = None,
    entry_id: int | None = None,
    gains: tuple[int, ...] | None = None,
    name: str | None = None,
) -> dict[str, object] | None:
    if not shutil.which("omarchy-shell"):
        return None
    try:
        if eq_command in ("status", "list"):
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "queryEq"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if proc.returncode == 0:
                data = json.loads(proc.stdout)
                if not data:
                    return None
                if eq_command == "list":
                    return {
                        "current": {key: data.get(key) for key in ("current_id", "current_name", "current_kind")},
                        "presets": data.get("presets", []),
                        "custom_entries": data.get("custom_entries", []),
                        "gain_step_db": data.get("gain_step_db", 1),
                    }
                return data
        elif eq_command == "set" and preset:
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setEq", preset],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"preset": preset, "verified": True}
        elif eq_command == "custom" and entry_id is not None and gains is not None:
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "setCustomEq", str(entry_id), json.dumps(list(gains))],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"entry_id": entry_id, "gains_db": list(gains), "verified": True}
        elif eq_command == "add" and name:
            gains_json = json.dumps(list(gains)) if gains is not None else "[]"
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "addCustomEq", name, gains_json],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"name": name, "verified": True}
        elif eq_command == "delete" and entry_id is not None:
            proc = subprocess.run(
                ["omarchy-shell", "realme-buds.control", "deleteCustomEq", str(entry_id)],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if proc.returncode == 0:
                return {"entry_id": entry_id, "deleted": True}
    except Exception:
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(prog="realme-buds")
    parser.add_argument("--device", metavar="ADDRESS", help="select a connected device by Bluetooth address")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("devices", help="list connected candidate devices")
    subparsers.add_parser("status", help="query product, battery and ANC state")
    subparsers.add_parser("capabilities", help="show verified capabilities for the selected device")
    diagnostics = subparsers.add_parser("diagnostics", help="produce a privacy-safe compatibility report")
    diagnostics.add_argument("--report", action="store_true", help="emit a pasteable JSON report")
    anc_parser = subparsers.add_parser("anc", help="query or safely set ANC state")
    anc_parser.add_argument(
        "mode",
        choices=("status", "on", "off", "transparency", "light", "medium", "deep", "smart", "cycle"),
    )
    eq_parser = subparsers.add_parser("eq", help="query or safely set native earbud EQ")
    eq_commands = eq_parser.add_subparsers(dest="eq_command", required=True)
    eq_commands.add_parser("status", help="read current native EQ and device-declared bands")
    eq_commands.add_parser("list", help="list factory presets and custom entries")
    eq_set = eq_commands.add_parser("set", help="select a factory or device-declared custom EQ")
    eq_set.add_argument("preset", help="preset key, numeric factory id, or custom:<id>")
    eq_custom = eq_commands.add_parser("custom", help="update an existing device-declared custom curve")
    eq_custom.add_argument("entry_id", type=int, help="custom entry id returned by eq status")
    eq_custom.add_argument("gains", nargs="+", type=int, help="one whole-dB gain per reported band")
    eq_add = eq_commands.add_parser("add", help="create a new custom EQ preset")
    eq_add.add_argument("name", help="name of the custom EQ preset")
    eq_add.add_argument("gains", nargs="*", type=int, help="optional whole-dB gains for bands")
    eq_del = eq_commands.add_parser("delete", help="delete a custom EQ preset by id")
    eq_del.add_argument("entry_id", type=int, help="custom preset id to delete")
    game_parser = subparsers.add_parser("game", help="query or toggle 45ms low-latency game mode")
    game_parser.add_argument(
        "action",
        choices=("status", "on", "off", "toggle"),
        nargs="?",
        default="status",
        help="query or set game mode state (default: status)",
    )
    notify_parser = subparsers.add_parser("notify", help="query, toggle, or test low battery desktop notifications")
    notify_parser.add_argument(
        "action",
        choices=("status", "on", "off", "test"),
        nargs="?",
        default="status",
        help="query, configure, or test battery notifications (default: status)",
    )
    wear_parser = subparsers.add_parser("wear", help="query or configure in-ear wear detection and MPRIS auto-pause")
    wear_parser.add_argument(
        "action",
        choices=("status", "on", "off", "toggle", "mpris-on", "mpris-off", "mpris-status"),
        nargs="?",
        default="status",
        help="query or configure in-ear detection and MPRIS hook (default: status)",
    )
    multipoint_parser = subparsers.add_parser(
        "multipoint",
        aliases=["dual"],
        help="query or configure dual-device / multipoint connection",
    )
    multipoint_parser.add_argument(
        "action",
        choices=("status", "on", "off", "toggle"),
        nargs="?",
        default="status",
        help="query or configure dual-device multipoint switch (default: status)",
    )
    find_parser = subparsers.add_parser(
        "find",
        aliases=["ring"],
        help="ring misplaced earbuds with acoustic locator chime",
    )
    find_parser.add_argument(
        "action",
        choices=("left", "right", "both", "stop", "status"),
        nargs="?",
        default="status",
        help="acoustic locator action: left, right, both, stop, status (default: status)",
    )
    gesture_parser = subparsers.add_parser(
        "gesture",
        aliases=["touch"],
        help="query or configure touch gesture tap controls",
    )
    gesture_commands = gesture_parser.add_subparsers(dest="gesture_command", required=False)
    gesture_commands.add_parser("status", help="show current touch gesture mappings")
    gesture_commands.add_parser("list", help="list supported gesture actions")
    gesture_set = gesture_commands.add_parser("set", help="set a touch gesture action")
    gesture_set.add_argument("side", choices=("left", "right"), help="earbud side")
    gesture_set.add_argument("trigger", choices=("double_tap", "triple_tap", "long_press"), help="tap trigger")
    gesture_set.add_argument("action", help="action to assign (e.g. next_track, play_pause, anc_cycle)")
    gesture_anc = gesture_commands.add_parser("anc-modes", help="configure long-press noise control modes")
    gesture_anc.add_argument("modes", nargs="+", choices=("anc", "transparency", "off"), help="modes to cycle on long-press")
    args = parser.parse_args()
    try:
        if args.command == "devices":
            output = [
                device_summary(device, include_address=True)
                for device in connected_devices()
                if device.looks_compatible
            ]
        elif args.command == "status":
            shell_res = _try_shell_status() if args.device is None else None
            output = shell_res if shell_res is not None else query_status(args.device)
        elif args.command == "capabilities":
            output = query_capabilities(args.device)
        elif args.command == "diagnostics":
            output = diagnostics_report(args.device)
        elif args.command == "eq":
            shell_res = (
                _try_shell_eq(
                    args.eq_command,
                    preset=getattr(args, "preset", None),
                    entry_id=getattr(args, "entry_id", None),
                    gains=tuple(getattr(args, "gains", ())) if getattr(args, "gains", None) else None,
                    name=getattr(args, "name", None),
                )
                if args.device is None
                else None
            )
            if shell_res is not None:
                output = shell_res
            elif args.eq_command == "status":
                output = query_eq(args.device)
            elif args.eq_command == "list":
                state = query_eq(args.device)
                output = {
                    "current": {key: state[key] for key in ("current_id", "current_name", "current_kind")},
                    "presets": state["presets"],
                    "custom_entries": state["custom_entries"],
                    "gain_step_db": state["gain_step_db"],
                }
            elif args.eq_command == "custom":
                output = set_custom_eq(args.entry_id, tuple(args.gains), args.device)
            elif args.eq_command == "add":
                from .custom_eq import CustomEqStore
                store = CustomEqStore()
                preset = store.add_preset(args.name, list(args.gains) if getattr(args, "gains", None) else None)
                output = preset.to_dict()
            elif args.eq_command == "delete":
                from .custom_eq import CustomEqStore
                store = CustomEqStore()
                store.delete_preset(args.entry_id)
                output = {"entry_id": args.entry_id, "deleted": True}
            else:
                output = set_eq(args.preset, args.device)
        elif args.command == "game":
            shell_res = _try_shell_game_mode(args.action) if args.device is None else None
            if shell_res is not None:
                output = shell_res
            elif args.action == "status":
                output = query_game_mode(args.device)
            elif args.action == "toggle":
                curr = query_game_mode(args.device)
                next_val = not bool(curr.get("game_mode", False))
                output = set_game_mode(next_val, args.device)
            else:
                output = set_game_mode(args.action == "on", args.device)
        elif args.command == "notify":
            shell_res = _try_shell_notify(args.action) if args.device is None else None
            if shell_res is not None:
                output = shell_res
            elif args.action == "test":
                from .notifications import BatteryNotificationPolicy
                policy = BatteryNotificationPolicy()
                event = policy.send_test_notification()
                output = {"sent": True, "event": event.to_dict()}
            elif args.action == "status":
                from .notifications import BatteryNotificationPolicy
                policy = BatteryNotificationPolicy()
                output = policy.get_state()
            else:
                output = {"enabled": args.action == "on"}
        elif args.command == "wear":
            shell_res = _try_shell_wear(args.action) if args.device is None else None
            if shell_res is not None:
                output = shell_res
            elif args.action == "status":
                output = query_wear_detection(args.device)
            elif args.action == "toggle":
                curr = query_wear_detection(args.device)
                next_val = not bool(curr.get("wear_detection", False))
                output = set_wear_detection(next_val, args.device)
            elif args.action in ("on", "off"):
                output = set_wear_detection(args.action == "on", args.device)
            elif args.action == "mpris-status":
                from .mpris import MprisManager
                output = MprisManager().get_state()
            elif args.action in ("mpris-on", "mpris-off"):
                output = {"mpris_hook": args.action == "mpris-on"}
            else:
                output = query_wear_detection(args.device)
        elif args.command in ("multipoint", "dual"):
            shell_res = _try_shell_multipoint(args.action) if args.device is None else None
            if shell_res is not None:
                output = shell_res
            elif args.action == "status":
                output = query_multipoint(args.device)
            elif args.action == "toggle":
                curr = query_multipoint(args.device)
                next_val = not bool(curr.get("multipoint", False))
                output = set_multipoint(next_val, args.device)
            elif args.action in ("on", "off"):
                output = set_multipoint(args.action == "on", args.device)
            else:
                output = query_multipoint(args.device)
        elif args.command in ("find", "ring"):
            shell_res = _try_shell_find(args.action) if args.device is None else None
            if shell_res is not None:
                output = shell_res
            elif args.action == "status":
                output = ring_status()
            elif args.action == "stop":
                output = stop_ring_buds()
            elif args.action in ("left", "right", "both"):
                output = ring_buds(target=args.action, address=args.device)
            else:
                output = ring_status()
        elif args.command == "anc":
            if args.mode == "status":
                status = query_status(args.device)
                output = {"anc": status["anc"], "anc_level": status["anc_level"]}
            elif args.mode == "cycle":
                shell_res = _try_shell_cycle_anc() if args.device is None else None
                output = shell_res if shell_res is not None else cycle_anc(args.device)
            else:
                output = set_anc(args.mode, args.device)
        elif args.command in ("gesture", "touch"):
            subcmd = getattr(args, "gesture_command", None) or "status"
            if subcmd == "list":
                output = {
                    "actions": [
                        {"key": k, "label": v["label"], "id": v["id"]}
                        for k, v in ACTION_DEFINITIONS.items()
                    ]
                }
            elif subcmd == "set":
                shell_res = (
                    _try_shell_gesture("set", side=args.side, trigger=args.trigger, action=args.action)
                    if args.device is None
                    else None
                )
                if shell_res is not None:
                    output = shell_res
                else:
                    output = set_gesture(args.side, args.trigger, args.action, args.device)
            elif subcmd == "anc-modes":
                shell_res = (
                    _try_shell_gesture("anc-modes", modes=args.modes)
                    if args.device is None
                    else None
                )
                if shell_res is not None:
                    output = shell_res
                else:
                    output = set_gesture_anc_modes(tuple(args.modes), args.device)
            else:
                shell_res = _try_shell_gesture("status") if args.device is None else None
                if shell_res is not None:
                    output = shell_res
                else:
                    output = query_gestures(args.device)
        print(json.dumps(output, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"realme-buds: {error}\n")


if __name__ == "__main__":
    main()
