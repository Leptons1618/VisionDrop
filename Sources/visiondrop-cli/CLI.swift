import Foundation
import VisionDropCore
import VisionDropKit

/// Headless tooling: replay a recording through the engine and report what it
/// produced (SRS REC-7).
///
/// This is what CI runs over the evaluation corpus to catch a regression in
/// gesture behaviour before it reaches the app. It needs no camera, no display
/// and no permissions.
///
/// Arguments are parsed by hand rather than with a package, because the product
/// links no third-party code (SRS CON-2) and this surface is a handful of flags.
@main
struct CLI {
    static func main() async {
        let arguments = Array(CommandLine.arguments.dropFirst())
        guard let command = arguments.first else {
            printUsage()
            exit(1)
        }

        do {
            switch command {
            case "replay":
                try replay(Array(arguments.dropFirst()))
            case "record":
                try await record(Array(arguments.dropFirst()))
            case "info":
                info()
            case "-h", "--help", "help":
                printUsage()
            default:
                FileHandle.standardError.write(Data("error: unknown command '\(command)'\n".utf8))
                printUsage()
                exit(1)
            }
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            exit(2)
        }
    }

    static func printUsage() {
        print(
            """
            visiondrop-cli — headless engine tooling

              replay <recording.jsonl> [--verbose] [--json]
                  Replay a recorded session through the engine and report the
                  gesture events and timing it produced.

              record <out.jsonl> [--seconds N] [--device ID] [--no-mirror]
                  Capture from the camera, track hands, and write a replayable
                  session. Needs camera permission.

              info
                  Print the engine defaults and the format version this build reads.
            """)
    }

    // MARK: replay

    struct ReplayReport: Codable {
        var frames: Int
        var handsPresent: Int
        var durationSeconds: Double
        var eventSequence: [String]
        var events: [String: Int]
        var meanProcessingMicroseconds: Double
        var p99ProcessingMicroseconds: Double
    }

    static func replay(_ arguments: [String]) throws {
        let flags = Set(arguments.filter { $0.hasPrefix("--") })
        guard let path = arguments.first(where: { !$0.hasPrefix("--") }) else {
            throw CLIError.missingArgument("replay needs a path to a .jsonl recording")
        }

        let url = URL(fileURLWithPath: path)
        let text = try String(contentsOf: url, encoding: .utf8)
        let session = try SessionCodec().decode(jsonl: text)

        let layout = DisplayLayout(
            displays: session.header.displays.map {
                Display(
                    id: $0.id,
                    bounds: ScreenRect(
                        x: $0.bounds[0], y: $0.bounds[1], width: $0.bounds[2], height: $0.bounds[3]),
                    scale: $0.scale,
                    isPrimary: $0.primary
                )
            })

        let config = EngineConfiguration()
        var engine = Engine(config: config, layout: layout, frameAspect: session.header.camera.aspect)
        var eventSequence: [String] = []
        var counts: [String: Int] = [:]
        var durations: [Double] = []
        var handsPresent = 0

        for frame in session.frames {
            let observation = frame.observation(minimumConfidence: config.tracking.minimumLandmarkConfidence)
            let started = DispatchTime.now().uptimeNanoseconds
            let state = engine.process(observation)
            durations.append(Double(DispatchTime.now().uptimeNanoseconds - started) / 1000.0)

            if state.handPresent { handsPresent += 1 }
            for event in state.events {
                eventSequence.append(event.rawValue)
                counts[event.rawValue, default: 0] += 1
                if flags.contains("--verbose") {
                    print(
                        String(
                            format: "[%8.3f] %-12@ pointer=(%.0f,%.0f) ratio=%.3f",
                            state.timestamp.seconds, event.rawValue as NSString,
                            state.pointer.x, state.pointer.y, state.pinch?.ratio ?? 0))
                }
            }
        }

        let sorted = durations.sorted()
        let report = ReplayReport(
            frames: session.frames.count,
            handsPresent: handsPresent,
            durationSeconds: (session.frames.last?.t ?? 0) - (session.frames.first?.t ?? 0),
            eventSequence: eventSequence,
            events: counts,
            meanProcessingMicroseconds: durations.isEmpty
                ? 0 : durations.reduce(0, +) / Double(durations.count),
            p99ProcessingMicroseconds: sorted.isEmpty
                ? 0 : sorted[min(sorted.count - 1, Int(0.99 * Double(sorted.count - 1)))]
        )

        if flags.contains("--json") {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            print(String(decoding: try encoder.encode(report), as: UTF8.self))
        } else {
            print("replayed \(report.frames) frames from \(url.lastPathComponent)")
            print("  tracker:   \(session.header.tracker)")
            print("  hands:     \(report.handsPresent)/\(report.frames) frames")
            print(
                String(
                    format: "  engine:    mean %.1f µs, p99 %.1f µs",
                    report.meanProcessingMicroseconds, report.p99ProcessingMicroseconds))
            if counts.isEmpty {
                print("  events:    none")
            } else {
                for (name, count) in counts.sorted(by: { $0.key < $1.key }) {
                    print("  \(name): \(count)")
                }
            }
        }
    }

