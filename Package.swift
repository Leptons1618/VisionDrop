// swift-tools-version: 6.0
import PackageDescription

// VisionDrop has zero third-party runtime dependencies by policy (SRS CON-2).
// Nothing but Apple frameworks and the Swift standard library may appear here.
let package = Package(
    name: "VisionDrop",
    platforms: [.macOS(.v15)],
    products: [
        .library(name: "VisionDropKit", targets: ["VisionDropKit"]),
        .executable(name: "visiondrop-cli", targets: ["visiondrop-cli"]),
        .executable(name: "visiondrop-app", targets: ["visiondrop-app"]),
    ],
    targets: [
        // Pure logic. No AppKit, no Vision, no I/O, no wall-clock time.
        // Compiles and tests with no camera, no display and no permissions (SRS MNT-1).
        .target(name: "VisionDropCore", swiftSettings: [.swiftLanguageMode(.v6)]),

        // Everything that touches macOS.
        .target(
            name: "VisionDropKit",
            dependencies: ["VisionDropCore"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),

        // Headless replay / bench / info, for CI (SRS REC-7).
        .executableTarget(
            name: "visiondrop-cli",
            dependencies: ["VisionDropCore", "VisionDropKit"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),

        // Minimal menu-bar shell. The overlay and capture loop remain separate
        // increments; this target proves the app lifecycle and permission UX.
        .executableTarget(
            name: "visiondrop-app",
            dependencies: ["VisionDropKit"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),

        .testTarget(
            name: "VisionDropCoreTests",
            dependencies: ["VisionDropCore"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),

        // Platform-facing tests that still need no camera, display or
        // permission: joint mapping, geometry, codecs (SRS MNT-1).
        .testTarget(
            name: "VisionDropKitTests",
            dependencies: ["VisionDropKit", "VisionDropCore"],
            swiftSettings: [.swiftLanguageMode(.v6)]
        ),
    ]
)
