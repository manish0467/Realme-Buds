import unittest
from unittest.mock import MagicMock, patch

from realme_buds.bluez import Device
from realme_buds.controller import BudsController
from realme_buds.models import ControllerSnapshot, StatusResult
from realme_buds.bridge import BudsFrontendBridge
from realme_buds.backend import query_multipoint, set_multipoint
from realme_buds.profiles import REGISTRY


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="realme Buds T310",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)


def make_status():
    return StatusResult(
        device=DEVICE,
        product_id="063C12",
        model="realme Buds T310",
        remote_version=(),
        firmware_version="1.1.0.47",
        battery={"left": {"percentage": 80, "charging": False}, "right": {"percentage": 80, "charging": False}},
        anc="off",
        anc_level=None,
    )


class FakeSession:
    def __init__(self):
        self.switches = {"multipoint": False}
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

    def set_feature_switch(self, feature, enabled):
        from realme_buds.models import EventBatch
        self.switches["multipoint"] = enabled
        return True, EventBatch((), 0)


class MultipointTests(unittest.TestCase):
    def test_device_profile_declares_multipoint(self):
        profile = REGISTRY.get("063C12")
        self.assertIsNotNone(profile)
        self.assertIn("multipoint", profile.capabilities)

    def test_controller_multipoint_status_and_set(self):
        controller = BudsController()
        fake_session = FakeSession()
        controller._session = fake_session
        controller._running = True
        controller._status = make_status()

        self.assertFalse(controller.multipoint_status())

        success, snapshot = controller.set_multipoint_with_snapshot(True)
        self.assertTrue(success)
        self.assertTrue(fake_session.switches["multipoint"])
        self.assertTrue(controller.multipoint_status())

        # Turn off
        success, snapshot = controller.set_multipoint_with_snapshot(False)
        self.assertTrue(success)
        self.assertFalse(fake_session.switches["multipoint"])
        self.assertFalse(controller.multipoint_status())

    def test_bridge_multipoint_commands(self):
        controller = BudsController()
        fake_session = FakeSession()
        controller._session = fake_session
        controller._running = True
        controller._status = make_status()

        events = []
        bridge = BudsFrontendBridge(emit=events.append, controller=controller)

        # Status query
        res = bridge.execute("multipoint_status")
        self.assertTrue(res["ok"])
        self.assertFalse(res["result"]["multipoint"])

        # Enable multipoint
        res = bridge.execute("set_multipoint", {"enabled": True})
        self.assertTrue(res["ok"])
        self.assertTrue(res["result"]["multipoint"])
        self.assertTrue(res["result"]["success"])
        self.assertTrue(controller.multipoint_status())

        # Disable multipoint
        res = bridge.execute("set_multipoint", {"enabled": False})
        self.assertTrue(res["ok"])
        self.assertFalse(res["result"]["multipoint"])
        self.assertFalse(controller.multipoint_status())

    def test_bridge_set_multipoint_invalid_params(self):
        controller = BudsController()
        bridge = BudsFrontendBridge(emit=lambda _: None, controller=controller)
        res = bridge.execute("set_multipoint", {"enabled": "yes"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "invalid_parameters")

    def test_backend_query_multipoint(self):
        with patch("realme_buds.backend.query_feature_switches", return_value={"multipoint": True}):
            res = query_multipoint("AA:BB:CC:DD:EE:FF")
            self.assertTrue(res["multipoint"])
            self.assertEqual(res["switches"], {"multipoint": True})

    def test_backend_set_multipoint(self):
        fake_session = FakeSession()
        with patch("realme_buds.backend.select_device", return_value=DEVICE):
            with patch("realme_buds.session.OpoSession.bootstrap", return_value=(fake_session, make_status(), None)):
                res = set_multipoint(True, "AA:BB:CC:DD:EE:FF")
                self.assertTrue(res["multipoint"])
                self.assertTrue(res["success"])
                self.assertTrue(fake_session.switches["multipoint"])

    def test_cli_try_shell_multipoint(self):
        from realme_buds.cli import _try_shell_multipoint
        with patch("shutil.which", return_value="/usr/bin/omarchy-shell"):
            with patch("subprocess.run") as mock_run:
                # status
                mock_run.return_value = MagicMock(returncode=0, stdout='{"multipoint": true}')
                res = _try_shell_multipoint("status")
                self.assertEqual(res, {"multipoint": True})

                # on
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                res = _try_shell_multipoint("on")
                self.assertEqual(res, {"multipoint": True, "verified": True})

                # off
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                res = _try_shell_multipoint("off")
                self.assertEqual(res, {"multipoint": False, "verified": True})


if __name__ == "__main__":
    unittest.main()
