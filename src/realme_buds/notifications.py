from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

from .models import StatusResult


@dataclass(frozen=True)
class NotificationEvent:
    title: str
    message: str
    urgency: Literal["low", "normal", "critical"] = "normal"
    icon: str = "battery-low"
    component: str = "earbuds"
    percentage: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "message": self.message,
            "urgency": self.urgency,
            "icon": self.icon,
            "component": self.component,
            "percentage": self.percentage,
        }


@dataclass
class ComponentAlertState:
    warned: bool = False
    critical_warned: bool = False
    last_percentage: int | None = None
    was_charging: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "warned": self.warned,
            "critical_warned": self.critical_warned,
            "last_percentage": self.last_percentage,
            "was_charging": self.was_charging,
        }


class NotificationDispatcher:
    def __init__(self, notify_send_path: str | None = None, omarchy_path: str | None = None):
        self.notify_send_path = notify_send_path if notify_send_path is not None else shutil.which("notify-send")
        self.omarchy_path = omarchy_path if omarchy_path is not None else shutil.which("omarchy")

    def send(self, event: NotificationEvent) -> bool:
        if self.notify_send_path:
            try:
                subprocess.Popen(
                    [
                        self.notify_send_path,
                        "-a", "realme Buds Control",
                        "-u", event.urgency,
                        "-i", event.icon,
                        event.title,
                        event.message,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass
        if self.omarchy_path:
            try:
                subprocess.Popen(
                    [
                        self.omarchy_path,
                        "notification", "send",
                        "--app-name", "realme Buds Control",
                        "-u", event.urgency,
                        "-i", event.icon,
                        event.title,
                        event.message,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                pass
        return False


class BatteryNotificationPolicy:
    WARNING_THRESHOLD = 20
    CRITICAL_THRESHOLD = 10
    RECOVERY_THRESHOLD = 25

    def __init__(
        self,
        *,
        enabled: bool = True,
        dispatcher: NotificationDispatcher | None = None,
    ):
        self.enabled = enabled
        self.dispatcher = dispatcher or NotificationDispatcher()
        self.states: dict[str, ComponentAlertState] = {
            "left": ComponentAlertState(),
            "right": ComponentAlertState(),
            "case": ComponentAlertState(),
            "device": ComponentAlertState(),
        }

    def reset(self) -> None:
        for state in self.states.values():
            state.warned = False
            state.critical_warned = False
            state.last_percentage = None
            state.was_charging = False

    def evaluate(self, status: StatusResult | None) -> list[NotificationEvent]:
        if not self.enabled or status is None or not status.device.connected:
            return []

        model_name = status.model or status.device.name or "realme Buds"
        events: list[NotificationEvent] = []

        battery = status.battery
        if battery:
            left = battery.get("left")
            right = battery.get("right")
            case = battery.get("case")

            # Check for coalesced earbuds alert if both left and right are discharging
            left_event = self._evaluate_component("left", left)
            right_event = self._evaluate_component("right", right)

            if left_event and right_event and left_event.urgency == right_event.urgency:
                urgency = left_event.urgency
                min_pct = min(left_event.percentage, right_event.percentage)
                if urgency == "critical":
                    events.append(NotificationEvent(
                        title=f"{model_name} Battery Critical",
                        message=f"Earbuds battery is critically low ({min_pct}%). Please place in case.",
                        urgency="critical",
                        icon="battery-caution",
                        component="both",
                        percentage=min_pct,
                    ))
                else:
                    events.append(NotificationEvent(
                        title=f"{model_name} Low Battery",
                        message=f"Earbuds battery is low ({min_pct}%).",
                        urgency="normal",
                        icon="battery-low",
                        component="both",
                        percentage=min_pct,
                    ))
            else:
                if left_event:
                    events.append(self._format_event(model_name, "Left earbud", left_event))
                if right_event:
                    events.append(self._format_event(model_name, "Right earbud", right_event))

            case_event = self._evaluate_component("case", case)
            if case_event:
                events.append(self._format_event(model_name, "Charging case", case_event, is_case=True))
        elif status.device.battery is not None:
            dev_info = {"percentage": status.device.battery, "charging": False}
            dev_event = self._evaluate_component("device", dev_info)
            if dev_event:
                events.append(self._format_event(model_name, "Earbuds", dev_event))

        return events

    def _evaluate_component(
        self,
        component_name: str,
        info: dict[str, int | bool] | None,
    ) -> NotificationEvent | None:
        if not info:
            return None

        pct = info.get("percentage")
        if not isinstance(pct, int):
            return None

        charging = bool(info.get("charging", False))
        state = self.states.setdefault(component_name, ComponentAlertState())
        state.last_percentage = pct

        if charging:
            state.warned = False
            state.critical_warned = False
            state.was_charging = True
            return None

        if pct >= self.RECOVERY_THRESHOLD:
            state.warned = False
            state.critical_warned = False

        state.was_charging = False

        if pct <= self.CRITICAL_THRESHOLD:
            if not state.critical_warned:
                state.critical_warned = True
                state.warned = True
                return NotificationEvent(
                    title="",
                    message="",
                    urgency="critical",
                    icon="battery-caution",
                    component=component_name,
                    percentage=pct,
                )
        elif pct <= self.WARNING_THRESHOLD:
            if not state.warned:
                state.warned = True
                return NotificationEvent(
                    title="",
                    message="",
                    urgency="normal",
                    icon="battery-low",
                    component=component_name,
                    percentage=pct,
                )

        return None

    def _format_event(
        self,
        model_name: str,
        label: str,
        event: NotificationEvent,
        is_case: bool = False,
    ) -> NotificationEvent:
        if event.urgency == "critical":
            hint = "Please connect charger." if is_case else "Please place in case."
            return NotificationEvent(
                title=f"{model_name} Battery Critical",
                message=f"{label} battery is critically low ({event.percentage}%). {hint}",
                urgency="critical",
                icon="battery-caution",
                component=event.component,
                percentage=event.percentage,
            )
        return NotificationEvent(
            title=f"{model_name} Low Battery",
            message=f"{label} battery is low ({event.percentage}%).",
            urgency="normal",
            icon="battery-low",
            component=event.component,
            percentage=event.percentage,
        )

    def check_and_notify(self, status: StatusResult | None) -> list[NotificationEvent]:
        events = self.evaluate(status)
        for event in events:
            self.dispatcher.send(event)
        return events

    def send_test_notification(self, model_name: str = "realme Buds") -> NotificationEvent:
        event = NotificationEvent(
            title=f"{model_name} Control",
            message="Low battery alerts are active (20% warning, 10% critical).",
            urgency="normal",
            icon="battery-low",
            component="test",
            percentage=20,
        )
        self.dispatcher.send(event)
        return event

    def get_state(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "thresholds": {
                "warning": self.WARNING_THRESHOLD,
                "critical": self.CRITICAL_THRESHOLD,
                "recovery": self.RECOVERY_THRESHOLD,
            },
            "components": {k: v.to_dict() for k, v in self.states.items()},
        }
