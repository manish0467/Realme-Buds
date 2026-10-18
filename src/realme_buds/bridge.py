from __future__ import annotations

import re

from collections.abc import Callable, Mapping
from collections import deque
from threading import Event
from typing import TypeAlias

from .availability import Availability
from .controller import BudsController
from .locator import AcousticLocator
from .models import ControllerSnapshot, ControlResult, EqControlResult
from .mpris import MprisManager
from .notifications import NotificationEvent
from .profiles import compatibility_for_product, profile_for_product
from .report import build_snapshot_report, write_report
from .service import BudsServiceRunner, ServiceState
from .timing import AncRequestError

JsonObject: TypeAlias = dict[str, object]
Dispatch: TypeAlias = Callable[[Callable[[], None]], None]

SCHEMA_VERSION = 1


def serialize_snapshot(snapshot: ControllerSnapshot) -> JsonObject:
    """Return the stable, address-free snapshot exposed to frontends."""
    profile = profile_for_product(snapshot.status.product_id) if snapshot.status else None
    capabilities = set(profile.capabilities) if profile else set()
    capabilities.update(snapshot.feature_switches)
    return {
        "status": snapshot.status.to_dict() if snapshot.status is not None else None,
        "compatibility": compatibility_for_product(
            snapshot.status.product_id if snapshot.status else None
        ),
        "capabilities": sorted(capabilities),
        "anc_modes": sorted(profile.anc.write_indices) if profile and profile.verified else [],
        "eq": snapshot.eq_status.to_dict() if snapshot.eq_status else None,
        "eq_write_verified": bool(
            profile and profile.verified and profile.eq and profile.eq.write_verified
        ),
        "custom_eq_write_verified": bool(
            profile and profile.verified and profile.eq and profile.eq.custom_write_verified
        ),
        "feature_switches": dict(snapshot.feature_switches),
        "session_connected": snapshot.session_connected,
        "advertised_event_codes": list(snapshot.advertised_event_codes),
        "notification_event_codes": list(snapshot.notification_event_codes),
        "ignored_frames": snapshot.ignored_frames,
        "reconnect_count": snapshot.reconnect_count,
        "generation": snapshot.generation,
        "gestures": snapshot.gestures.to_dict() if snapshot.gestures else None,
    }


