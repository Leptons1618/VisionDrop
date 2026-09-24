import AppKit
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

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private var permissionItem: NSMenuItem?
    private var cameraItem: NSMenuItem?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "VisionDrop"
        item.menu = makeMenu()
        statusItem = item
        refreshPermission()
    }

    func applicationWillTerminate(_ notification: Notification) {
        statusItem = nil
    }

    private func makeMenu() -> NSMenu {
        let menu = NSMenu()
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
    }
}
