import QtQuick
import Quickshell.Io
import "BridgeModel.js" as BridgeModel

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var state: BridgeModel.initialState()
  property int nextRequestId: 1
  property bool stopping: false
  property var lifecycleObservations: []

  function observeLifecycle(phase, productId) {
    lifecycleObservations = lifecycleObservations.concat([{
      phase: phase, unix_ms: Date.now(), product_id: productId || null
    }]).slice(-32)
  }

  readonly property string helperPath: localPath(Qt.resolvedUrl("realme-buds-bridge"))
  readonly property string connection: String(state.connection || "stopped")
  readonly property var snapshot: state.snapshot || null
  readonly property var lastResponse: state.lastResponse || null
  readonly property string lastError: String(state.lastError || "")

  function localPath(url) {
    var value = String(url || "")
    return value.indexOf("file://") === 0
      ? decodeURIComponent(value.slice(7)) : value
  }

  function startHelper() {
    restartTimer.stop()
    if (!stopping && helperPath && !helper.running) {
      helper.command = [helperPath]
      helper.running = true
    }
  }

  function restartHelper() {
    helper.running = false
    startHelper()
  }

  function reconnect() {
    startHelper()
  }

  onManifestChanged: {
    if (!stopping && !helper.running) {
      startHelper()
    }
  }

  Timer {
    id: restartTimer
    interval: 2000
    repeat: false
    onTriggered: {
      if (!root.stopping && !helper.running) {
        root.startHelper()
      }
    }
  }

  function handleLine(line) {
    var parsed = BridgeModel.parseLine(line)
    if (!parsed.ok) {
      state = {
        connection: state.connection,
        snapshot: state.snapshot,
        lastResponse: state.lastResponse,
        lastError: parsed.error
      }
      return
    }
    var previous = state
    state = BridgeModel.applyMessage(state, parsed.message)
    if (state.connection !== previous.connection)
      observeLifecycle("frontend_" + state.connection, null)
    var status = state.snapshot && state.snapshot.status
    var oldStatus = previous.snapshot && previous.snapshot.status
    if (status && state.snapshot.session_connected
        && (!oldStatus || !previous.snapshot.session_connected
            || oldStatus.product_id !== status.product_id))
      observeLifecycle("frontend_first_usable", status.product_id)
  }

  function request(command, parameters) {
    if (!helper.running) {
      startHelper()
      return null
    }
    var requestId = nextRequestId++
    helper.write(JSON.stringify({
      request_id: requestId,
      command: command,
      parameters: parameters === undefined ? {} : parameters
    }) + "\n")
    return requestId
  }

  function refresh() {
    return request("refresh", {})
  }

  function refreshBattery() {
    return request("refresh_battery", {})
  }

  function setAnc(mode) {
    return request("set_anc", { mode: String(mode || "") })
  }

  function cycleAnc() {
    return request("cycle_anc", {})
  }

  function setGameMode(enabled) {
    return request("set_game_mode", { enabled: !!enabled })
  }

  function queryGameMode() {
    return request("game_mode_status", {})
  }

  function notifyStatus() {
    return request("notify_status", {})
  }

  function setNotifications(enabled) {
    return request("set_notify", { enabled: !!enabled })
  }

  function testNotification() {
    return request("test_notification", {})
  }

  function setWearDetection(enabled) {
    return request("set_wear_detection", { enabled: !!enabled })
  }

  function queryWearDetection() {
    return request("wear_detection_status", {})
  }

  function setMprisHook(enabled) {
    return request("set_mpris_hook", { enabled: !!enabled })
  }

  function mprisHookStatus() {
    return request("mpris_hook_status", {})
  }

  function setMultipoint(enabled) {
    return request("set_multipoint", { enabled: !!enabled })
  }

  function queryMultipoint() {
    return request("multipoint_status", {})
  }

  function ringBuds(target) {
    return request("ring_buds", { target: String(target || "both") })
  }

  function stopRingBuds() {
    return request("stop_ring_buds", {})
  }

  function ringStatus() {
    return request("ring_status", {})
  }

  function eqStatus() {
    return request("eq_status", {})
  }

  function setEq(preset) {
    return request("set_eq", { preset: String(preset || "") })
  }

  function setCustomEq(entryId, gains) {
    return request("set_custom_eq", { entry_id: Number(entryId), gains_db: gains })
  }

  function saveDiagnosticReport(path) {
    return request("save_diagnostic_report", { path: String(path || "") })
  }

  function gestureStatus() {
    return request("gesture_status", {})
  }

  function setGesture(side, trigger, action) {
    return request("set_gesture", {
      side: String(side || ""),
      trigger: String(trigger || ""),
      action: String(action || "")
    })
  }

  function setGestureAncModes(modes) {
    return request("set_gesture_anc_modes", {
      modes: modes || []
    })
  }

  onHelperPathChanged: startHelper()

  Component.onCompleted: startHelper()

  Component.onDestruction: {
    stopping = true
    helper.running = false
  }

  Process {
    id: helper
    stdinEnabled: true
    command: []

    stdout: SplitParser {
      onRead: function(line) { root.handleLine(line) }
    }

    stderr: SplitParser {
      onRead: function(_line) {
        root.state = {
          connection: root.state.connection,
          snapshot: root.state.snapshot,
          lastResponse: root.state.lastResponse,
          lastError: "Backend process reported an error"
        }
      }
    }

    onExited: function(_exitCode) {
      if (!root.stopping) {
        root.state = {
          connection: "stopped",
          snapshot: root.state.snapshot,
          lastResponse: root.state.lastResponse,
          lastError: root.state.lastError || "Backend process stopped"
        }
        restartTimer.restart()
      }
    }
  }
}
