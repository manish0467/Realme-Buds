import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs
import QtCore
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "BarModel.js" as BarModel

BarWidget {
  id: root
  moduleName: "realme-buds.control"

  readonly property var budsService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName) : null
  readonly property string connection: budsService
    ? String(budsService.connection || "stopped") : "unavailable"
  readonly property var snapshot: budsService ? budsService.snapshot : null
  readonly property var presentation: BarModel.presentation(connection, snapshot)
  readonly property var ancOptions: BarModel.ancModes(snapshot)
  readonly property string currentAncMode: BarModel.currentAncMode(snapshot)
  readonly property var lastResponse: budsService ? budsService.lastResponse : null
  readonly property var eqStatus: snapshot ? snapshot.eq : null
  readonly property var eqPresets: BarModel.eqPresets(snapshot)
  readonly property var customEqEntries: BarModel.customEqEntries(snapshot)
  readonly property string compatibilityKind: BarModel.compatibility(snapshot)
  readonly property string compatibilityLabel: BarModel.compatibilityLabel(snapshot)
  readonly property string reportActionLabel: BarModel.reportActionLabel(snapshot)
  readonly property string reportIssueUrl: BarModel.compatibilityIssueUrl(snapshot)
  readonly property string reportSubmissionActionLabel: experimentalDevice
    ? "Submit compatibility report on GitHub" : "Open GitHub issue"
  readonly property string reportDialogSelectedFile: String(reportFileDialog.selectedFile || "")
  readonly property bool experimentalDevice: compatibilityKind === "experimental"
  readonly property bool communityTestedDevice: compatibilityKind === "community_tested"
  readonly property bool compatibilityNoticeShown: experimentalDevice || communityTestedDevice
  readonly property bool reportAvailable: connection === "connected"
    && snapshot !== null && snapshot.status !== null
  readonly property bool reportActionShown: reportAvailable && !reportDetailsOpen
  readonly property var selectedCustom: customEqEntries.length > 0
    ? customEqEntries[Math.max(0, Math.min(customSlotIndex, customEqEntries.length - 1))] : null
  readonly property bool eqAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("eq") !== -1)
  readonly property bool gameModeAvailable: !!(snapshot && snapshot.capabilities
    && (snapshot.capabilities.indexOf("game_mode") !== -1
        || snapshot.capabilities.indexOf("low_latency") !== -1))
  readonly property bool gameModeEnabled: !!(snapshot && snapshot.feature_switches
    && (snapshot.feature_switches.game_mode === true
        || snapshot.feature_switches.low_latency === true))
  readonly property bool wearDetectionAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("wear_detection") !== -1)
  readonly property bool wearDetectionEnabled: !!(snapshot && snapshot.feature_switches
    && snapshot.feature_switches.wear_detection === true)
  readonly property bool multipointAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("multipoint") !== -1)
  readonly property bool multipointEnabled: !!(snapshot && snapshot.feature_switches
    && snapshot.feature_switches.multipoint === true)
  property bool notificationsEnabled: true
  property bool mprisHookEnabled: true
  property bool locatorRinging: false
  property string locatorTarget: ""
  property bool locatorCardOpen: false
  property string pendingRingTarget: ""
  readonly property bool gestureAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("gestures") !== -1)
  readonly property var gesturesData: BarModel.gestures(snapshot)
  property bool gestureCardOpen: false
  readonly property bool useTwoColumnLayout: eqAvailable
    && popup.availableCardWidth >= Style.space(560)
  readonly property int panelHeight: popup.contentHeight

  readonly property bool lifecycleUsable: connection === "connected"
    && snapshot !== null && snapshot.session_connected === true
    && snapshot.status !== null && ancOptions.length > 0
  onLifecycleUsableChanged: {
    if (budsService && typeof budsService.observeLifecycle === "function")
      budsService.observeLifecycle(lifecycleUsable ? "ui_usable" : "ui_unavailable",
        snapshot && snapshot.status ? snapshot.status.product_id : null)
  }

  property bool popupOpen: false
  property int pendingRequestId: -1
  property string pendingMode: ""
  property string outcome: ""
  property string pendingKind: ""
  property int customSlotIndex: 0
  property bool customSelectionDirty: false
  property bool reportDetailsOpen: false
  property bool reportSaved: false
  property string proposedReportFilename: ""
  property string pendingReportLocation: ""
  property string savedReportFilename: ""
  property string savedReportLocation: ""

  onCompatibilityKindChanged: {
    reportDetailsOpen = false
    clearReportResult()
  }

  function syncCustomSlotFromEq() {
    if (!eqStatus || !customEqEntries.length) return
    for (var i = 0; i < customEqEntries.length; i++) {
      if (customEqEntries[i].eq_id === eqStatus.current_id) {
        customSlotIndex = i
        return
      }
    }
    customSlotIndex = 0
  }

  function selectCustomSlot(index) {
    if (index < 0 || index >= customEqEntries.length) return
    customSlotIndex = index
    customSelectionDirty = true
  }

  onEqStatusChanged: {
    if (!customSelectionDirty) syncCustomSlotFromEq()
  }
  property bool hoverExpanded: false
  readonly property bool batteryExpanded: !vertical && presentation.label !== ""
    && (hoverExpanded || popupOpen)

  onPopupOpenChanged: {
    if (popupOpen) {
      customSelectionDirty = false
      syncCustomSlotFromEq()
      collapseTimer.stop()
      if (bar) bar.hideTooltip(root)
      if (budsService && connection === "connected") {
        budsService.refreshBattery()
      }
      if (budsService && connection === "connected" && snapshot
          && snapshot.capabilities && snapshot.capabilities.indexOf("eq") !== -1
          && pendingRequestId < 0) {
        var requestId = budsService.eqStatus()
        if (requestId !== null) {
          pendingRequestId = requestId
          pendingKind = "eq_status"
        }
      }
    } else if (!hitArea.containsMouse) {
      collapseTimer.restart()
    }
  }

  readonly property bool opened: popupOpen

  function open() { popupOpen = true }
  function close() { popupOpen = false }
  function togglePanel() { popupOpen = !popupOpen }


  function selectAnc(mode) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var supported = false
    for (var i = 0; i < ancOptions.length; i++)
      if (ancOptions[i].value === mode) supported = true
    if (!supported) return

    var requestId = budsService.setAnc(mode)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = mode
    pendingKind = "anc"
    outcome = ""
  }

  function cycleAnc() {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.cycleAnc()
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = "cycle"
    pendingKind = "anc"
    outcome = ""
  }

  function toggleGameMode() {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var nextState = !gameModeEnabled
    var requestId = budsService.setGameMode(nextState)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = nextState ? "game_on" : "game_off"
    pendingKind = "game_mode"
    outcome = ""
  }

  function toggleNotifications() {
    notificationsEnabled = !notificationsEnabled
    if (budsService) budsService.setNotifications(notificationsEnabled)
  }

  function testNotification() {
    if (budsService) budsService.testNotification()
  }

  function toggleWearDetection() {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var nextState = !wearDetectionEnabled
    var requestId = budsService.setWearDetection(nextState)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = nextState ? "wear_on" : "wear_off"
    pendingKind = "wear_detection"
    outcome = ""
  }

  function toggleMprisHook() {
    mprisHookEnabled = !mprisHookEnabled
    if (budsService) budsService.setMprisHook(mprisHookEnabled)
  }

  function toggleMultipoint() {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var nextState = !multipointEnabled
    var requestId = budsService.setMultipoint(nextState)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = nextState ? "dual_on" : "dual_off"
    pendingKind = "multipoint"
    outcome = ""
  }

  function ringBuds(target) {
    if (!budsService) return
    locatorTarget = String(target || "both")
    locatorRinging = true
    budsService.ringBuds(locatorTarget)
  }

  function stopRingBuds() {
    if (!budsService) return
    locatorRinging = false
    locatorTarget = ""
    budsService.stopRingBuds()
  }

  function toggleLocatorCard() {
    locatorCardOpen = !locatorCardOpen
    if (!locatorCardOpen) {
      pendingRingTarget = ""
      if (locatorRinging) {
        stopRingBuds()
      }
    }
  }

  function setGesture(side, trigger, action) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setGesture(side, trigger, action)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = side + "_" + trigger
    pendingKind = "gesture"
    outcome = ""
  }

  function setGestureAncModes(modes) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setGestureAncModes(modes)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = "anc_modes"
    pendingKind = "gesture"
    outcome = ""
  }

  function toggleGestureCard() {
    gestureCardOpen = !gestureCardOpen
  }

  function selectEq(value) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setEq(value)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "eq"
    pendingMode = String(value)
    outcome = ""
  }

  function applyCustomEq() {
    if (!selectedCustom || !budsService || pendingRequestId >= 0) return
    var gains = []
    for (var i = 0; i < bandRepeater.count; i++)
      gains.push(Number(bandRepeater.itemAt(i).gainValue))
    var customName = (customNameField && customNameField.text.trim())
      ? customNameField.text.trim() : selectedCustom.name
    var requestId = budsService.setCustomEq(selectedCustom.eq_id, gains, customName)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "custom_eq"
    pendingMode = customName
    outcome = ""
  }

  function addCustomEq(name) {
    if (!budsService || pendingRequestId >= 0) return
    var nextNum = root.customEqEntries.length + 1
    var presetName = (name && String(name).trim()) ? String(name).trim() : ("Custom " + nextNum)
    var requestId = budsService.addCustomEq(presetName, [0, 0, 0, 0, 0, 0])
    if (requestId !== null) {
      pendingRequestId = requestId
      pendingKind = "add_custom_eq"
      outcome = ""
    }
  }

  function deleteCustomEq(entryId) {
    if (!budsService || pendingRequestId >= 0) return
    var requestId = budsService.deleteCustomEq(entryId)
    if (requestId !== null) {
      pendingRequestId = requestId
      pendingKind = "delete_custom_eq"
    }
  }

  function saveDiagnosticReport(fileUrl) {
    if (!budsService || pendingRequestId >= 0) return
    var destination = String(fileUrl || "")
    var requestId = budsService.saveDiagnosticReport(destination)
    if (requestId === null) { outcome = "Could not start report"; return }
    pendingRequestId = requestId
    pendingKind = "diagnostic_report"
    pendingMode = ""
    pendingReportLocation = destination
    outcome = ""
    clearReportResult()
  }

  function clearReportResult() {
    reportSaved = false
    savedReportFilename = ""
    savedReportLocation = ""
  }

  function prepareReportFileDialog() {
    clearReportResult()
    outcome = ""
    proposedReportFilename = BarModel.reportFilename(snapshot, new Date())
    var folder = String(reportFileDialog.currentFolder || "")
    reportFileDialog.selectedFile = folder + (folder.endsWith("/") ? "" : "/")
      + proposedReportFilename
  }

  function openReportFileDialog() {
    prepareReportFileDialog()
    reportFileDialog.open()
  }

  function acceptReportFile(fileUrl) {
    var selected = String(fileUrl || "")
    var textDestination = BarModel.textReportUrl(selected)
    if (selected !== textDestination) {
      reportFileDialog.selectedFile = textDestination
      Qt.callLater(function() { reportFileDialog.open() })
      return
    }
    saveDiagnosticReport(textDestination)
  }

  function cancelDiagnosticReport() {
    clearReportResult()
    pendingReportLocation = ""
    outcome = ""
  }

  function openReportIssue() {
    Qt.openUrlExternally(reportIssueUrl)
  }

  onLastResponseChanged: {
    var response = lastResponse
    if (!response || Number(response.request_id) !== pendingRequestId) return
    pendingRequestId = -1
    pendingMode = ""
    var completedKind = pendingKind
    pendingKind = ""
    if (completedKind === "diagnostic_report") {
      if (response.ok === true) {
        reportSaved = true
        savedReportFilename = response.result && response.result.filename
          ? String(response.result.filename) : "diagnostic report"
        savedReportLocation = BarModel.reportLocationLabel(
          pendingReportLocation, savedReportFilename,
          StandardPaths.writableLocation(StandardPaths.HomeLocation))
        outcome = ""
      } else {
        clearReportResult()
        outcome = response.error && response.error.message
          ? String(response.error.message) : "Diagnostic report could not be saved"
      }
      pendingReportLocation = ""
      return
    }
    if (response.ok === true && (completedKind === "eq_status" || completedKind === "eq")) {
      customSelectionDirty = false
      syncCustomSlotFromEq()
    }
    if (response.ok === true && completedKind === "add_custom_eq") {
      var newId = (response.result && response.result.eq_id !== undefined) ? response.result.eq_id : -1
      var targetIdx = -1
      if (newId !== -1) {
        for (var i = 0; i < root.customEqEntries.length; i++) {
          if (root.customEqEntries[i].eq_id === newId) {
            targetIdx = i
            break
          }
        }
      }
      if (targetIdx >= 0) {
        root.customSlotIndex = targetIdx
      } else {
        root.customSlotIndex = Math.max(0, root.customEqEntries.length - 1)
      }
      root.customSelectionDirty = true
      outcome = "Created " + (response.result && response.result.name ? response.result.name : "custom EQ")
      return
    }
    if (response.ok === true && completedKind === "delete_custom_eq") {
      root.customSlotIndex = Math.max(0, Math.min(root.customSlotIndex, root.customEqEntries.length - 1))
      root.customSelectionDirty = true
      outcome = "Custom EQ deleted"
      return
    }
    if (response.ok === true && completedKind === "custom_eq") {
      root.customSelectionDirty = true
      outcome = "Custom EQ applied"
      return
    }
    if (response.ok === true && completedKind === "gesture") {
      outcome = "Gesture updated"
    } else if (response.ok === true && response.result && response.result.verified === true) {
      outcome = "Verified on earbuds"
    } else if (response.ok === true && completedKind === "eq_status") {
      outcome = ""
    } else {
      var detail = response.error && response.error.message
        ? String(response.error.message) : "Change could not be verified"
      outcome = detail
    }
  }

  visible: true
  implicitWidth: icon.implicitWidth + Style.space(14)
    + (batteryExpanded ? Style.space(5) + batteryLabel.implicitWidth : 0)
  implicitHeight: barSize

  Behavior on implicitWidth {
    NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
  }

  Timer {
    id: collapseTimer
    interval: 300
    onTriggered: if (!hitArea.containsMouse && !root.popupOpen) root.hoverExpanded = false
  }

  Item {
    anchors.fill: parent
    anchors.leftMargin: Style.space(7)
    anchors.rightMargin: Style.space(7)
    clip: true

    Text {
      id: icon
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: root.presentation.icon
      color: root.presentation.connected
        ? root.bar.barForeground : Qt.darker(root.bar.barForeground, 1.5)
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.body
    }

    Text {
      id: batteryLabel
      anchors.left: icon.right
      anchors.leftMargin: Style.space(5)
      anchors.verticalCenter: parent.verticalCenter
      visible: !root.vertical && text !== ""
      textFormat: Text.PlainText
      text: root.presentation.label
      color: root.bar.barForeground
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
  }

  MouseArea {
    id: hitArea
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    cursorShape: Qt.PointingHandCursor
    onClicked: {
      if (root.connection === "stopped" || root.connection === "unavailable") {
        if (root.budsService && typeof root.budsService.startHelper === "function") {
          root.budsService.startHelper()
        }
      }
      root.popupOpen = !root.popupOpen
    }
    onEntered: {
      collapseTimer.stop()
      root.hoverExpanded = true
      if (root.bar && !root.popupOpen) root.bar.showTooltip(root, root.presentation.tooltip)
    }
    onExited: {
      collapseTimer.restart()
      if (root.bar) root.bar.hideTooltip(root)
    }
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(root.useTwoColumnLayout
      ? Style.space(600) : Style.space(320))
    contentHeight: popup.fittedContentHeight(panelContent.implicitHeight)

    Flickable {
      id: panelScroll
      anchors.fill: parent
      contentWidth: width
      contentHeight: panelContent.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.VerticalFlick
      Controls.ScrollBar.vertical: Controls.ScrollBar {}

      function reveal(item) {
        var top = item.mapToItem(panelContent, 0, 0).y
        if (top < contentY) contentY = top
        else if (top + item.height > contentY + height)
          contentY = top + item.height - height
      }

      Column {
        id: panelContent
        width: panelScroll.width
        spacing: Style.space(12)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.snapshot && root.snapshot.status && root.snapshot.status.model
            ? String(root.snapshot.status.model) : "realme earbuds"
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: true
          wrapMode: Text.Wrap
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.presentation.label || BarModel.titleCase(root.connection)
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
        Item {
          id: controlSections
          width: parent.width
          height: implicitHeight
          implicitHeight: root.useTwoColumnLayout
            ? Math.max(noiseColumn.implicitHeight, eqColumn.implicitHeight)
            : noiseColumn.implicitHeight
              + (eqColumn.visible ? Style.space(14) + eqColumn.implicitHeight : 0)

          Column {
            id: noiseColumn
            x: 0
            y: 0
            width: root.useTwoColumnLayout
              ? (controlSections.width - Style.space(16)) / 2 : controlSections.width
            spacing: Style.space(8)

            Repeater {
              model: BarModel.ancGroups(root.snapshot)

              delegate: Column {
                id: section
                required property var modelData
                width: noiseColumn.width
                spacing: Style.space(5)

                Text {
                  width: parent.width
                  text: section.modelData.title
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }

                Repeater {
                  model: section.modelData.options

                  delegate: Button {
                    required property var modelData
                    width: section.width
                    height: Math.max(implicitHeight, Style.space(32))
                    text: modelData.label
                    selected: modelData.value === root.currentAncMode
                      || (modelData.value === "on" && root.snapshot
                        && root.snapshot.status && root.snapshot.status.anc === "on")
                    bordered: true
                    leftAlign: true
                    enabled: root.connection === "connected" && root.pendingRequestId < 0
                    opacity: enabled ? 1.0 : 0.5
                    foreground: root.bar.foreground
                    background: root.bar.background
                    accent: Color.accent
                    fontFamily: root.bar.fontFamily
                    focusable: true
                    onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                    Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                    Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                    Keys.onEscapePressed: root.close()
                    onClicked: root.selectAnc(modelData.value)
                  }
                }
              }
            }

            Column {
              id: featureColumn
              width: noiseColumn.width
              spacing: Style.space(5)
              visible: root.gameModeAvailable || true

              Text {
                width: parent.width
                text: "Special Features"
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
              }

              Button {
                id: gameModeButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: "󰊴  Game Mode (45ms)"
                selected: root.gameModeEnabled
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected" && root.pendingRequestId < 0
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                visible: root.gameModeAvailable
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleGameMode()
              }

              Button {
                id: notifyButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: root.notificationsEnabled ? "󰂃  Battery Alerts (20% & 10%)" : "󰂃  Battery Alerts (Off)"
                selected: root.notificationsEnabled
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected"
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleNotifications()
              }

              Button {
                id: wearDetectionButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: "󰂚  In-Ear Detection"
                selected: root.wearDetectionEnabled
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected" && root.pendingRequestId < 0
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                visible: root.wearDetectionAvailable
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleWearDetection()
              }

              Button {
                id: mprisHookButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: root.mprisHookEnabled ? "󰎆  MPRIS Auto-Pause (On)" : "󰎆  MPRIS Auto-Pause (Off)"
                selected: root.mprisHookEnabled
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected"
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleMprisHook()
              }

              Button {
                id: multipointButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: "󰂌  Dual Connection"
                selected: root.multipointEnabled
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected" && root.pendingRequestId < 0
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                visible: root.multipointAvailable
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleMultipoint()
              }

              Button {
                id: findBudsButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: root.locatorRinging ? "󰓛  Ringing (" + root.locatorTarget + ")…" : "󰖲  Find My Buds"
                selected: root.locatorCardOpen || root.locatorRinging
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected"
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleLocatorCard()
              }

              Column {
                id: locatorCard
                width: featureColumn.width
                visible: root.locatorCardOpen
                spacing: Style.space(6)

                Column {
                  width: parent.width
                  spacing: Style.space(5)
                  visible: !root.locatorRinging && root.pendingRingTarget === ""

                  Text {
                    width: parent.width
                    text: "Select earbud to ring:"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }

                  Row {
                    width: parent.width
                    spacing: Style.space(4)

                    Button {
                      width: (parent.width - Style.space(8)) / 3
                      height: Math.max(implicitHeight, Style.space(28))
                      text: "Left"
                      bordered: true
                      foreground: root.bar.foreground
                      background: root.bar.background
                      accent: Color.accent
                      fontFamily: root.bar.fontFamily
                      onClicked: root.pendingRingTarget = "left"
                    }

                    Button {
                      width: (parent.width - Style.space(8)) / 3
                      height: Math.max(implicitHeight, Style.space(28))
                      text: "Right"
                      bordered: true
                      foreground: root.bar.foreground
                      background: root.bar.background
                      accent: Color.accent
                      fontFamily: root.bar.fontFamily
                      onClicked: root.pendingRingTarget = "right"
                    }

                    Button {
                      width: (parent.width - Style.space(8)) / 3
                      height: Math.max(implicitHeight, Style.space(28))
                      text: "Both"
                      bordered: true
                      foreground: root.bar.foreground
                      background: root.bar.background
                      accent: Color.accent
                      fontFamily: root.bar.fontFamily
                      onClicked: root.pendingRingTarget = "both"
                    }
                  }
                }

                Column {
                  width: parent.width
                  spacing: Style.space(6)
                  visible: !root.locatorRinging && root.pendingRingTarget !== ""

                  Text {
                    width: parent.width
                    text: "⚠️ Ear Safety Lock"
                    textFormat: Text.PlainText
                    color: Color.accent
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    font.bold: true
                  }

                  Text {
                    width: parent.width
                    text: "Earbuds will chirp at maximum volume! Take them OUT of your ears."
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    wrapMode: Text.Wrap
                  }

                  Row {
                    width: parent.width
                    spacing: Style.space(6)

                    Text {
                      text: "Type 'realme':"
                      anchors.verticalCenter: parent.verticalCenter
                      color: root.bar.foreground
                      font.family: root.bar.fontFamily
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }

                    Controls.TextField {
                      id: ringConfirmInput
                      width: parent.width - Style.space(95)
                      placeholderText: "realme"
                      font.pixelSize: Style.font.bodySmall
                      Keys.onReturnPressed: {
                        if (ringConfirmInput.text.trim().toLowerCase() === "realme") {
                          root.ringBuds(root.pendingRingTarget)
                          root.pendingRingTarget = ""
                          ringConfirmInput.text = ""
                        }
                      }
                    }
                  }

                  Row {
                    width: parent.width
                    spacing: Style.space(6)

                    Button {
                      width: (parent.width - Style.space(6)) / 2
                      height: Math.max(implicitHeight, Style.space(28))
                      text: "Cancel"
                      bordered: true
                      foreground: root.bar.foreground
                      background: root.bar.background
                      fontFamily: root.bar.fontFamily
                      onClicked: {
                        root.pendingRingTarget = ""
                        ringConfirmInput.text = ""
                      }
                    }

                    Button {
                      width: (parent.width - Style.space(6)) / 2
                      height: Math.max(implicitHeight, Style.space(28))
                      text: "󰓛 Ring " + (root.pendingRingTarget === "both" ? "Both" : (root.pendingRingTarget === "left" ? "Left" : "Right"))
                      enabled: ringConfirmInput.text.trim().toLowerCase() === "realme"
                      opacity: enabled ? 1.0 : 0.4
                      selected: enabled
                      bordered: true
                      foreground: root.bar.foreground
                      background: root.bar.background
                      accent: Color.accent
                      fontFamily: root.bar.fontFamily
                      onClicked: {
                        root.ringBuds(root.pendingRingTarget)
                        root.pendingRingTarget = ""
                        ringConfirmInput.text = ""
                      }
                    }
                  }
                }

                Button {
                  width: parent.width
                  height: Math.max(implicitHeight, Style.space(30))
                  visible: root.locatorRinging
                  text: "󰓛  Stop Ringing"
                  selected: true
                  bordered: true
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.stopRingBuds()
                }
              }

              Button {
                id: gesturesButton
                width: featureColumn.width
                height: Math.max(implicitHeight, Style.space(32))
                text: "󰈈  Touch Gestures"
                selected: root.gestureCardOpen
                bordered: true
                leftAlign: true
                enabled: root.connection === "connected" && root.pendingRequestId < 0
                opacity: enabled ? 1.0 : 0.5
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                visible: root.gestureAvailable
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Keys.onEscapePressed: root.close()
                onClicked: root.toggleGestureCard()
              }

              Column {
                id: gestureCard
                width: featureColumn.width
                visible: root.gestureCardOpen
                spacing: Style.space(5)

                Text {
                  width: parent.width
                  text: "Left Earbud"
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Double Tap"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: leftDoubleTapCombo
                    width: parent.width - Style.space(84)
                    model: ["Next Track", "Play / Pause", "Previous Track", "Voice Assistant", "Game Mode", "Noise Control", "Volume Up", "Volume Down", "Disabled"]
                    property var actionKeys: ["next_track", "play_pause", "prev_track", "voice_assistant", "game_mode", "anc_cycle", "volume_up", "volume_down", "none"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.left ? root.gesturesData.left.double_tap : "next_track"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("left", "double_tap", actionKeys[index]) }
                  }
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Triple Tap"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: leftTripleTapCombo
                    width: parent.width - Style.space(84)
                    model: ["Disabled", "Previous Track", "Next Track", "Voice Assistant", "Game Mode", "Play / Pause"]
                    property var actionKeys: ["none", "prev_track", "next_track", "voice_assistant", "game_mode", "play_pause"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.left ? root.gesturesData.left.triple_tap : "none"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("left", "triple_tap", actionKeys[index]) }
                  }
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Touch & Hold"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: leftLongPressCombo
                    width: parent.width - Style.space(84)
                    model: ["Disabled", "Noise Control", "Game Mode", "Voice Assistant"]
                    property var actionKeys: ["none", "anc_cycle", "game_mode", "voice_assistant"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.left ? root.gesturesData.left.long_press : "none"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("left", "long_press", actionKeys[index]) }
                  }
                }

                Text {
                  width: parent.width
                  text: "Right Earbud"
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  topPadding: Style.space(4)
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Double Tap"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: rightDoubleTapCombo
                    width: parent.width - Style.space(84)
                    model: ["Play / Pause", "Next Track", "Previous Track", "Voice Assistant", "Game Mode", "Noise Control", "Volume Up", "Volume Down", "Disabled"]
                    property var actionKeys: ["play_pause", "next_track", "prev_track", "voice_assistant", "game_mode", "anc_cycle", "volume_up", "volume_down", "none"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.right ? root.gesturesData.right.double_tap : "play_pause"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("right", "double_tap", actionKeys[index]) }
                  }
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Triple Tap"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: rightTripleTapCombo
                    width: parent.width - Style.space(84)
                    model: ["Disabled", "Next Track", "Previous Track", "Voice Assistant", "Game Mode", "Play / Pause"]
                    property var actionKeys: ["none", "next_track", "prev_track", "voice_assistant", "game_mode", "play_pause"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.right ? root.gesturesData.right.triple_tap : "none"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("right", "triple_tap", actionKeys[index]) }
                  }
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)
                  Text {
                    width: Style.space(80)
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Touch & Hold"
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.ComboBox {
                    id: rightLongPressCombo
                    width: parent.width - Style.space(84)
                    model: ["Noise Control", "Game Mode", "Voice Assistant", "Disabled"]
                    property var actionKeys: ["anc_cycle", "game_mode", "voice_assistant", "none"]
                    currentIndex: Math.max(0, actionKeys.indexOf(root.gesturesData && root.gesturesData.right ? root.gesturesData.right.long_press : "anc_cycle"))
                    enabled: root.pendingRequestId < 0
                    onActivated: function(index) { root.setGesture("right", "long_press", actionKeys[index]) }
                  }
                }

                Text {
                  width: parent.width
                  text: "Long-Press Noise Modes"
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  topPadding: Style.space(4)
                }

                Row {
                  width: parent.width
                  spacing: Style.space(4)

                  Button {
                    width: (parent.width - Style.space(4)) / 2
                    height: Math.max(implicitHeight, Style.space(28))
                    text: "ANC ↔ Transp"
                    selected: !(root.gesturesData && root.gesturesData.long_press_anc_modes
                      && root.gesturesData.long_press_anc_modes.indexOf("off") !== -1)
                    bordered: true
                    foreground: root.bar.foreground
                    background: root.bar.background
                    accent: Color.accent
                    fontFamily: root.bar.fontFamily
                    onClicked: root.setGestureAncModes(["anc", "transparency"])
                  }

                  Button {
                    width: (parent.width - Style.space(4)) / 2
                    height: Math.max(implicitHeight, Style.space(28))
                    text: "+ Off (All 3)"
                    selected: !!(root.gesturesData && root.gesturesData.long_press_anc_modes
                      && root.gesturesData.long_press_anc_modes.indexOf("off") !== -1)
                    bordered: true
                    foreground: root.bar.foreground
                    background: root.bar.background
                    accent: Color.accent
                    fontFamily: root.bar.fontFamily
                    onClicked: root.setGestureAncModes(["anc", "transparency", "off"])
                  }
                }
              }
            }
          }


          Column {
            id: eqColumn
            x: root.useTwoColumnLayout ? noiseColumn.width + Style.space(16) : 0
            y: root.useTwoColumnLayout ? 0 : noiseColumn.implicitHeight + Style.space(14)
            width: root.useTwoColumnLayout ? noiseColumn.width : controlSections.width
            spacing: Style.space(5)
            visible: root.eqAvailable

            Text {
              width: parent.width
              text: "Earbud EQ"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Text {
              width: parent.width
              text: root.eqStatus ? "Current: " + root.eqStatus.current_name : "Current: Balanced"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }

            Flow {
              id: eqPresetFlow
              width: parent.width
              spacing: Style.space(5)

              Repeater {
                model: root.eqPresets
                delegate: Button {
                  required property var modelData
                  width: modelData.name.length > 22 ? eqPresetFlow.width
                    : (eqPresetFlow.width - eqPresetFlow.spacing) / 2
                  height: Math.max(implicitHeight, Style.space(32))
                  text: modelData.name
                  selected: !!(root.eqStatus && (root.eqStatus.current_id === modelData.id || root.eqStatus.current_name === modelData.name))
                  bordered: true
                  leftAlign: true
                  enabled: root.connection === "connected" && root.pendingRequestId < 0
                  opacity: enabled ? 1.0 : 0.5
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.selectEq(modelData.key)
                }
              }
            }

            Row {
              width: parent.width
              spacing: Style.space(6)
              Text {
                width: parent.width - Style.space(90)
                anchors.verticalCenter: parent.verticalCenter
                text: "Custom EQ"
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
              }
              Button {
                width: Style.space(84)
                height: Style.space(26)
                text: "󰐕  New EQ"
                onClicked: root.addCustomEq("Custom " + (root.customEqEntries.length + 1))
              }
            }

            Row {
              width: parent.width
              spacing: Style.space(5)
              visible: root.customEqEntries.length > 0
              Controls.ComboBox {
                id: customSlotCombo
                width: root.customEqEntries.length > 1 ? parent.width - Style.space(75) : parent.width
                model: root.customEqEntries.map(function(entry) { return entry.name })
                currentIndex: Math.max(0, Math.min(root.customSlotIndex, root.customEqEntries.length - 1))
                enabled: root.pendingRequestId < 0
                onActivated: function(index) { root.selectCustomSlot(index) }
              }
              Button {
                width: Style.space(70)
                height: Style.space(32)
                visible: root.customEqEntries.length > 1
                text: "󰆴 Delete"
                onClicked: {
                  if (root.selectedCustom) root.deleteCustomEq(root.selectedCustom.eq_id)
                }
              }
            }

            Row {
              width: parent.width
              spacing: Style.space(6)
              visible: root.selectedCustom !== null
              Text {
                text: "Name:"
                anchors.verticalCenter: parent.verticalCenter
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Controls.TextField {
                id: customNameField
                width: parent.width - Style.space(50)
                text: root.selectedCustom ? root.selectedCustom.name : ""
                placeholderText: "Preset name"
              }
            }

            Flow {
              id: customBandFlow
              width: parent.width
              spacing: Style.space(5)
              visible: root.selectedCustom !== null

              Repeater {
                id: bandRepeater
                model: root.selectedCustom ? root.selectedCustom.bands : []
                delegate: Column {
                  required property var modelData
                  property alias gainValue: gainBox.value
                  width: (customBandFlow.width - customBandFlow.spacing) / 2
                  spacing: Style.space(2)

                  Text {
                    width: parent.width
                    text: {
                      var freq = modelData.frequency || modelData.frequency_hz || 1000
                      return freq >= 1000 ? (freq / 1000) + " kHz" : freq + " Hz"
                    }
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.SpinBox {
                    id: gainBox
                    width: parent.width
                    from: root.selectedCustom ? (root.selectedCustom.minimum_gain_db || root.selectedCustom.min_gain_db || -12) : -12
                    to: root.selectedCustom ? (root.selectedCustom.maximum_gain_db || root.selectedCustom.max_gain_db || 12) : 12
                    stepSize: root.eqStatus && root.eqStatus.gain_step_db ? root.eqStatus.gain_step_db : 1
                    value: modelData.gain_db !== undefined ? modelData.gain_db : 0
                    editable: true
                    enabled: root.pendingRequestId < 0
                    textFromValue: function(value) { return (value > 0 ? "+" : "") + value + " dB" }
                    valueFromText: function(text) { return parseInt(text) || 0 }
                  }
                }
              }
            }

            Button {
              width: parent.width
              height: Math.max(implicitHeight, Style.space(32))
              visible: root.selectedCustom !== null
              text: "󰄬  Apply " + (root.selectedCustom ? root.selectedCustom.name : "Custom EQ")
              bordered: true
              leftAlign: true
              enabled: root.connection === "connected" && root.pendingRequestId < 0
              opacity: enabled ? 1.0 : 0.5
              foreground: root.bar.foreground
              background: root.bar.background
              accent: Color.accent
              fontFamily: root.bar.fontFamily
              onClicked: root.applyCustomEq()
            }
          }
        }

        Column {
          id: compatibilityNotice
          objectName: "compatibilityNotice"
          width: parent.width
          spacing: Style.space(3)
          visible: root.compatibilityNoticeShown

          Text {
            width: parent.width
            text: root.compatibilityLabel
            textFormat: Text.PlainText
            color: root.bar.foreground
            opacity: root.communityTestedDevice ? 0.72 : 0.88
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: root.experimentalDevice
          }

          Text {
            width: parent.width
            visible: root.experimentalDevice
            text: "This model has not been hardware verified."
            textFormat: Text.PlainText
            color: root.bar.foreground
            opacity: 0.72
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }

        }

        Column {
          id: reportSection
          objectName: "diagnosticReportSection"
          width: parent.width
          spacing: Style.space(3)
          visible: root.reportAvailable

          Text {
            id: reportAction
            objectName: "reportAction"
            visible: root.reportActionShown
            text: root.reportActionLabel
            textFormat: Text.PlainText
            color: Color.accent
            opacity: 0.82
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.underline: reportActionMouse.containsMouse

            MouseArea {
              id: reportActionMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.reportDetailsOpen = true
            }
          }

          Column {
            width: parent.width
            spacing: Style.space(3)
            visible: root.reportDetailsOpen

            Text {
              width: parent.width
              text: "The report includes versions, capabilities, connection state and safe protocol counters. Addresses, names, paths and secrets are omitted or redacted. Nothing is uploaded."
              textFormat: Text.PlainText
              color: root.bar.foreground
              opacity: 0.72
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }

            Text {
              id: saveReportAction
              objectName: "saveDiagnosticReportAction"
              visible: !root.reportSaved
              text: "Choose where to save report…"
              textFormat: Text.PlainText
              color: Color.accent
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.underline: saveReportMouse.containsMouse
              enabled: root.pendingRequestId < 0
              opacity: enabled ? 1.0 : 0.5

              MouseArea {
                id: saveReportMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                enabled: parent.enabled
                onClicked: root.openReportFileDialog()
              }
            }

            Column {
              id: reportSavedGuidance
              objectName: "reportSavedGuidance"
              visible: root.reportSaved
              width: parent.width
              spacing: Style.space(3)

              Text {
                objectName: "reportSavedConfirmation"
                width: parent.width
                text: "Your diagnostic report has been saved."
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                wrapMode: Text.Wrap
              }

              Text {
                objectName: "reportSavedLocation"
                width: parent.width
                text: root.savedReportLocation !== ""
                  ? "Saved to: " + root.savedReportLocation
                  : "Saved as: " + root.savedReportFilename
                textFormat: Text.PlainText
                color: root.bar.foreground
                opacity: 0.76
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.WrapAnywhere
              }

              Text {
                width: parent.width
                text: "Open a GitHub issue and manually attach the report file so the problem can be investigated. Nothing is uploaded automatically."
                textFormat: Text.PlainText
                color: root.bar.foreground
                opacity: 0.72
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.Wrap
              }

              Text {
                id: openIssueAction
                objectName: "openCompatibilityIssueAction"
                text: root.reportSubmissionActionLabel
                textFormat: Text.PlainText
                color: Color.accent
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.underline: openIssueMouse.containsMouse

                MouseArea {
                  id: openIssueMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.openReportIssue()
                }
              }
            }
          }
        }

        Text {
          width: parent.width
          visible: root.outcome !== "" || root.pendingRequestId >= 0
          textFormat: Text.PlainText
          text: root.pendingRequestId >= 0
            ? (root.pendingKind === "eq_status" ? "Reading native EQ…"
              : root.pendingKind === "diagnostic_report" ? "Saving diagnostic report…"
              : "Verifying " + BarModel.titleCase(root.pendingMode) + "…") : root.outcome
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
      }
    }
  }

  FileDialog {
    id: reportFileDialog
    title: "Save compatibility report"
    fileMode: FileDialog.SaveFile
    // The GTK native chooser can abort the in-process Quickshell host while
    // creating its GVFS directory monitor. Keep the chooser inside Qt Quick.
    options: FileDialog.DontUseNativeDialog
    currentFolder: {
      var documents = StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
      return String(documents || "") !== "" ? documents
        : StandardPaths.writableLocation(StandardPaths.HomeLocation)
    }
    defaultSuffix: "txt"
    nameFilters: ["Text reports (*.txt)"]
    onAccepted: root.acceptReportFile(selectedFile)
    onRejected: root.cancelDiagnosticReport()
  }

  IpcHandler {
    target: "realme-buds.control"

    function cycleAnc(): string {
      root.cycleAnc()
      return "ok"
    }

    function setAnc(mode: string): string {
      root.selectAnc(mode)
      return "ok"
    }

    function toggleGameMode(): string {
      root.toggleGameMode()
      return "ok"
    }

    function setGameMode(enabled: string): string {
      var val = (enabled === "true" || enabled === "1" || enabled === "on")
      if (root.budsService) root.budsService.setGameMode(val)
      return "ok"
    }

    function testNotification(): string {
      root.testNotification()
      return "ok"
    }

    function setNotifications(enabled: string): string {
      var val = (enabled === "true" || enabled === "1" || enabled === "on")
      root.notificationsEnabled = val
      if (root.budsService) root.budsService.setNotifications(val)
      return "ok"
    }

    function notifyStatus(): string {
      return JSON.stringify({
        enabled: root.notificationsEnabled,
        warning_threshold: 20,
        critical_threshold: 10
      })
    }

    function toggleWearDetection(): string {
      root.toggleWearDetection()
      return "ok"
    }

    function setWearDetection(enabled: string): string {
      var val = (enabled === "true" || enabled === "1" || enabled === "on")
      if (root.budsService) root.budsService.setWearDetection(val)
      return "ok"
    }

    function wearStatus(): string {
      return JSON.stringify({
        wear_detection: root.wearDetectionEnabled,
        wear_detection_available: root.wearDetectionAvailable,
        mpris_hook: root.mprisHookEnabled
      })
    }

    function toggleMprisHook(): string {
      root.toggleMprisHook()
      return "ok"
    }

    function setMprisHook(enabled: string): string {
      var val = (enabled === "true" || enabled === "1" || enabled === "on")
      root.mprisHookEnabled = val
      if (root.budsService) root.budsService.setMprisHook(val)
      return "ok"
    }

    function mprisHookStatus(): string {
      return JSON.stringify({
        enabled: root.mprisHookEnabled
      })
    }

    function toggleMultipoint(): string {
      root.toggleMultipoint()
      return "ok"
    }

    function setMultipoint(enabled: string): string {
      var val = (enabled === "true" || enabled === "1" || enabled === "on")
      if (root.budsService) root.budsService.setMultipoint(val)
      return "ok"
    }

    function multipointStatus(): string {
      return JSON.stringify({
        multipoint: root.multipointEnabled,
        multipoint_available: root.multipointAvailable
      })
    }

    function ringBuds(target: string): string {
      root.ringBuds(target)
      return "ok"
    }

    function stopRingBuds(): string {
      root.stopRingBuds()
      return "ok"
    }

    function ringStatus(): string {
      return JSON.stringify({
        ringing: root.locatorRinging,
        target: root.locatorTarget
      })
    }

    function setGesture(side: string, trigger: string, action: string): string {
      root.setGesture(side, trigger, action)
      return "ok"
    }

    function setGestureAncModes(modesJson: string): string {
      try {
        var modes = JSON.parse(modesJson)
        root.setGestureAncModes(modes)
      } catch (e) {
        root.setGestureAncModes(["anc", "transparency"])
      }
      return "ok"
    }

    function gestureStatus(): string {
      return JSON.stringify(root.gesturesData)
    }

    function setEq(preset: string): string {
      root.selectEq(preset)
      return "ok"
    }

    function queryEq(): string {
      return JSON.stringify(root.eqStatus || {})
    }

    function addCustomEq(name: string, gainsJson: string): string {
      var gains = [0, 0, 0, 0, 0, 0]
      if (gainsJson) {
        try { gains = JSON.parse(gainsJson) } catch (e) {}
      }
      if (root.budsService) {
        root.budsService.addCustomEq(name || "Custom", gains)
      }
      return "ok"
    }

    function deleteCustomEq(entryId: string): string {
      var id = parseInt(entryId, 10)
      if (!isNaN(id) && root.budsService) {
        root.budsService.deleteCustomEq(id)
      }
      return "ok"
    }

    function setCustomEq(entryId: string, gainsJson: string): string {
      var id = parseInt(entryId, 10)
      var gains = []
      try { gains = JSON.parse(gainsJson) } catch (e) {}
      if (!isNaN(id) && Array.isArray(gains) && gains.length > 0 && root.budsService) {
        root.budsService.setCustomEq(id, gains)
      }
      return "ok"
    }

    function reconnect(): string {
      if (root.budsService && typeof root.budsService.startHelper === "function") {
        root.budsService.startHelper()
        return "ok"
      }
      return "service_unavailable"
    }

    function restart(): string {
      if (root.budsService && typeof root.budsService.restartHelper === "function") {
        root.budsService.restartHelper()
        return "ok"
      }
      return "service_unavailable"
    }

    function status(): string {
      return JSON.stringify({
        service: root.budsService !== null,
        connection: root.connection,
        snapshot: root.snapshot !== null,
        device_status: root.snapshot ? root.snapshot.status : null,
        session_connected: root.snapshot ? root.snapshot.session_connected : false,
        generation: root.snapshot ? root.snapshot.generation : 0,
        lifecycle: root.budsService && root.budsService.lifecycleObservations
          ? root.budsService.lifecycleObservations : [],
        label: root.presentation.label,
        expanded: root.batteryExpanded,
        width: root.width,
        popup_open: root.popupOpen,
        panel_width: popup.contentWidth,
        panel_height: popup.contentHeight,
        two_column: root.useTwoColumnLayout,
        anc_modes: root.ancOptions.map(function(option) { return option.value }),
        current_anc: root.currentAncMode,
        game_mode: root.gameModeEnabled,
        game_mode_available: root.gameModeAvailable,
        notifications_enabled: root.notificationsEnabled,
        wear_detection: root.wearDetectionEnabled,
        wear_detection_available: root.wearDetectionAvailable,
        mpris_hook_enabled: root.mprisHookEnabled,
        multipoint: root.multipointEnabled,
        multipoint_available: root.multipointAvailable,
        ringing: root.locatorRinging,
        ringing_target: root.locatorTarget,
        gestures: root.gesturesData,
        gestures_available: root.gestureAvailable,
        pending: root.pendingRequestId >= 0,
        eq: root.eqStatus,
        compatibility: root.compatibilityKind,
        compatibility_notice: root.compatibilityNoticeShown,
        report_available: root.reportAvailable,
        report_action: reportAction.visible,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

}
