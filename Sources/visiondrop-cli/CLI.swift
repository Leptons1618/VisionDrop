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

              replay <recording.jsonl | -> [--verbose] [--json]
                  Replay a recorded session through the engine and report the
                  gesture events and timing it produced. `-` reads a live v2
                  stream from stdin and handles each frame as it arrives, e.g.
                  `visiondrop run --emit-v2 | visiondrop-cli replay - --verbose`.

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
        let (path, flags, _) = try parse(
            arguments, command: "replay", switches: ["--verbose", "--json"], options: [])

        // Lines are decoded and run one at a time, so `-` can be a live feed:
        // another tracker writing v2 frames to our stdin as it sees them.
        let source: String
        let lines: AnyIterator<String>
        if path == "-" {
            source = "stdin"
            setvbuf(stdout, nil, _IOLBF, 0)
            lines = AnyIterator { readLine(strippingNewline: true) }
        } else {
            let url = URL(fileURLWithPath: path)
            source = url.lastPathComponent
            let text = try String(contentsOf: url, encoding: .utf8)
            lines = AnyIterator(
                text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init).makeIterator())
        }

        let codec = SessionCodec()
        let config = EngineConfiguration()
        var header: SessionHeader?
        var engine = Engine(config: config)
        var frames: [Double] = []
        var number = 0
        var eventSequence: [String] = []
        var counts: [String: Int] = [:]
        var durations: [Double] = []
        var handsPresent = 0

        while let raw = lines.next() {
            number += 1
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { continue }
            if header == nil {
                let decoded = try codec.decodeHeader(line: line)
                header = decoded
                engine = Engine(
                    config: config, layout: layout(of: decoded), frameAspect: decoded.camera.aspect)
                continue
            }
            let frame = try codec.decodeFrame(line: line, number: number, after: frames.last)
            frames.append(frame.t)
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
                            format: "[%8.3f] ", state.timestamp.seconds)
                            + event.rawValue.padding(toLength: 12, withPad: " ", startingAt: 0)
                            + String(
                                format: " pointer=(%.0f,%.0f) ratio=%.3f",
                                state.pointer.x, state.pointer.y, state.pinch?.ratio ?? 0))
                }
            }
        }

        guard let header else { throw SessionError.emptyRecording }

        let sorted = durations.sorted()
        let report = ReplayReport(
            frames: frames.count,
            handsPresent: handsPresent,
            durationSeconds: (frames.last ?? 0) - (frames.first ?? 0),
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
            print("replayed \(report.frames) frames from \(source)")
            print("  tracker:   \(header.tracker)")
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

    static func layout(of header: SessionHeader) -> DisplayLayout {
        DisplayLayout(
            displays: header.displays.map {
                Display(
                    id: $0.id,
                    bounds: ScreenRect(
                        x: $0.bounds[0], y: $0.bounds[1], width: $0.bounds[2], height: $0.bounds[3]),
                    scale: $0.scale,
                    isPrimary: $0.primary
                )
            })
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
        #if canImport(AVFoundation)
        print("  camera:           \(CameraSource.authorizationDescription) — hand tracking")
        #else
        print("  camera:           not applicable on this platform")
        #endif
        print("  accessibility:    checked from M4 — injecting clicks and keys")
        print("  screen recording: checked from M6 — magnifier and OCR")
        print("")
        print("cameras:")
        #if canImport(AVFoundation)
        let cameras = CameraSource.availableDevices()
        if cameras.isEmpty {
            print("  none found")
        } else {
            for camera in cameras { print("  \(camera.name)  [\(camera.id)]") }
        }
        #else
        print("  unavailable: camera capture is macOS-only; replay works on this platform")
        #endif
    }
}

enum CLIError: Error, CustomStringConvertible {
    case missingArgument(String)
    case invalidArgument(String)
    case unsupported(String)

    var description: String {
        switch self {
        case .missingArgument(let detail), .invalidArgument(let detail), .unsupported(let detail):
            detail
        }
    }
}

extension CLI {
    /// Splits arguments into exactly one positional path, on/off switches, and
    /// options that take a value. Anything else is an error rather than being
    /// ignored, so a typo cannot silently change what was recorded or replayed.
    static func parse(
        _ arguments: [String], command: String, switches: Set<String>, options: Set<String>
    ) throws -> (path: String, switches: Set<String>, options: [String: String]) {
        var paths: [String] = []
        var seen: Set<String> = []
        var values: [String: String] = [:]
        var remaining = arguments[...]
        while let argument = remaining.popFirst() {
            if switches.contains(argument) {
                seen.insert(argument)
            } else if options.contains(argument) {
                guard let value = remaining.popFirst(), !value.hasPrefix("--") else {
                    throw CLIError.missingArgument("\(argument) needs a value")
                }
                values[argument] = value
            } else if argument.hasPrefix("-") && argument != "-" {
                throw CLIError.invalidArgument("\(command) does not accept \(argument)")
            } else {
                paths.append(argument)
            }
        }
        guard paths.count == 1, let path = paths.first, !path.isEmpty else {
            throw paths.isEmpty
                ? CLIError.missingArgument("\(command) needs a path")
                : CLIError.invalidArgument("\(command) takes one path, got \(paths.count)")
        }
        return (path, seen, values)
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
        let (path, flags, options) = try parse(
            arguments, command: "record", switches: ["--no-mirror"], options: ["--seconds", "--device"])
        let seconds = try options["--seconds"].map(parseSeconds) ?? 10
        let deviceID = options["--device"]
        let mirrored = !flags.contains("--no-mirror")

        #if !(canImport(AVFoundation) && canImport(Vision))
        _ = (path, seconds, deviceID, mirrored)
        throw CLIError.unsupported(
            "record needs AVFoundation and Vision, which are macOS-only; replay works on this platform")
        #else

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
        #endif
    }

    static func parseSeconds(_ text: String) throws -> Double {
        guard let seconds = Double(text), seconds.isFinite, seconds > 0 else {
            throw CLIError.invalidArgument("--seconds must be a positive number, got '\(text)'")
        }
        return seconds
    }
}
