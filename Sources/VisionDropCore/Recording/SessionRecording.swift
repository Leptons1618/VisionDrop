import Foundation

/// The JSONL session format: one JSON object per line, a header followed by
/// frames (SRS §6.1).
///
/// The format is deliberately tracker- and platform-independent (SRS PRT-2), so
/// a session recorded by one tracker can be replayed against another and the
/// two compared on identical input. That comparison is the evidence base for
/// revisiting the hand-tracking choice (ADR 0001 §7).
public enum SessionFormat {
    /// Readers reject anything they do not recognise rather than guessing
    /// (SRS DAT-3). Version 1 was the Python prototype's landmark-only format,
    /// whose points carried a depth component this engine does not accept.
    public static let currentVersion = 2
}

public struct SessionHeader: Sendable, Codable, Equatable {
    public var version: Int = SessionFormat.currentVersion
    /// Identifies the tracker and its model revision, so a recording is never
    /// silently replayed as though another tracker produced it (SRS DAT-2).
    public var tracker: String
    public var camera: CameraInfo
    public var displays: [DisplayInfo]
    public var started: Date
    /// Relative path to the source video beside this file, when one was
    /// recorded (SRS REC-3, DAT-4).
    public var video: String?

    public struct CameraInfo: Sendable, Codable, Equatable {
        public var id: String
        public var width: Int
        public var height: Int
        public var fps: Double
        /// Whether the frame was mirrored. Applied exactly once, at the sensing
        /// boundary, and recorded here so replay reproduces it (SRS COORD-2).
        public var mirrored: Bool

        public init(id: String, width: Int, height: Int, fps: Double, mirrored: Bool) {
            self.id = id
            self.width = width
            self.height = height
            self.fps = fps
            self.mirrored = mirrored
        }

        public var aspect: Double {
            height > 0 ? Double(width) / Double(height) : 1
        }
    }

    public struct DisplayInfo: Sendable, Codable, Equatable {
        public var id: UInt32
        /// `[x, y, width, height]` in CoreGraphics global space.
        public var bounds: [Double]
        public var scale: Double
        public var primary: Bool

        public init(id: UInt32, bounds: [Double], scale: Double, primary: Bool) {
            self.id = id
            self.bounds = bounds
            self.scale = scale
            self.primary = primary
        }
    }

    public init(
        tracker: String,
        camera: CameraInfo,
        displays: [DisplayInfo],
        started: Date = Date(),
        video: String? = nil
    ) {
        self.tracker = tracker
        self.camera = camera
        self.displays = displays
        self.started = started
        self.video = video
    }
}

/// One recorded frame.
public struct RecordedFrame: Sendable, Codable, Equatable {
    /// Capture time in seconds, from the session epoch.
    public var t: Double
    public var hands: [RecordedHand]

    public init(t: Double, hands: [RecordedHand]) {
        self.t = t
        self.hands = hands
    }
}

public struct RecordedHand: Sendable, Codable, Equatable {
    public var handedness: HandLandmarks.Chirality
    public var score: Double
    /// 21 entries in `HandJoint` order. Each is `[x, y, confidence]`, or `null`
    /// for a joint the tracker did not report — which is distinct from one
    /// reported with low confidence (SRS DAT-5).
    public var points: [[Double]?]

    public init(handedness: HandLandmarks.Chirality, score: Double, points: [[Double]?]) {
        self.handedness = handedness
        self.score = score
        self.points = points
    }
}

public enum SessionError: Error, Equatable, CustomStringConvertible {
    case emptyRecording
    case missingHeader
    case unsupportedVersion(found: Int, supported: Int)
    case malformedLine(number: Int, reason: String)
    case wrongPointCount(line: Int, found: Int)
    case wrongPointArity(line: Int, found: Int)
    case invalidDisplayLayout(reason: String)
    case invalidFrame(reason: String)

    public var description: String {
        switch self {
        case .emptyRecording:
            "the recording contains no lines"
        case .missingHeader:
            "the first line is not a session header"
        case .unsupportedVersion(let found, let supported):
            "recording format version \(found) is not supported (this build reads version \(supported))"
        case .malformedLine(let number, let reason):
            "line \(number) is malformed: \(reason)"
        case .wrongPointCount(let line, let found):
            "line \(line) has \(found) points, expected \(HandJoint.allCases.count)"
        case .wrongPointArity(let line, let found):
            "line \(line) has a landmark with \(found) values, expected 3"
        case .invalidDisplayLayout(let reason):
            "display layout is invalid: \(reason)"
        case .invalidFrame(let reason):
            "frame is invalid: \(reason)"
        }
    }
}

private extension SessionHeader {
    func validate() throws {
        guard camera.width > 0, camera.height > 0, camera.fps.isFinite, camera.fps > 0 else {
            throw SessionError.invalidDisplayLayout(
                reason: "camera dimensions and frame rate must be positive")
        }
        guard !displays.isEmpty else {
            throw SessionError.invalidDisplayLayout(reason: "at least one display is required")
        }
        guard displays.contains(where: \.primary) else {
            throw SessionError.invalidDisplayLayout(reason: "a primary display is required")
        }
        for display in displays {
            guard display.bounds.count == 4 else {
                throw SessionError.invalidDisplayLayout(
                    reason: "display \(display.id) needs x, y, width, and height")
            }
            guard display.bounds.allSatisfy(\.isFinite), display.bounds[2] > 0, display.bounds[3] > 0,
                display.scale.isFinite, display.scale > 0
            else {
                throw SessionError.invalidDisplayLayout(
                    reason: "display \(display.id) has invalid bounds or scale")
            }
        }
    }
}

