from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .protocol import Frame, SOF

# Physical earbud sides
SIDE_LEFT = 1
SIDE_RIGHT = 2

SIDE_NAMES = {
    SIDE_LEFT: "left",
    SIDE_RIGHT: "right",
}
SIDE_IDS = {v: k for k, v in SIDE_NAMES.items()}

# Trigger types
TRIGGER_SINGLE_TAP = 1
TRIGGER_DOUBLE_TAP = 2
TRIGGER_TRIPLE_TAP = 3
TRIGGER_LONG_PRESS = 4

TRIGGER_NAMES = {
    TRIGGER_SINGLE_TAP: "single_tap",
    TRIGGER_DOUBLE_TAP: "double_tap",
    TRIGGER_TRIPLE_TAP: "triple_tap",
    TRIGGER_LONG_PRESS: "long_press",
}
TRIGGER_IDS = {v: k for k, v in TRIGGER_NAMES.items()}

# Action definitions
ACTION_NONE = 0
ACTION_PLAY_PAUSE = 1
ACTION_PREV_TRACK = 2
ACTION_NEXT_TRACK = 3
ACTION_VOICE_ASSISTANT = 4
ACTION_GAME_MODE = 5
ACTION_AUDIO_TRACK_6 = 6
ACTION_VOLUME_UP = 7
ACTION_VOLUME_DOWN = 8
ACTION_ANC_CYCLE = 17  # 0x11

ACTION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "none": {"id": ACTION_NONE, "label": "Disabled", "wire_id": 0},
    "play_pause": {"id": ACTION_PLAY_PAUSE, "label": "Play / Pause", "wire_id": 1},
    "prev_track": {"id": ACTION_PREV_TRACK, "label": "Previous Track", "wire_id": 2},
    "next_track": {"id": ACTION_NEXT_TRACK, "label": "Next Track", "wire_id": 6},
    "voice_assistant": {"id": ACTION_VOICE_ASSISTANT, "label": "Voice Assistant", "wire_id": 4},
    "game_mode": {"id": ACTION_GAME_MODE, "label": "Game Mode", "wire_id": 5},
    "anc_cycle": {"id": ACTION_ANC_CYCLE, "label": "Noise Control", "wire_id": 17},
    "volume_up": {"id": ACTION_VOLUME_UP, "label": "Volume Up", "wire_id": 7},
    "volume_down": {"id": ACTION_VOLUME_DOWN, "label": "Volume Down", "wire_id": 8},
}

WIRE_TO_ACTION: dict[int, str] = {
    0: "none",
    1: "play_pause",
    2: "prev_track",
    3: "next_track",
    4: "voice_assistant",
    5: "game_mode",
    6: "next_track",
    7: "volume_up",
    8: "volume_down",
    17: "anc_cycle",
}


@dataclass(frozen=True)
class GestureItem:
    side: str
    trigger: str
    action: str
    action_id: int
    label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GestureConfig:
    items: tuple[GestureItem, ...]
    long_press_anc_modes: tuple[str, ...] = ("anc", "transparency")

    def to_dict(self) -> dict[str, Any]:
        left_dict: dict[str, str] = {}
        right_dict: dict[str, str] = {}
        for item in self.items:
            if item.side == "left":
                left_dict[item.trigger] = item.action
            elif item.side == "right":
                right_dict[item.trigger] = item.action

        actions_list = [
            {"key": key, "label": val["label"], "id": val["id"]}
            for key, val in ACTION_DEFINITIONS.items()
        ]

        return {
            "left": left_dict,
            "right": right_dict,
            "items": [item.to_dict() for item in self.items],
            "actions": actions_list,
            "long_press_anc_modes": list(self.long_press_anc_modes),
        }

    def get_action(self, side: str, trigger: str) -> str:
        for item in self.items:
            if item.side == side and item.trigger == trigger:
                return item.action
        return "none"

    def with_action(self, side: str, trigger: str, action: str) -> GestureConfig:
        norm_side = side.lower().strip()
        norm_trigger = trigger.lower().strip()
        norm_action = action.lower().strip()

        if norm_side not in ("left", "right"):
            raise ValueError(f"Invalid side: {side!r}. Must be 'left' or 'right'.")
        if norm_trigger not in ("double_tap", "triple_tap", "long_press"):
            raise ValueError(f"Invalid trigger: {trigger!r}. Must be 'double_tap', 'triple_tap', or 'long_press'.")
        if norm_action not in ACTION_DEFINITIONS:
            raise ValueError(f"Unknown gesture action: {action!r}. Valid choices: {list(ACTION_DEFINITIONS.keys())}")

        action_info = ACTION_DEFINITIONS[norm_action]
        new_items: list[GestureItem] = []
        found = False
        for item in self.items:
            if item.side == norm_side and item.trigger == norm_trigger:
                new_items.append(
                    GestureItem(
                        side=norm_side,
                        trigger=norm_trigger,
                        action=norm_action,
                        action_id=action_info["id"],
                        label=action_info["label"],
                    )
                )
                found = True
            else:
                new_items.append(item)

        if not found:
            new_items.append(
                GestureItem(
                    side=norm_side,
                    trigger=norm_trigger,
                    action=norm_action,
                    action_id=action_info["id"],
                    label=action_info["label"],
                )
            )

        return GestureConfig(tuple(new_items), self.long_press_anc_modes)

    def with_anc_modes(self, modes: tuple[str, ...]) -> GestureConfig:
        valid = {"anc", "transparency", "off"}
        cleaned = tuple(m.lower().strip() for m in modes if m.lower().strip() in valid)
        if not cleaned:
            cleaned = ("anc", "transparency")
        return GestureConfig(self.items, cleaned)