class BudsFrontendBridge:
    """Versioned frontend contract over one serialized controller."""

    def __init__(
        self,
        emit: Callable[[JsonObject], None],
        *,
        controller: BudsController | None = None,
        dispatch: Dispatch | None = None,
        availability: Availability | None = None,
        poll_interval: float = 0.5,
    ) -> None:
        self.controller = controller or BudsController()
        self.emit = emit
        self.dispatch = dispatch or (lambda callback: callback())
        self._recent_errors: deque[str] = deque(maxlen=12)
        self.mpris_manager = MprisManager(enabled=True)
        self.locator = AcousticLocator(default_address=self.controller.address)
        self._last_charging_state: bool | None = None
        self.runner = BudsServiceRunner(
            self.controller,
            availability=availability,
            poll_interval=poll_interval,
            on_state=self._on_state,
            on_snapshot=self._on_snapshot,
            on_notification=self._on_notification,
        )

    def _on_notification(self, event: NotificationEvent) -> None:
        self.dispatch(lambda: self.emit({"type": "notification", "notification": event.to_dict()}))

    def run(self, cancelled: Event) -> ControllerSnapshot:
        """Run the service lifecycle until the caller signals cancellation."""
        return self.runner.run(cancelled)

    def execute(
        self,
        command: str,
        parameters: Mapping[str, object] | None = None,
        *,
        request_id: str | int | None = None,
    ) -> JsonObject:
        """Execute one validated command and return a JSON-compatible response."""
        if parameters is not None and not isinstance(parameters, Mapping):
            return self._response(
                command,
                request_id,
                ok=False,
                error={"code": "invalid_parameters", "message": "parameters must be an object"},
            )
        params = dict(parameters or {})
        try:
            if command == "snapshot":
                self._require_parameters(command, params, set())
                result: object = serialize_snapshot(self.controller.snapshot())
            elif command == "refresh":
                self._require_parameters(command, params, set())
                snapshot = self.controller.refresh()
                result = serialize_snapshot(snapshot)
                self._on_snapshot(snapshot)
            elif command == "refresh_battery":
                self._require_parameters(command, params, set())
                battery = self.controller.refresh_battery()
                snapshot = self.controller.snapshot()
                result = {"battery": battery}
                self._on_snapshot(snapshot)
            elif command == "set_anc":
                self._require_parameters(command, params, {"mode"})
                mode = params["mode"]
                if not isinstance(mode, str) or not mode:
                    raise ValueError("set_anc parameter 'mode' must be a non-empty string")
                control, snapshot = self.controller.set_anc_with_snapshot(mode)
                result = self._serialize_control(control)
                self._on_snapshot(snapshot)
            elif command == "cycle_anc":
                self._require_parameters(command, params, set())
                control, snapshot = self.controller.cycle_anc_with_snapshot()
                result = self._serialize_control(control)
                self._on_snapshot(snapshot)
            elif command == "eq_status":
                self._require_parameters(command, params, set())
                result = self.controller.eq_status().to_dict()
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_eq":
                self._require_parameters(command, params, {"preset"})
                preset = params["preset"]
                if not isinstance(preset, str) or not preset:
                    raise ValueError("set_eq parameter 'preset' must be a non-empty string")
                control = self.controller.set_eq(preset)
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_custom_eq":
                self._require_parameters(command, params, {"entry_id", "gains_db"})
                entry_id, gains = params["entry_id"], params["gains_db"]
                if not isinstance(entry_id, int) or isinstance(entry_id, bool):
                    raise ValueError("set_custom_eq parameter 'entry_id' must be an integer")
                if not isinstance(gains, list) or any(
                    not isinstance(value, int) or isinstance(value, bool) for value in gains
                ):
                    raise ValueError("set_custom_eq parameter 'gains_db' must be an integer array")
                control = self.controller.set_custom_eq(entry_id, tuple(gains))
                self.controller.eq_status()
                result = self._serialize_eq_control(control)
                self._on_snapshot(self.controller.snapshot())
            elif command == "game_mode_status":
                self._require_parameters(command, params, set())
                result = {"game_mode": self.controller.game_mode_status()}
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_game_mode":
                self._require_parameters(command, params, {"enabled"})
                enabled = params["enabled"]
                if not isinstance(enabled, bool):
                    raise ValueError("set_game_mode parameter 'enabled' must be a boolean")
                success, snapshot = self.controller.set_game_mode_with_snapshot(enabled)
                result = {"game_mode": enabled, "success": success}
                self._on_snapshot(snapshot)
            elif command == "notify_status":
                self._require_parameters(command, params, set())
                result = self.runner.notification_policy.get_state()
            elif command == "set_notify":
                self._require_parameters(command, params, {"enabled"})
                enabled = params["enabled"]
                if not isinstance(enabled, bool):
                    raise ValueError("set_notify parameter 'enabled' must be a boolean")
                self.runner.notification_policy.enabled = enabled
                result = {"enabled": enabled}
            elif command == "test_notification":
                self._require_parameters(command, params, set())
                model_name = self.controller.snapshot().status.model if self.controller.snapshot().status else "realme Buds"
                event = self.runner.notification_policy.send_test_notification(model_name=model_name or "realme Buds")
                result = {"sent": True, "event": event.to_dict()}
            elif command == "wear_detection_status":
                self._require_parameters(command, params, set())
                result = {"wear_detection": self.controller.wear_detection_status()}
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_wear_detection":
                self._require_parameters(command, params, {"enabled"})
                enabled = params["enabled"]
                if not isinstance(enabled, bool):
                    raise ValueError("set_wear_detection parameter 'enabled' must be a boolean")
                success, snapshot = self.controller.set_wear_detection_with_snapshot(enabled)
                result = {"wear_detection": enabled, "success": success}
                self._on_snapshot(snapshot)
            elif command == "mpris_hook_status":
                self._require_parameters(command, params, set())
                result = self.mpris_manager.get_state()
            elif command == "set_mpris_hook":
                self._require_parameters(command, params, {"enabled"})
                enabled = params["enabled"]
                if not isinstance(enabled, bool):
                    raise ValueError("set_mpris_hook parameter 'enabled' must be a boolean")
                self.mpris_manager.enabled = enabled
                result = {"enabled": enabled}
            elif command == "multipoint_status":
                self._require_parameters(command, params, set())
                result = {"multipoint": self.controller.multipoint_status()}
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_multipoint":
                self._require_parameters(command, params, {"enabled"})
                enabled = params["enabled"]
                if not isinstance(enabled, bool):
                    raise ValueError("set_multipoint parameter 'enabled' must be a boolean")
                success, snapshot = self.controller.set_multipoint_with_snapshot(enabled)
                result = {"multipoint": enabled, "success": success}
                self._on_snapshot(snapshot)
            elif command == "ring_buds":
                target = str(params.get("target", "both")).lower()
                duration = float(params.get("duration", 30.0))
                result = self.locator.start(target=target, duration=duration, address=self.controller.address)
            elif command == "stop_ring_buds":
                self._require_parameters(command, params, set())
                result = self.locator.stop()
            elif command == "ring_status":
                self._require_parameters(command, params, set())
                result = self.locator.get_state()
            elif command == "gesture_status":
                self._require_parameters(command, params, set())
                result = self.controller.gesture_status().to_dict()
                self._on_snapshot(self.controller.snapshot())
            elif command == "set_gesture":
                self._require_parameters(command, params, {"side", "trigger", "action"})
                side = str(params["side"])
                trigger = str(params["trigger"])
                action = str(params["action"])
                success, snapshot = self.controller.set_gesture_with_snapshot(side, trigger, action)
                result = {"side": side, "trigger": trigger, "action": action, "success": success}
                self._on_snapshot(snapshot)
            elif command == "set_gesture_anc_modes":
                self._require_parameters(command, params, {"modes"})
                modes_raw = params["modes"]
                if not isinstance(modes_raw, list):
                    raise ValueError("set_gesture_anc_modes parameter 'modes' must be a list of strings")
                modes = tuple(str(m) for m in modes_raw)
                success, snapshot = self.controller.set_gesture_anc_modes(modes)
                result = {"modes": list(modes), "success": success}
                self._on_snapshot(snapshot)
            elif command == "save_diagnostic_report":
                self._require_parameters(command, params, {"path"})
                path = params["path"]
                if not isinstance(path, str) or not path:
                    raise ValueError(
                        "save_diagnostic_report parameter 'path' must be a non-empty string"
                    )
                report = build_snapshot_report(
                    self.controller.snapshot(), recent_errors=tuple(self._recent_errors)
                )
                filename = write_report(report, path)
                result = {"saved": True, "filename": filename}
            else:
                return self._response(
                    command,
                    request_id,
                    ok=False,
                    error={"code": "unknown_command", "message": f"unknown command: {command}"},
                )
        except ValueError as error:
            self._remember_error(error)
            return self._response(
                command,
                request_id,
                ok=False,
                error={"code": "invalid_parameters", "message": self._safe_error(error)},
            )
        except (OSError, RuntimeError) as error:
            self._remember_error(error)
            return self._response(
                command,
                request_id,
                ok=False,
                error={
                    "code": "command_failed",
                    "message": self._safe_error(error),
                    **({"timings_ms": dict(error.timings_ms)}
                       if isinstance(error, AncRequestError) else {}),
                },
            )
        return self._response(command, request_id, ok=True, result=result)

    def _on_state(self, state: ServiceState) -> None:
        if state.error:
            self._remember_error(RuntimeError(state.error))
        event: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "type": "connection",
            "connection": state.connection,
            "attempt": state.attempt,
            "retry_delay": state.retry_delay,
            "error": state.error,
        }
        self._dispatch_event(event)

    def _on_snapshot(self, snapshot: ControllerSnapshot) -> None:
        if snapshot.status and snapshot.status.battery:
            now_charging = any(
                b.get("charging", False)
                for k, b in snapshot.status.battery.items()
                if k in ("left", "right") and isinstance(b, dict)
            )
            if self._last_charging_state is not None:
                if now_charging and not self._last_charging_state:
                    self.mpris_manager.handle_wear_change(wearing=False)
                elif not now_charging and self._last_charging_state:
                    self.mpris_manager.handle_wear_change(wearing=True)
            self._last_charging_state = now_charging

        event: JsonObject = {
            "schema_version": SCHEMA_VERSION,
            "type": "snapshot",
            "snapshot": serialize_snapshot(snapshot),
        }
        self._dispatch_event(event)

    def _dispatch_event(self, event: JsonObject) -> None:
        self.dispatch(lambda: self.emit(event))

    def _response(
        self,
        command: str,
        request_id: str | int | None,
        *,
        ok: bool,
        result: object | None = None,
        error: JsonObject | None = None,
    ) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "command_response",
            "request_id": request_id,
            "command": command,
            "ok": ok,
            "result": result,
            "error": error,
        }

    def _require_parameters(
        self,
        command: str,
        parameters: Mapping[str, object],
        expected: set[str],
    ) -> None:
        supplied = set(parameters)
        if supplied != expected:
            raise ValueError(
                f"{command} requires parameters {sorted(expected)}; received {sorted(supplied)}"
            )

    def _safe_error(self, error: Exception) -> str:
        return re.sub(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", "[device]", str(error))

    def _remember_error(self, error: Exception) -> None:
        self._recent_errors.append(self._safe_error(error))

    @staticmethod
    def _serialize_control(result: ControlResult) -> JsonObject:
        return result.to_dict()

    @staticmethod
    def _serialize_eq_control(result: EqControlResult) -> JsonObject:
        return result.to_dict()
