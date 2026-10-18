import unittest
from unittest.mock import MagicMock, patch

from realme_buds.bluez import Device
from realme_buds.models import StatusResult, ControllerSnapshot
from realme_buds.notifications import (
    BatteryNotificationPolicy,
    NotificationDispatcher,
    NotificationEvent,
)
from realme_buds.bridge import BudsFrontendBridge
from realme_buds.service import BudsServiceRunner


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="realme Buds T310",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)


def make_status(battery=None, device_battery=80, connected=True):
    dev = Device(
        address="AA:BB:CC:DD:EE:FF",
        name="realme Buds T310",
        connected=connected,
        uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
        battery=device_battery,
    )
    return StatusResult(
        device=dev,
        product_id="063C12",
        model="realme Buds T310",
        remote_version=(),
        firmware_version="1.1.0.47",
        battery=battery,
        anc="off",
        anc_level=None,
    )


class NotificationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.dispatcher = MagicMock(spec=NotificationDispatcher)
        self.policy = BatteryNotificationPolicy(dispatcher=self.dispatcher)

    def test_no_alert_when_battery_healthy(self):
        status = make_status(battery={"left": {"percentage": 80, "charging": False}, "right": {"percentage": 85, "charging": False}})
        events = self.policy.evaluate(status)
        self.assertEqual(len(events), 0)

    def test_warning_alert_at_20_percent(self):
        status = make_status(battery={"left": {"percentage": 20, "charging": False}, "right": {"percentage": 75, "charging": False}})
        events = self.policy.evaluate(status)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].urgency, "normal")
        self.assertIn("Left earbud", events[0].message)
        self.assertEqual(events[0].percentage, 20)

    def test_no_duplicate_warning_while_in_warning_band(self):
        status20 = make_status(battery={"left": {"percentage": 20, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status20)), 1)

        status18 = make_status(battery={"left": {"percentage": 18, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status18)), 0)

        status12 = make_status(battery={"left": {"percentage": 12, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status12)), 0)

    def test_critical_alert_at_10_percent(self):
        status20 = make_status(battery={"left": {"percentage": 20, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.policy.evaluate(status20)

        status10 = make_status(battery={"left": {"percentage": 10, "charging": False}, "right": {"percentage": 75, "charging": False}})
        events = self.policy.evaluate(status10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].urgency, "critical")
        self.assertIn("critically low", events[0].message)
        self.assertEqual(events[0].percentage, 10)

    def test_no_duplicate_critical_alert(self):
        status10 = make_status(battery={"left": {"percentage": 10, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.policy.evaluate(status10)

        status5 = make_status(battery={"left": {"percentage": 5, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status5)), 0)

    def test_charging_suppresses_alerts_and_resets_state(self):
        status_charging = make_status(battery={"left": {"percentage": 8, "charging": True}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status_charging)), 0)
        self.assertFalse(self.policy.states["left"].warned)
        self.assertFalse(self.policy.states["left"].critical_warned)

    def test_recovery_above_threshold_resets_alerts(self):
        status_low = make_status(battery={"left": {"percentage": 15, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status_low)), 1)

        # Charged back up to 80%
        status_recovered = make_status(battery={"left": {"percentage": 80, "charging": False}, "right": {"percentage": 80, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status_recovered)), 0)
        self.assertFalse(self.policy.states["left"].warned)

        # Discharges to 18% again
        status_low_again = make_status(battery={"left": {"percentage": 18, "charging": False}, "right": {"percentage": 75, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status_low_again)), 1)

    def test_coalesces_left_and_right_earbuds(self):
        status = make_status(battery={"left": {"percentage": 15, "charging": False}, "right": {"percentage": 15, "charging": False}})
        events = self.policy.evaluate(status)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].component, "both")
        self.assertIn("Earbuds battery is low", events[0].message)

    def test_coalesces_critical_left_and_right_earbuds(self):
        status = make_status(battery={"left": {"percentage": 8, "charging": False}, "right": {"percentage": 9, "charging": False}})
        events = self.policy.evaluate(status)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].component, "both")
        self.assertEqual(events[0].urgency, "critical")
        self.assertIn("Earbuds battery is critically low", events[0].message)

    def test_case_battery_low_and_critical(self):
        status_case_low = make_status(battery={
            "left": {"percentage": 80, "charging": False},
            "right": {"percentage": 80, "charging": False},
            "case": {"percentage": 20, "charging": False},
        })
        events = self.policy.evaluate(status_case_low)
        self.assertEqual(len(events), 1)
        self.assertIn("Charging case", events[0].message)
        self.assertEqual(events[0].urgency, "normal")

        status_case_crit = make_status(battery={
            "left": {"percentage": 80, "charging": False},
            "right": {"percentage": 80, "charging": False},
            "case": {"percentage": 10, "charging": False},
        })
        events = self.policy.evaluate(status_case_crit)
        self.assertEqual(len(events), 1)
        self.assertIn("Charging case", events[0].message)
        self.assertEqual(events[0].urgency, "critical")
        self.assertIn("Please connect charger", events[0].message)

    def test_bluez_battery_fallback(self):
        status = make_status(battery=None, device_battery=15)
        events = self.policy.evaluate(status)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].percentage, 15)
        self.assertEqual(events[0].urgency, "normal")

    def test_disabled_policy_generates_no_alerts(self):
        self.policy.enabled = False
        status = make_status(battery={"left": {"percentage": 5, "charging": False}, "right": {"percentage": 5, "charging": False}})
        self.assertEqual(len(self.policy.evaluate(status)), 0)

    def test_send_test_notification_dispatches_event(self):
        event = self.policy.send_test_notification("realme Buds T310")
        self.assertEqual(event.component, "test")
        self.dispatcher.send.assert_called_once_with(event)