def default_gesture_config() -> GestureConfig:
    """Return default hardware gestures for realme Buds T310."""
    return GestureConfig(
        items=(
            GestureItem("left", "double_tap", "next_track", 3, "Next Track"),
            GestureItem("left", "triple_tap", "none", 0, "Disabled"),
            GestureItem("left", "long_press", "none", 0, "Disabled"),
            GestureItem("right", "double_tap", "play_pause", 1, "Play / Pause"),
            GestureItem("right", "triple_tap", "none", 0, "Disabled"),
            GestureItem("right", "long_press", "anc_cycle", 17, "Noise Control"),
        ),
        long_press_anc_modes=("anc", "transparency"),
    )


def parse_gesture_payload(payload: bytes) -> GestureConfig | None:
    """Parse 0x8108 response payload into GestureConfig."""
    if len(payload) < 2:
        return None
    status = payload[0]
    count = payload[1]
    if status != 0 or len(payload) < 2 + count * 4:
        return None

    items: list[GestureItem] = []
    idx = 2
    for _ in range(count):
        chunk = payload[idx : idx + 4]
        side_id = chunk[0]
        trigger_id = chunk[2]
        action_id = chunk[3]

        side_name = SIDE_NAMES.get(side_id, f"side_{side_id}")
        trigger_name = TRIGGER_NAMES.get(trigger_id, f"trigger_{trigger_id}")
        action_name = WIRE_TO_ACTION.get(action_id, f"action_{action_id}")
        action_label = ACTION_DEFINITIONS.get(action_name, {}).get("label", f"Action {action_id}")

        items.append(
            GestureItem(
                side=side_name,
                trigger=trigger_name,
                action=action_name,
                action_id=action_id,
                label=action_label,
            )
        )
        idx += 4

    return GestureConfig(items=tuple(items))


def encode_set_gesture_payload(side: str, trigger: str, action: str) -> bytes:
    """Encode 4-byte payload for setting a single gesture mapping on wire."""
    side_id = SIDE_IDS.get(side.lower().strip(), 1)
    trigger_id = TRIGGER_IDS.get(trigger.lower().strip(), 2)
    action_info = ACTION_DEFINITIONS.get(action.lower().strip())
    action_id = action_info["wire_id"] if action_info else 0
    return bytes((side_id, 1, trigger_id, action_id))


class GestureStore:
    """Manages persistent custom gesture mappings across reconnects and reboots."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_dir = Path.home() / ".config" / "omarchy" / "plugins" / "realme-buds.control"
            config_path = config_dir / "gestures.json"
        self.config_path = Path(config_path)

    def load(self, fallback: GestureConfig | None = None) -> GestureConfig:
        config = fallback or default_gesture_config()
        if not self.config_path.exists():
            return config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            left = data.get("left", {})
            right = data.get("right", {})
            anc_modes = tuple(data.get("long_press_anc_modes", ["anc", "transparency"]))

            current = config
            for trigger, action in left.items():
                if action in ACTION_DEFINITIONS and trigger in ("double_tap", "triple_tap", "long_press"):
                    current = current.with_action("left", trigger, action)
            for trigger, action in right.items():
                if action in ACTION_DEFINITIONS and trigger in ("double_tap", "triple_tap", "long_press"):
                    current = current.with_action("right", trigger, action)
            current = current.with_anc_modes(anc_modes)
            return current
        except Exception:
            return config

    def save(self, config: GestureConfig) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2)
        except Exception:
            pass
