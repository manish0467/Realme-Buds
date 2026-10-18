import unittest
from unittest.mock import MagicMock, patch

from realme_buds.bluez import Device
from realme_buds.controller import BudsController
from realme_buds.models import ControllerSnapshot, StatusResult
from realme_buds.mpris import MprisManager
from realme_buds.bridge import BudsFrontendBridge


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="realme Buds T310",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)


def make_status(battery=None, connected=True):
    dev = Device(
        address="AA:BB:CC:DD:EE:FF",
        name="realme Buds T310",
        connected=connected,
        uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
        battery=80,
    )
    return StatusResult(
        device=dev,
        product_id="063C12",
        model="realme Buds T310",
        remote_version=(),
        firmware_version="1.1.0.47",
        battery=battery or {"left": {"percentage": 80, "charging": False}, "right": {"percentage": 80, "charging": False}},
        anc="off",
        anc_level=None,
    )


class MprisManagerTests(unittest.TestCase):
    def test_mpris_pause_all_and_resume(self):
        manager = MprisManager(enabled=True)
        with patch.object(manager, "get_playing_players", return_value=["org.mpris.MediaPlayer2.sporetify"]):
            with patch("dbus.SessionBus") as mock_bus_cls:
                mock_bus = MagicMock()
                mock_player_obj = MagicMock()
                mock_bus.get_object.return_value = mock_player_obj
                mock_bus_cls.return_value = mock_bus

                with patch("dbus.Interface") as mock_iface_cls:
                    mock_iface = MagicMock()
                    mock_iface_cls.return_value = mock_iface

                    paused = manager.pause_all()
                    self.assertEqual(paused, ["org.mpris.MediaPlayer2.sporetify"])
                    self.assertEqual(manager._auto_paused, ["org.mpris.MediaPlayer2.sporetify"])
                    mock_iface.Pause.assert_called_once()

                    resumed = manager.resume_paused()
                    self.assertEqual(resumed, ["org.mpris.MediaPlayer2.sporetify"])
                    self.assertEqual(manager._auto_paused, [])
                    mock_iface.Play.assert_called_once()

    def test_handle_wear_change(self):
        manager = MprisManager(enabled=True)
        with patch.object(manager, "pause_all", return_value=["player1"]) as mock_pause:
            with patch.object(manager, "resume_paused", return_value=["player1"]) as mock_resume:
                # Removed from ear -> pause
                manager.handle_wear_change(wearing=False)
                mock_pause.assert_called_once()

                # Placed in ear -> resume
                manager.handle_wear_change(wearing=True)
                mock_resume.assert_called_once()

    def test_disabled_manager_does_nothing(self):
        manager = MprisManager(enabled=False)
        with patch.object(manager, "get_playing_players", return_value=["player1"]):
            self.assertEqual(manager.pause_all(), [])
            self.assertEqual(manager.handle_wear_change(wearing=False), [])
            self.assertEqual(manager.handle_wear_change(wearing=True), [])


class FakeSession:
    def __init__(self):
        self.switches = {"wear_detection": True}
        self.advertised_event_codes = ()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def authenticate_and_subscribe(self):
        from realme_buds.models import EventBatch
        return EventBatch((), 0)

    def query_feature_switches(self):
        return dict(self.switches)

    def set_feature_switch(self, fid, enabled):
        from realme_buds.models import EventBatch, SafeEvent
        self.switches["wear_detection"] = enabled
        return True, EventBatch((SafeEvent("feature_switches", {"wear_detection": enabled}),), 0)


class FakeBackend:
    def __init__(self, session):
        self.session = session

    def start_session(self, _address=None):
        from realme_buds.models import EventBatch
        return self.session, make_status(), EventBatch((), 0)

    def status(self, _address=None):
        return make_status()


class ControllerWearTests(unittest.TestCase):
    def test_wear_detection_controller_methods(self):
        session = FakeSession()
        backend = FakeBackend(session)
        controller = BudsController(backend)
        controller.start()

        self.assertTrue(controller.wear_detection_status())
        ok, snapshot = controller.set_wear_detection_with_snapshot(False)
        self.assertTrue(ok)
        self.assertFalse(snapshot.feature_switches.get("wear_detection"))
        self.assertFalse(controller.wear_detection_status())
        controller.shutdown()


class BridgeWearCommandsTests(unittest.TestCase):
    def test_bridge_wear_and_mpris_commands(self):
        emitted = []
        controller = MagicMock()
        controller.wear_detection_status.return_value = True
        controller.set_wear_detection_with_snapshot.return_value = (True, ControllerSnapshot(
            status=make_status(),
            feature_switches={"wear_detection": False},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=1,
        ))
        controller.snapshot.return_value = ControllerSnapshot(
            status=make_status(),
            feature_switches={"wear_detection": True},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=1,
        )

        bridge = BudsFrontendBridge(emitted.append, controller=controller)

        # wear_detection_status
        status_res = bridge.execute("wear_detection_status")
        self.assertTrue(status_res["ok"])
        self.assertTrue(status_res["result"]["wear_detection"])

        # set_wear_detection
        set_res = bridge.execute("set_wear_detection", {"enabled": False})
        self.assertTrue(set_res["ok"])
        self.assertFalse(set_res["result"]["wear_detection"])
        self.assertTrue(set_res["result"]["success"])

        # validation error
        invalid = bridge.execute("set_wear_detection", {"enabled": "bad"})
        self.assertFalse(invalid["ok"])

        # mpris_hook_status
        mpris_status = bridge.execute("mpris_hook_status")
        self.assertTrue(mpris_status["ok"])
        self.assertTrue(mpris_status["result"]["enabled"])

        # set_mpris_hook
        mpris_set = bridge.execute("set_mpris_hook", {"enabled": False})
        self.assertTrue(mpris_set["ok"])
        self.assertFalse(mpris_set["result"]["enabled"])
        self.assertFalse(bridge.mpris_manager.enabled)

    def test_bridge_charging_transition_triggers_mpris(self):
        controller = MagicMock()
        bridge = BudsFrontendBridge(lambda _e: None, controller=controller)
        bridge.mpris_manager = MagicMock(spec=MprisManager)

        # Snapshot 1: wearing (not charging)
        s1 = ControllerSnapshot(
            status=make_status(battery={"left": {"percentage": 80, "charging": False}, "right": {"percentage": 80, "charging": False}}),
            feature_switches={},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=1,
        )
        bridge._on_snapshot(s1)
        bridge.mpris_manager.handle_wear_change.assert_not_called()

        # Snapshot 2: placed in case (now charging) -> should pause!
        s2 = ControllerSnapshot(
            status=make_status(battery={"left": {"percentage": 80, "charging": True}, "right": {"percentage": 80, "charging": True}}),
            feature_switches={},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=2,
        )
        bridge._on_snapshot(s2)
        bridge.mpris_manager.handle_wear_change.assert_called_with(wearing=False)

        # Snapshot 3: taken out of case (now not charging) -> should resume!
        s3 = ControllerSnapshot(
            status=make_status(battery={"left": {"percentage": 80, "charging": False}, "right": {"percentage": 80, "charging": False}}),
            feature_switches={},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=3,
        )
        bridge._on_snapshot(s3)
        bridge.mpris_manager.handle_wear_change.assert_called_with(wearing=True)


if __name__ == "__main__":
    unittest.main()