/// Reads and writes the JSONL session format.
///
/// Parsing is defensive throughout: a malformed recording produces a typed
/// error, never a crash (SRS SEC-4).
public struct SessionCodec: Sendable {
    public init() {}

    private static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        // One object per line: the output must contain no newlines of its own.
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }

    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    // MARK: Encoding

    public func encode(header: SessionHeader) throws -> String {
        var object =
            try JSONSerialization.jsonObject(
                with: Self.encoder().encode(header)
            ) as? [String: Any] ?? [:]
        object["type"] = "header"
        return try Self.line(from: object)
    }

    public func encode(frame: RecordedFrame) throws -> String {
        var object =
            try JSONSerialization.jsonObject(
                with: Self.encoder().encode(frame)
            ) as? [String: Any] ?? [:]
        object["type"] = "frame"
        return try Self.line(from: object)
    }

    private static func line(from object: [String: Any]) throws -> String {
        let data = try JSONSerialization.data(
            withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes])
        return String(decoding: data, as: UTF8.self)
    }

    // MARK: Decoding

    /// Parses a whole recording.
    ///
    /// Blank lines are skipped, so a file that was appended to after an
    /// interrupted session still reads.
    public func decode(jsonl: String) throws -> (header: SessionHeader, frames: [RecordedFrame]) {
        let lines =
            jsonl
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .enumerated()
            .filter { !$0.element.isEmpty }

        guard let first = lines.first else { throw SessionError.emptyRecording }

        let decoder = Self.decoder()
        guard let headerData = first.element.data(using: .utf8),
            let probe = try? JSONSerialization.jsonObject(with: headerData) as? [String: Any],
            probe["type"] as? String == "header"
        else { throw SessionError.missingHeader }

        let header: SessionHeader
        do {
            header = try decoder.decode(SessionHeader.self, from: headerData)
        } catch {
            throw SessionError.malformedLine(number: 1, reason: "\(error)")
        }

        guard header.version == SessionFormat.currentVersion else {
            throw SessionError.unsupportedVersion(
                found: header.version, supported: SessionFormat.currentVersion
            )
        }
        try header.validate()

        var frames: [RecordedFrame] = []
        var previousTimestamp: Double?
        for (index, line) in lines.dropFirst() {
            let number = index + 1
            guard let data = line.data(using: .utf8) else {
                throw SessionError.malformedLine(number: number, reason: "not valid UTF-8")
            }
            let frame: RecordedFrame
            do {
                frame = try decoder.decode(RecordedFrame.self, from: data)
            } catch {
                throw SessionError.malformedLine(number: number, reason: "\(error)")
            }
            guard frame.t.isFinite else {
                throw SessionError.invalidFrame(reason: "timestamp must be finite")
            }
            if let previousTimestamp, frame.t < previousTimestamp {
                throw SessionError.invalidFrame(reason: "timestamps must be monotonic")
            }
            previousTimestamp = frame.t
            for hand in frame.hands {
                guard hand.points.count == HandJoint.allCases.count else {
                    throw SessionError.wrongPointCount(line: number, found: hand.points.count)
                }
                for point in hand.points.compactMap({ $0 }) {
                    guard point.count == 3, point.allSatisfy(\.isFinite),
                        (0.0...1.0).contains(point[2])
                    else {
                        throw SessionError.wrongPointArity(line: number, found: point.count)
                    }
                }
            }
            frames.append(frame)
        }

        return (header, frames)
    }
}

// MARK: - Bridging to engine types

extension RecordedHand {
    public init(_ hand: HandLandmarks) {
        self.init(
            handedness: hand.chirality,
            score: hand.score,
            points: HandJoint.allCases.map { joint in
                hand[joint].map { [$0.x, $0.y, $0.confidence] }
            }
        )
    }

    /// - Parameter minimumConfidence: joints below this are dropped, matching
    ///   what the live tracker would have discarded (SRS SEN-7).
    /// - Returns: the landmarks, or `nil` if the point count is wrong.
    public func landmarks(minimumConfidence: Double = 0) -> HandLandmarks? {
        guard points.count == HandJoint.allCases.count else { return nil }
        let joints: [Landmark?] = points.map { entry in
            guard let entry, entry.count == 3, entry[2] >= minimumConfidence else { return nil }
            return Landmark(x: entry[0], y: entry[1], confidence: entry[2])
        }
        return HandLandmarks(joints: joints, chirality: handedness, score: score)
    }
}

extension RecordedFrame {
    public init(_ observation: FrameObservation) {
        self.init(t: observation.timestamp.seconds, hands: observation.hands.map(RecordedHand.init))
    }

    public func observation(minimumConfidence: Double = 0) -> FrameObservation {
        FrameObservation(
            timestamp: .seconds(t),
            hands: hands.compactMap { $0.landmarks(minimumConfidence: minimumConfidence) }
        )
    }
}
