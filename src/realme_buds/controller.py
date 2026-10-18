from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import cast

from .lifecycle_trace import mark
from .api import BudsBackend
from .models import (
    ControllerSnapshot,
    ControlResult,
    EqControlResult,
    EqStatusResult,
    EventBatch,
    GestureStatusResult,
    StatusResult,
)
from .gestures import GestureConfig, GestureStore, default_gesture_config
from .profiles import profile_for_product
from .protocol import (
    FEATURE_GAME_MODE,
    FEATURE_LOW_LATENCY,
    FEATURE_MULTIPOINT,
    FEATURE_WEAR_DETECTION,
    VersionRecord,
)
from .session import OpoSession, UnsupportedProductError
from .timing import AncRequestError, PhaseTimer


class BudsController:
    """Serialized state/session owner for a future service or frontend."""

    def __init__(self, backend: BudsBackend | None = None, address: str | None = None,
                 *, reuse_session: bool = True) -> None:
        self.backend = backend or BudsBackend()
        self._selected_address = address
        self.address = address
        self.reuse_session = reuse_session
        self._lock = RLock()
        self._running = False
        self._session: OpoSession | None = None
        self._status: StatusResult | None = None
        self._feature_switches: dict[str, bool] = {}
        self._advertised_event_codes: tuple[int, ...] = ()
        self._notification_event_codes: tuple[int, ...] = ()
        self._ignored_frames = 0
        self._reconnect_count = 0
        self._generation = 0
        self._eq_status: EqStatusResult | None = None
        self._gesture_status: GestureStatusResult | None = None
        self._gesture_store = GestureStore()

    def start(self) -> ControllerSnapshot:
        with self._lock:
            if self._running:
                return self.snapshot()
            mark("controller_start")
            self.shutdown()
            try:
                self._session, self._status, batch = self.backend.start_session(self._selected_address)
                self.address = self._status.device.address
                self._advertised_event_codes = self._session.advertised_event_codes
                self._apply_batch(batch)
                if self._session is not None and hasattr(self._session, "query_gestures"):
                    try:
                        g_cfg = self._session.query_gestures()
                        self._update_gesture_status(g_cfg)
                    except Exception:
                        pass
                self._running = True
                mark("controller_usable")
            except UnsupportedProductError as error:
                self._status = StatusResult(
                    device=error.device,
                    product_id=error.product_id,
                    model=None,
                    remote_version=(),
                    firmware_version=None,
                    battery=None,
                    anc=None,
                    anc_level=None,
                )
                self.address = error.device.address
                self._running = True
                self._generation += 1
                return self.snapshot()
            except Exception:
                self.shutdown()
                raise
            return self.snapshot()

    def refresh(self) -> ControllerSnapshot:
        with self._lock:
            self.shutdown()
            return self.start()

    def request_battery(self) -> None:
        with self._lock:
            if self._session is not None and hasattr(self._session, "request_battery"):
                self._session.request_battery()

    def refresh_battery(self) -> dict[str, dict[str, int | bool]] | None:
        with self._lock:
            self._require_running()
            if self._session is None:
                return None
            battery = self._session.query_battery() if hasattr(self._session, "query_battery") else None
            if battery is not None and self._status is not None:
                new_battery = dict(battery)
                if self._status.battery and "case" in self._status.battery and "case" not in new_battery:
                    prev_case = self._status.battery["case"]
                    if isinstance(prev_case, dict) and prev_case.get("percentage", 0) > 0:
                        new_battery["case"] = {"percentage": prev_case["percentage"], "charging": False}
                self._status = replace(self._status, battery=new_battery)
                self._generation += 1
            return battery

    def set_anc(self, mode: str) -> ControlResult:
        timer = PhaseTimer()
        timings: dict[str, float] = {}
        with self._lock:
            timer.mark("controller_lock_wait")
            if self.reuse_session and self._running and mode in ("on", "off", "transparency"):
                return self._set_session_anc(mode, timer)
            try:
                self._close_session()
                timer.mark("monitor_close")
                try:
                    result = self.backend.set_anc(mode, self.address)
                    timings.update(result.timings_ms)
                    timer.mark("backend_request")
                    if self._status is not None:
                        self._status = replace(
                            self._status,
                            anc=result.anc,
                            anc_level=result.anc_level,
                        )
                    self._generation += 1
                except Exception as error:
                    if isinstance(error, AncRequestError):
                        timings.update(error.timings_ms)
                    timer.mark("backend_request")
                    if self._running and self._status is not None:
                        try:
                            self._connect_session()
                        except Exception:
                            pass
                    timer.mark("monitor_recovery")
                    raise
                if self._running:
                    self._connect_session()
                timer.mark("monitor_resume")
            except (OSError, RuntimeError) as error:
                timer.mark("failed_controller_phase")
                raise AncRequestError(
                    str(error), {**timings, **timer.finish("controller_total")}
                ) from error
            return replace(
                result, timings_ms={**timings, **timer.finish("controller_total")}
            )

    def _set_session_anc(self, mode: str, timer: PhaseTimer) -> ControlResult:
        try:
            if self._session is None:
                self._connect_session()
            timer.mark("session_ready")
            result, batch = cast(OpoSession, self._session).set_anc(mode)
            self._apply_batch(batch)
            if self._status is not None:
                self._status = replace(self._status, anc=result.anc, anc_level=result.anc_level)
            self._generation += 1
            # No socket teardown, reauthentication, or subscription restoration.
            return replace(result, timings_ms={
                **result.timings_ms, **timer.finish("controller_total"),
            })
        except ValueError:
            # Profile/parameter rejection happens before transport I/O.
            raise
        except (OSError, RuntimeError) as error:
            # Never replay an uncertain write. Poll/service recovery can reopen
            # later, without delaying this failed command's response.
            self._close_session()
            if self._status is not None:
                self._status = replace(self._status, anc=None, anc_level=None)
            self._generation += 1
            timings = error.timings_ms if isinstance(error, AncRequestError) else {}
            raise AncRequestError(str(error), {
                **timings, **timer.finish("controller_total"),
            }) from error

    def set_anc_with_snapshot(self, mode: str) -> tuple[ControlResult, ControllerSnapshot]:
        """Capture verified state before a poll can start monitoring recovery."""
        timer = PhaseTimer()
        with self._lock:
            timer.mark("controller_lock_wait")
            result = self.set_anc(mode)
            snapshot = self.snapshot()
            return replace(result, timings_ms={
                **result.timings_ms, **timer.finish("controller_total"),
            }), snapshot

    @staticmethod
    def _next_anc_mode(current_mode: str | None, profile: object | None) -> str:
        candidates = ("off", "transparency", "on")
        if profile and hasattr(profile, "anc") and hasattr(profile.anc, "write_indices"):
            modes = [m for m in candidates if m in profile.anc.write_indices]
        else:
            modes = list(candidates)
        if not modes:
            modes = list(candidates)

        if current_mode in modes:
            idx = modes.index(current_mode)
            return modes[(idx + 1) % len(modes)]
        elif current_mode in ("light", "medium", "deep", "smart"):
            return "off" if "off" in modes else modes[0]
        else:
            return "transparency" if "transparency" in modes else modes[0]

    def cycle_anc(self) -> ControlResult:
        with self._lock:
            product_id = self._status.product_id if self._status else None
            profile = profile_for_product(product_id)
            current_mode = self._status.anc if self._status else None
            next_mode = self._next_anc_mode(current_mode, profile)
            return self.set_anc(next_mode)

    def cycle_anc_with_snapshot(self) -> tuple[ControlResult, ControllerSnapshot]:
        timer = PhaseTimer()
        with self._lock:
            timer.mark("controller_lock_wait")
            result = self.cycle_anc()
            snapshot = self.snapshot()
            return replace(result, timings_ms={
                **result.timings_ms, **timer.finish("controller_total"),
            }), snapshot

    def eq_status(self) -> EqStatusResult:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            result, batch = cast(OpoSession, self._session).eq_status()
            self._apply_batch(batch)
            self._eq_status = result
            self._generation += 1
            return result

    def set_eq(self, preset: str) -> EqControlResult:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            try:
                result, batch = cast(OpoSession, self._session).set_eq(preset)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def set_custom_eq(self, entry_id: int, gains_db: tuple[int, ...]) -> EqControlResult:
        with self._lock:
            self._require_running()
            if self._session is None:
                self.refresh()
            try:
                result, batch = cast(OpoSession, self._session).set_custom_eq(entry_id, gains_db)
            except ValueError:
                raise
            except (OSError, RuntimeError):
                self._close_session()
                self._eq_status = None
                self._generation += 1
                raise
            self._apply_batch(batch)
            self._eq_status = None
            self._generation += 1
            return result

    def query_feature_switches(self) -> dict[str, bool]:
        with self._lock:
            self._require_running()
            if self._session is None:
                return dict(self._feature_switches)
            switches = cast(OpoSession, self._session).query_feature_switches()
            self._feature_switches.update(switches)
            self._generation += 1
            return dict(self._feature_switches)

    def set_feature_switch(self, feature: int | str, enabled: bool) -> bool:
        with self._lock:
            self._require_running()
            if self._session is None:
                raise RuntimeError("session is not connected")
            success, batch = cast(OpoSession, self._session).set_feature_switch(feature, enabled)
            self._apply_batch(batch)
            return success

    def game_mode_status(self) -> bool:
        with self._lock:
            switches = self.query_feature_switches()
            return switches.get("game_mode", switches.get("low_latency", False))

    def set_game_mode(self, enabled: bool) -> bool:
        with self._lock:
            self._require_running()
            if self._session is None:
                raise RuntimeError("session is not connected")
            success = False
            for fid in (FEATURE_GAME_MODE, FEATURE_LOW_LATENCY):
                try:
                    s, batch = cast(OpoSession, self._session).set_feature_switch(fid, enabled)
                    self._apply_batch(batch)
                    if s:
                        success = True
                        break
                except Exception:
                    pass
            self._generation += 1
            return success

    def set_game_mode_with_snapshot(self, enabled: bool) -> tuple[bool, ControllerSnapshot]:
        with self._lock:
            success = self.set_game_mode(enabled)
            snapshot = self.snapshot()
            return success, snapshot

    def wear_detection_status(self) -> bool:
        with self._lock:
            switches = self.query_feature_switches()
            return switches.get("wear_detection", False)

    def set_wear_detection(self, enabled: bool) -> bool:
        with self._lock:
            self._require_running()
            if self._session is None:
                raise RuntimeError("session is not connected")
            try:
                success, batch = cast(OpoSession, self._session).set_feature_switch(
                    FEATURE_WEAR_DETECTION, enabled
                )
                self._apply_batch(batch)
            except Exception:
                success = False
            self._generation += 1
            return success

    def set_wear_detection_with_snapshot(self, enabled: bool) -> tuple[bool, ControllerSnapshot]:
        with self._lock:
            success = self.set_wear_detection(enabled)
            snapshot = self.snapshot()
            return success, snapshot

    def multipoint_status(self) -> bool:
        with self._lock:
            switches = self.query_feature_switches()
            return switches.get("multipoint", False)

    def set_multipoint(self, enabled: bool) -> bool:
        with self._lock:
            self._require_running()
            if self._session is None:
                raise RuntimeError("session is not connected")
            try:
                success, batch = cast(OpoSession, self._session).set_feature_switch(
                    FEATURE_MULTIPOINT, enabled
                )
                self._apply_batch(batch)
            except Exception:
                success = False
            self._generation += 1
            return success

    def set_multipoint_with_snapshot(self, enabled: bool) -> tuple[bool, ControllerSnapshot]:
        with self._lock:
            success = self.set_multipoint(enabled)
            snapshot = self.snapshot()
            return success, snapshot

    def _update_gesture_status(self, config: GestureConfig) -> None:
        data = config.to_dict()
        self._gesture_status = GestureStatusResult(
            left=data["left"],
            right=data["right"],
            actions=tuple(data["actions"]),
            long_press_anc_modes=tuple(data["long_press_anc_modes"]),
            items=tuple(data["items"]),
        )

    def gesture_status(self) -> GestureStatusResult:
        with self._lock:
            self._require_running()
            if self._gesture_status is None:
                if self._session is not None and hasattr(self._session, "query_gestures"):
                    config = cast(OpoSession, self._session).query_gestures()
                    self._update_gesture_status(config)
                else:
                    self._update_gesture_status(self._gesture_store.load())
            return cast(GestureStatusResult, self._gesture_status)

    def set_gesture(self, side: str, trigger: str, action: str) -> bool:
        with self._lock:
            self._require_running()
            if self._session is not None and hasattr(self._session, "set_gesture"):
                success, batch = cast(OpoSession, self._session).set_gesture(side, trigger, action)
                self._apply_batch(batch)
            else:
                config = self._gesture_store.load().with_action(side, trigger, action)
                self._gesture_store.save(config)
                self._update_gesture_status(config)
                success = True
            self._generation += 1
            return success

    def set_gesture_with_snapshot(self, side: str, trigger: str, action: str) -> tuple[bool, ControllerSnapshot]:
        with self._lock:
            success = self.set_gesture(side, trigger, action)
            return success, self.snapshot()

    def set_gesture_anc_modes(self, modes: tuple[str, ...]) -> tuple[bool, ControllerSnapshot]:
        with self._lock:
            self._require_running()
            if self._session is not None and hasattr(self._session, "set_gesture_anc_modes"):
                success, batch = cast(OpoSession, self._session).set_gesture_anc_modes(modes)
                self._apply_batch(batch)
            else:
                config = self._gesture_store.load().with_anc_modes(modes)
                self._gesture_store.save(config)
                self._update_gesture_status(config)
                success = True
            self._generation += 1
            return success, self.snapshot()

    def poll(self, wait: float = 0.2) -> ControllerSnapshot:
        with self._lock:
            self._require_running()
            if self._session is None:
                if self._status is not None and profile_for_product(
                    self._status.product_id
                ) is None:
                    return self.snapshot()
                return self.refresh()
            try:
                batch = cast(OpoSession, self._session).poll(wait)
            except OSError:
                self._reconnect_count += 1
                return self.refresh()
            else:
                self._apply_batch(batch)
            return self.snapshot()

    def shutdown(self) -> ControllerSnapshot:
        with self._lock:
            self._running = False
            self._close_session()
            self.address = self._selected_address
            self._status = None
            self._feature_switches.clear()
            self._advertised_event_codes = ()
            self._notification_event_codes = ()
            self._ignored_frames = 0
            self._eq_status = None
            self._gesture_status = None
            self._generation += 1
            return self.snapshot()

    def snapshot(self) -> ControllerSnapshot:
        with self._lock:
            return ControllerSnapshot(
                status=self._status,
                feature_switches=dict(self._feature_switches),
                session_connected=self._session is not None,
                advertised_event_codes=self._advertised_event_codes,
                notification_event_codes=self._notification_event_codes,
                ignored_frames=self._ignored_frames,
                reconnect_count=self._reconnect_count,
                generation=self._generation,
                eq_status=self._eq_status,
                gestures=self._gesture_status,
            )

    def _connect_session(self) -> None:
        if self._status is None:
            raise RuntimeError("controller has no device status")
        session = self.backend.open_session(self.address, status=self._status)
        session.__enter__()
        try:
            batch = session.authenticate_and_subscribe()
        except Exception:
            session.__exit__(None, None, None)
            raise
        self._session = session
        self._advertised_event_codes = session.advertised_event_codes
        self._apply_batch(batch)

    def _close_session(self) -> None:
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None

    def _apply_batch(self, batch: EventBatch) -> None:
        self._ignored_frames += batch.ignored_frames
        for event in batch.events:
            if event.kind == "battery" and self._status is not None:
                new_battery = dict(cast(dict[str, dict[str, int | bool]], event.data))
                if self._status.battery and "case" in self._status.battery and "case" not in new_battery:
                    prev_case = self._status.battery["case"]
                    if isinstance(prev_case, dict) and prev_case.get("percentage", 0) > 0:
                        new_battery["case"] = {"percentage": prev_case["percentage"], "charging": False}
                self._status = replace(
                    self._status,
                    battery=new_battery,
                )
            elif event.kind == "anc" and self._status is not None:
                self._status = replace(
                    self._status,
                    anc=cast(str | None, event.data.get("mode")),
                    anc_level=cast(str | None, event.data.get("level")),
                )
            elif event.kind == "firmware" and self._status is not None:
                self._status = replace(self._status,
                    firmware_version=cast(str | None, event.data["version"]),
                    remote_version=tuple(VersionRecord(**record) for record in event.data["records"]))
            elif event.kind == "feature_switches":
                self._feature_switches.update(
                    {key: value for key, value in event.data.items() if isinstance(value, bool)}
                )
            elif event.kind == "notification":
                code = event.data.get("event_code")
                if isinstance(code, int):
                    self._notification_event_codes = (
                        self._notification_event_codes + (code,)
                    )[-32:]
            elif event.kind == "eq_changed":
                # The next consumer read must fetch complete state, including
                # changes made by HeyMelody on the shared device.
                self._eq_status = None
            elif event.kind == "gestures":
                left = cast(dict[str, str], event.data.get("left", {}))
                right = cast(dict[str, str], event.data.get("right", {}))
                actions = tuple(cast(list[dict[str, object]], event.data.get("actions", [])))
                anc_modes = tuple(cast(list[str], event.data.get("long_press_anc_modes", ["anc", "transparency"])))
                items = tuple(cast(list[dict[str, object]], event.data.get("items", [])))
                self._gesture_status = GestureStatusResult(
                    left=left,
                    right=right,
                    actions=actions,
                    long_press_anc_modes=anc_modes,
                    items=items,
                )
        if batch.events:
            self._generation += 1

    def _require_running(self) -> None:
        if not self._running:
            raise RuntimeError("controller is not running")