class ServiceRunnerNotificationTests(unittest.TestCase):
    def test_service_runner_triggers_on_notification(self):
        notifications = []
        dispatcher = MagicMock(spec=NotificationDispatcher)
        policy = BatteryNotificationPolicy(dispatcher=dispatcher)

        controller = MagicMock()
        status = make_status(battery={"left": {"percentage": 18, "charging": False}, "right": {"percentage": 80, "charging": False}})
        snapshot = ControllerSnapshot(
            status=status,
            feature_switches={},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=1,
        )

        runner = BudsServiceRunner(
            controller,
            notification_policy=policy,
            on_notification=notifications.append,
        )
        runner._publish_snapshot(snapshot)

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].percentage, 18)
        dispatcher.send.assert_called_once()


class BridgeNotificationCommandTests(unittest.TestCase):
    def test_bridge_notification_commands(self):
        emitted = []
        controller = MagicMock()
        controller.snapshot.return_value = ControllerSnapshot(
            status=make_status(),
            feature_switches={},
            session_connected=True,
            advertised_event_codes=(),
            notification_event_codes=(),
            ignored_frames=0,
            reconnect_count=0,
            generation=1,
        )
        bridge = BudsFrontendBridge(emitted.append, controller=controller)

        status_res = bridge.execute("notify_status")
        self.assertTrue(status_res["ok"])
        self.assertTrue(status_res["result"]["enabled"])
        self.assertEqual(status_res["result"]["thresholds"]["warning"], 20)

        disable_res = bridge.execute("set_notify", {"enabled": False})
        self.assertTrue(disable_res["ok"])
        self.assertFalse(disable_res["result"]["enabled"])
        self.assertFalse(bridge.runner.notification_policy.enabled)

        with patch("subprocess.Popen") as mock_popen:
            test_res = bridge.execute("test_notification")
            self.assertTrue(test_res["ok"])
            self.assertTrue(test_res["result"]["sent"])
            self.assertEqual(test_res["result"]["event"]["component"], "test")


if __name__ == "__main__":
    unittest.main()
