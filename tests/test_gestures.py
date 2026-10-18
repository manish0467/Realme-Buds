from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from realme_buds.bridge import BudsFrontendBridge, serialize_snapshot
from realme_buds.controller import BudsController
from realme_buds.gestures import (
    ACTION_DEFINITIONS,
    GestureConfig,
    GestureItem,
    GestureStore,
    default_gesture_config,
    encode_set_gesture_payload,
    parse_gesture_payload,
)
from realme_buds.models import GestureStatusResult


class GesturesUnitTests(unittest.TestCase):
    def test_default_gesture_config(self) -> None:
        cfg = default_gesture_config()
        self.assertEqual(len(cfg.items), 6)
        self.assertEqual(cfg.get_action("left", "double_tap"), "next_track")
        self.assertEqual(cfg.get_action("right", "double_tap"), "play_pause")
        self.assertEqual(cfg.get_action("right", "long_press"), "anc_cycle")
        self.assertEqual(cfg.long_press_anc_modes, ("anc", "transparency"))

    def test_gesture_config_with_action(self) -> None:
        cfg = default_gesture_config()
        updated = cfg.with_action("left", "double_tap", "play_pause")
        self.assertEqual(updated.get_action("left", "double_tap"), "play_pause")
        self.assertEqual(cfg.get_action("left", "double_tap"), "next_track")

        # Adding new trigger mapping
        added = cfg.with_action("left", "triple_tap", "game_mode")
        self.assertEqual(added.get_action("left", "triple_tap"), "game_mode")

    def test_gesture_config_with_action_validation(self) -> None:
        cfg = default_gesture_config()
        with self.assertRaises(ValueError):
            cfg.with_action("middle", "double_tap", "play_pause")
        with self.assertRaises(ValueError):
            cfg.with_action("left", "quad_tap", "play_pause")
        with self.assertRaises(ValueError):
            cfg.with_action("left", "double_tap", "invalid_action_xyz")

    def test_gesture_config_with_anc_modes(self) -> None:
        cfg = default_gesture_config()
        updated = cfg.with_anc_modes(("anc", "transparency", "off"))
        self.assertEqual(updated.long_press_anc_modes, ("anc", "transparency", "off"))
        # Invalid modes filtered
        fallback = cfg.with_anc_modes(("invalid_mode",))
        self.assertEqual(fallback.long_press_anc_modes, ("anc", "transparency"))

    def test_gesture_config_to_dict(self) -> None:
        cfg = default_gesture_config()
        d = cfg.to_dict()
        self.assertIn("left", d)
        self.assertIn("right", d)
        self.assertIn("actions", d)
        self.assertIn("long_press_anc_modes", d)
        self.assertEqual(d["left"]["double_tap"], "next_track")
        self.assertEqual(d["right"]["double_tap"], "play_pause")

    def test_parse_gesture_payload(self) -> None:
        # 26-byte payload from realme Buds T310 hardware probe:
        # status 0, count 6, 6 items of 4 bytes:
        # [01 01 02 06] Left double_tap -> next_track
        # [01 01 03 00] Left triple_tap -> none
        # [01 01 04 00] Left long_press -> none
        # [02 01 02 01] Right double_tap -> play_pause
        # [02 01 03 00] Right triple_tap -> none
        # [02 01 04 11] Right long_press -> anc_cycle (17)
        raw = bytes.fromhex("0006010102060101030001010400020102010201030002010411")
        cfg = parse_gesture_payload(raw)
        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(len(cfg.items), 6)
        self.assertEqual(cfg.get_action("left", "double_tap"), "next_track")
        self.assertEqual(cfg.get_action("left", "triple_tap"), "none")
        self.assertEqual(cfg.get_action("left", "long_press"), "none")
        self.assertEqual(cfg.get_action("right", "double_tap"), "play_pause")
        self.assertEqual(cfg.get_action("right", "triple_tap"), "none")
        self.assertEqual(cfg.get_action("right", "long_press"), "anc_cycle")

    def test_parse_gesture_payload_invalid(self) -> None:
        self.assertIsNone(parse_gesture_payload(b""))
        self.assertIsNone(parse_gesture_payload(b"\x00"))
        # Non-zero status
        self.assertIsNone(parse_gesture_payload(bytes.fromhex("010601010206")))
        # Truncated length
        self.assertIsNone(parse_gesture_payload(bytes.fromhex("000601010206")))

    def test_encode_set_gesture_payload(self) -> None:
        p_left_dt = encode_set_gesture_payload("left", "double_tap", "play_pause")
        self.assertEqual(p_left_dt, bytes((0x01, 0x01, 0x02, 0x01)))

        p_right_lp = encode_set_gesture_payload("right", "long_press", "anc_cycle")
        self.assertEqual(p_right_lp, bytes((0x02, 0x01, 0x04, 0x11)))

        p_none = encode_set_gesture_payload("left", "triple_tap", "none")
        self.assertEqual(p_none, bytes((0x01, 0x01, 0x03, 0x00)))

    def test_gesture_store_load_and_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = Path(tmpdir) / "gestures.json"
            store = GestureStore(store_file)

            # Initially file doesn't exist, returns fallback/default
            loaded = store.load()
            self.assertEqual(loaded.get_action("left", "double_tap"), "next_track")

            # Save modified config
            modified = loaded.with_action("left", "double_tap", "game_mode")
            modified = modified.with_anc_modes(("anc", "transparency", "off"))
            store.save(modified)

            # Reload
            reloaded = store.load()
            self.assertEqual(reloaded.get_action("left", "double_tap"), "game_mode")
            self.assertEqual(reloaded.long_press_anc_modes, ("anc", "transparency", "off"))

    def test_gesture_store_corrupted_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = Path(tmpdir) / "gestures.json"
            store_file.write_text("NOT_JSON")
            store = GestureStore(store_file)
            loaded = store.load()
            self.assertEqual(loaded.get_action("left", "double_tap"), "next_track")