    // MARK: info

    static func info() {
        let config = EngineConfiguration()
        print("visiondrop-cli")
        print("  recording format version: \(SessionFormat.currentVersion)")
        print("  pinch:   enter \(config.pinch.enterRatio), exit \(config.pinch.exitRatio)")
        print("  filter:  minCutoff \(config.filter.minCutoff), beta \(config.filter.beta)")
        print(
            "  pointer: box x \(config.pointer.activeBoxLeft)…\(config.pointer.activeBoxRight), "
                + "y \(config.pointer.activeBoxBottom)…\(config.pointer.activeBoxTop), gain \(config.pointer.gain)"
        )
        print("")
        print("permissions:")
        print("  camera:           \(CameraSource.authorizationDescription) — hand tracking")
        print("  accessibility:    checked from M4 — injecting clicks and keys")
        print("  screen recording: checked from M6 — magnifier and OCR")
        print("")
        print("cameras:")
        let cameras = CameraSource.availableDevices()
        if cameras.isEmpty {
            print("  none found")
        } else {
            for camera in cameras { print("  \(camera.name)  [\(camera.id)]") }
        }
    }
}

enum CLIError: Error, CustomStringConvertible {
    case missingArgument(String)

    var description: String {
        switch self {
        case .missingArgument(let detail): detail
        }
    }
}

// MARK: - record

extension CLI {
    /// Captures a session to disk.
    ///
    /// This is how real fixtures get made: the evaluation corpus the regression
    /// gate replays has to come from an actual hand in front of an actual
    /// camera (SRS REC-1, §7.4).
    ///
    /// Note that macOS binds camera permission to the code signature, so a
    /// binary run from a terminal inherits the terminal's grant rather than
    /// having one of its own (ARCHITECTURE §4, H9).
    static func record(_ arguments: [String]) async throws {
        let flags = Set(arguments.filter { $0.hasPrefix("--") })
        guard let path = arguments.first(where: { !$0.hasPrefix("--") }) else {
            throw CLIError.missingArgument("record needs an output path")
        }
        let seconds = value(for: "--seconds", in: arguments).flatMap(Double.init) ?? 10
        let deviceID = value(for: "--device", in: arguments)
        let mirrored = !flags.contains("--no-mirror")

        guard await CameraSource.requestAccess() else { throw CameraError.permissionDenied }

        let config = EngineConfiguration()
        let tracker = VisionHandTracker(maximumHands: config.tracking.maximumHands)
        // Load the model before the camera starts, so the first seconds of the
        // session are not spent compiling it (SRS PERF-7).
        await tracker.warmUp()

        let camera = CameraSource()
        let frames = try camera.start(deviceID: deviceID, mirrored: mirrored)
        defer { camera.stop() }
        let codec = SessionCodec()

        var lines: [String] = []
        var recorded: [RecordedFrame] = []
        var engine = Engine()
        var counts: [String: Int] = [:]
        var epoch: Duration?
        var cameraSize = (width: 0, height: 0)

        print(
            "recording for \(Int(seconds))s at \(Int(camera.frameRate)) fps "
                + "— make some gestures. Ctrl+C to stop early.")

        for await frame in frames {
            let start = epoch ?? frame.timestamp
            epoch = start
            cameraSize = (frame.width, frame.height)

            let observation = try await tracker.hands(
                in: frame, minimumConfidence: config.tracking.minimumLandmarkConfidence)

            // Rebase onto the session epoch so timestamps start at zero.
            let rebased = FrameObservation(
                timestamp: observation.timestamp - start, hands: observation.hands)
            recorded.append(RecordedFrame(rebased))

            engine.frameAspect = frame.aspect
            for event in engine.process(rebased).events {
                counts[event.rawValue, default: 0] += 1
                print("  \(event.rawValue)")
            }

            if (frame.timestamp - start).seconds >= seconds { break }
        }

        let header = SessionHeader(
            tracker: tracker.identifier,
            camera: .init(
                id: camera.deviceIdentifier, width: cameraSize.width, height: cameraSize.height,
                fps: camera.frameRate, mirrored: camera.isMirrored),
            displays: [.init(id: 1, bounds: [0, 0, 1920, 1080], scale: 2.0, primary: true)]
        )

        lines.append(try codec.encode(header: header))
        lines.append(contentsOf: try recorded.map { try codec.encode(frame: $0) })
        try (lines.joined(separator: "\n") + "\n").write(
            toFile: path, atomically: true, encoding: .utf8)

        print("wrote \(path): \(recorded.count) frames, \(camera.droppedFrames) dropped by the camera")
        let withHands = recorded.count { !$0.hands.isEmpty }
        print("  hands present in \(withHands)/\(recorded.count) frames")
        for (name, count) in counts.sorted(by: { $0.key < $1.key }) { print("  \(name): \(count)") }
    }

    static func value(for flag: String, in arguments: [String]) -> String? {
        guard let index = arguments.firstIndex(of: flag), index + 1 < arguments.count else { return nil }
        return arguments[index + 1]
    }
}
