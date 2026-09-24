import AppKit
import VisionDropCore
import VisionDropKit

@main
@MainActor
struct VisionDropApp {
    static func main() {
        let application = NSApplication.shared
        let delegate = AppDelegate()
        application.delegate = delegate
        application.setActivationPolicy(.accessory)
        application.run()
    }
}

private struct TrackingUpdate: Sendable, Equatable {
    let phase: String
    let event: PinchEvent?

    init(_ state: EngineState) {
        if !state.handPresent {
            phase = "no hand"
        } else if state.features == nil {
            phase = "hand partly visible"
        } else if state.pinch?.isDragging == true {
            phase = "dragging"
        } else if state.pinch?.isClosed == true {
            phase = "pinched"
        } else if state.isIdle {
            phase = "resting"
        } else if state.isActive {
            phase = "pointing"
        } else {
            phase = "hand visible"
        }
        event = state.events.last
    }
}

private enum TrackingOutcome: Sendable {
    case finished
    case stopped
    case failed(String)
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let config = EngineConfiguration()
    private let tracker = VisionHandTracker(maximumHands: EngineConfiguration().tracking.maximumHands)
    private var camera: CameraSource?
    private var trackingTask: Task<Void, Never>?
    private var statusItem: NSStatusItem?
    private var permissionItem: NSMenuItem?
    private var cameraItem: NSMenuItem?
    private var trackingItem: NSMenuItem?
    private var trackingToggleItem: NSMenuItem?
    private var trackingPhase = "off"
    private var lastEvent: PinchEvent?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "VisionDrop"
        item.menu = makeMenu()
        statusItem = item
        refreshPermission()
    }

    func applicationWillTerminate(_ notification: Notification) {
        trackingTask?.cancel()
        camera?.stop()
        camera = nil
        statusItem = nil
    }

    private func makeMenu() -> NSMenu {
        let menu = NSMenu()
        menu.delegate = self

        let permission = NSMenuItem(
            title: "Camera: \(CameraSource.authorizationDescription)",
            action: nil,
            keyEquivalent: ""
        )
        permission.isEnabled = false
        menu.addItem(permission)
        permissionItem = permission

        let cameras = NSMenuItem(
            title: "Cameras: \(CameraSource.availableDevices().count)",
            action: nil,
            keyEquivalent: ""
        )
        cameras.isEnabled = false
        menu.addItem(cameras)
        cameraItem = cameras

        let tracking = NSMenuItem(title: "Tracking: off", action: nil, keyEquivalent: "")
        tracking.isEnabled = false
        menu.addItem(tracking)
        trackingItem = tracking

        let toggle = NSMenuItem(
            title: "Start Tracking",
            action: #selector(toggleTracking),
            keyEquivalent: ""
        )
        toggle.target = self
        menu.addItem(toggle)
        trackingToggleItem = toggle

        menu.addItem(.separator())
        let request = NSMenuItem(
            title: "Request camera access…",
            action: #selector(requestCameraAccess),
            keyEquivalent: ""
        )
        request.target = self
        menu.addItem(request)

        menu.addItem(.separator())
        let quit = NSMenuItem(
            title: "Quit VisionDrop",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        menu.addItem(quit)
        return menu
    }

    func menuWillOpen(_ menu: NSMenu) {
        refreshPermission()
    }

    @objc private func toggleTracking() {
        if trackingTask != nil {
            trackingTask?.cancel()
            trackingPhase = "stopping…"
            refreshTrackingStatus()
            return
        }

        let camera = CameraSource()
        self.camera = camera
        trackingPhase = "starting…"
        lastEvent = nil
        refreshTrackingStatus()

        let config = self.config
        let delegate = self
        trackingTask = Task { [camera, tracker, config, delegate] in
            let outcome = await Self.runTracking(
                camera: camera,
                tracker: tracker,
                config: config,
                report: { update in
                    await delegate.apply(update)
                })
            delegate.trackingEnded(outcome)
        }
    }

    @objc private func requestCameraAccess() {
        permissionItem?.title = "Camera: requesting…"
        Task { @MainActor [weak self] in
            _ = await CameraSource.requestAccess()
            self?.refreshPermission()
        }
    }

    private func refreshPermission() {
        permissionItem?.title = "Camera: \(CameraSource.authorizationDescription)"
        let count = CameraSource.availableDevices().count
        cameraItem?.title = "Cameras: \(count)"
        refreshTrackingStatus()
    }

    private func apply(_ update: TrackingUpdate) {
        trackingPhase = update.phase
        if let event = update.event {
            lastEvent = event
        }
        refreshTrackingStatus()
    }

    private func trackingEnded(_ outcome: TrackingOutcome) {
        trackingTask = nil
        camera = nil
        switch outcome {
        case .finished:
            trackingPhase = "off"
        case .stopped:
            trackingPhase = "off"
        case .failed(let message):
            trackingPhase = "stopped — \(message)"
        }
        refreshTrackingStatus()
    }

    private func refreshTrackingStatus() {
        var status = "Tracking: \(trackingPhase)"
        if let lastEvent {
            status += " — last \(lastEvent.rawValue)"
        }
        trackingItem?.title = status
        trackingToggleItem?.title = trackingTask == nil ? "Start Tracking" : "Stop Tracking"
    }

    private nonisolated static func runTracking(
        camera: CameraSource,
        tracker: VisionHandTracker,
        config: EngineConfiguration,
        report: @escaping @Sendable (TrackingUpdate) async -> Void
    ) async -> TrackingOutcome {
        do {
            guard await CameraSource.requestAccess() else {
                throw CameraError.permissionDenied
            }
            try Task.checkCancellation()
            await tracker.warmUp()
            try Task.checkCancellation()

            let frames = try camera.start()
            defer { camera.stop() }
            var engine = Engine(config: config)
            var previous: TrackingUpdate?

            for await frame in frames {
                try Task.checkCancellation()
                let observation = try await tracker.hands(
                    in: frame,
                    minimumConfidence: config.tracking.minimumLandmarkConfidence)
                engine.frameAspect = frame.aspect
                let update = TrackingUpdate(engine.process(observation))
                if update != previous {
                    previous = update
                    await report(update)
                }
            }
            return .finished
        } catch is CancellationError {
            return .stopped
        } catch {
            return .failed((error as? CameraError)?.description ?? error.localizedDescription)
        }
    }
}