class ControllerAndBridgeGestureTests(unittest.TestCase):
    def test_controller_gesture_status_and_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store_file = Path(tmpdir) / "gestures.json"
            controller = BudsController()
            controller._running = True
            controller._gesture_store = GestureStore(store_file)

            status = controller.gesture_status()
            self.assertIsInstance(status, GestureStatusResult)
            self.assertEqual(status.left["double_tap"], "next_track")

            # Set gesture
            success = controller.set_gesture("left", "double_tap", "play_pause")
            self.assertTrue(success)
            self.assertEqual(controller.gesture_status().left["double_tap"], "play_pause")

            # Set with snapshot
            ok, snapshot = controller.set_gesture_with_snapshot("right", "long_press", "game_mode")
            self.assertTrue(ok)
            self.assertIsNotNone(snapshot.gestures)
            assert snapshot.gestures is not None
            self.assertEqual(snapshot.gestures.right["long_press"], "game_mode")

            # Set ANC modes
            ok, snapshot = controller.set_gesture_anc_modes(("anc", "transparency", "off"))
            self.assertTrue(ok)
            assert snapshot.gestures is not None
            self.assertEqual(snapshot.gestures.long_press_anc_modes, ("anc", "transparency", "off"))

    def test_bridge_gesture_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            events: list[dict[str, object]] = []
            controller = BudsController()
            controller._running = True
            controller._gesture_store = GestureStore(Path(tmpdir) / "gestures.json")

            bridge = BudsFrontendBridge(emit=events.append, controller=controller)

            # gesture_status command
            res_status = bridge.execute("gesture_status")
            self.assertTrue(res_status["ok"])
            result = res_status["result"]
            assert isinstance(result, dict)
            self.assertIn("left", result)
            self.assertIn("right", result)

            # set_gesture command
            res_set = bridge.execute(
                "set_gesture",
                {"side": "left", "trigger": "double_tap", "action": "game_mode"},
            )
            self.assertTrue(res_set["ok"])
            set_res = res_set["result"]
            assert isinstance(set_res, dict)
            self.assertEqual(set_res["action"], "game_mode")
            self.assertTrue(set_res["success"])

            # set_gesture_anc_modes command
            res_modes = bridge.execute(
                "set_gesture_anc_modes",
                {"modes": ["anc", "transparency"]},
            )
            self.assertTrue(res_modes["ok"])

            # serialize_snapshot includes gestures
            snap = serialize_snapshot(controller.snapshot())
            self.assertIn("gestures", snap)
            self.assertIsNotNone(snap["gestures"])


if __name__ == "__main__":
    unittest.main()
