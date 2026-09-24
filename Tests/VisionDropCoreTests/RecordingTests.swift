import Foundation
import Testing

@testable import VisionDropCore

@Suite("Session recording")
struct RecordingTests {
    let codec = SessionCodec()

    private func makeHeader(version: Int = SessionFormat.currentVersion) -> SessionHeader {
        var header = SessionHeader(
            tracker: "vision.handpose.r1",
            camera: .init(id: "FaceTime HD", width: 1280, height: 720, fps: 60, mirrored: true),
            displays: [.init(id: 1, bounds: [0, 0, 1920, 1080], scale: 2.0, primary: true)],
            started: Date(timeIntervalSince1970: 1_790_000_000),
            video: "session-0001.mov"
        )
        header.version = version
        return header
    }

    private func makeFrames() -> [RecordedFrame] {
        let poses: [SyntheticHand.Pose] = [.point, .point, .pinch, .pinch, .pinch, .point, .point, .point]
        return poses.enumerated().map { index, pose in
            RecordedFrame(
                FrameObservation(
                    timestamp: .seconds(Double(index) / 60.0),
                    hands: [SyntheticHand.make(pose: pose)]
                )
            )
        }
    }

    private func jsonl(header: SessionHeader, frames: [RecordedFrame]) throws -> String {
        try ([codec.encode(header: header)] + frames.map { try codec.encode(frame: $0) })
            .joined(separator: "\n")
    }

    @Test("a recording round-trips through the format unchanged")
    func roundTrip() throws {
        let header = makeHeader()
        let frames = makeFrames()
        let decoded = try codec.decode(jsonl: jsonl(header: header, frames: frames))

        #expect(decoded.header == header)
        #expect(decoded.frames.count == frames.count)
        #expect(decoded.frames == frames)
    }

    @Test("every line is a single line of JSON")
    func linesAreSingleLines() throws {
        let text = try jsonl(header: makeHeader(), frames: makeFrames())
        let lines = text.split(separator: "\n")
        #expect(lines.count == makeFrames().count + 1)
        #expect(lines.allSatisfy { $0.hasPrefix("{") && $0.hasSuffix("}") })
    }

    /// A joint the tracker never reported must stay distinguishable from one it
    /// reported weakly (SRS DAT-5).
    @Test("a missing joint survives as null, not as a coordinate")
    func missingJointsRoundTrip() throws {
        let hand = SyntheticHand.make(pose: .pinch, missing: [.littleTip, .ringDIP])
        let frame = RecordedFrame(FrameObservation(timestamp: .seconds(0), hands: [hand]))

        let line = try codec.encode(frame: frame)
        #expect(line.contains("null"))

        let decoded = try codec.decode(
            jsonl: [codec.encode(header: makeHeader()), line].joined(separator: "\n"))
        let restored = try #require(decoded.frames[0].hands[0].landmarks())
        #expect(restored[.littleTip] == nil)
        #expect(restored[.ringDIP] == nil)
        #expect(restored[.indexTip] != nil)
    }

    @Test("confidence is preserved rather than flattened")
    func confidenceRoundTrips() throws {
        let hand = SyntheticHand.make(pose: .open, confidence: 0.63)
        let frame = RecordedFrame(FrameObservation(timestamp: .seconds(0), hands: [hand]))
        let decoded = try codec.decode(
            jsonl: [try codec.encode(header: makeHeader()), try codec.encode(frame: frame)].joined(
                separator: "\n")
        )
        let restored = try #require(decoded.frames[0].hands[0].landmarks())
        #expect(restored[.wrist]?.confidence == 0.63)
    }

    @Test("joints below the confidence threshold are dropped on read")
    func lowConfidenceIsDropped() throws {
        let hand = SyntheticHand.make(pose: .open, confidence: 0.3)
        let recorded = RecordedHand(hand)
        #expect(
            recorded.landmarks(minimumConfidence: 0.5) == nil
                || recorded.landmarks(minimumConfidence: 0.5)?[.wrist] == nil)
        #expect(recorded.landmarks(minimumConfidence: 0.2)?[.wrist] != nil)
    }

    // MARK: Defensive parsing (SRS SEC-4, DAT-3)

    @Test("an unknown format version is rejected, not guessed at")
    func unknownVersionIsRejected() throws {
        let text = try jsonl(header: makeHeader(version: 99), frames: makeFrames())
        #expect(throws: SessionError.unsupportedVersion(found: 99, supported: SessionFormat.currentVersion)) {
            try codec.decode(jsonl: text)
        }
    }

    @Test("the Python prototype's version 1 format is rejected")
    func legacyVersionIsRejected() throws {
        // Version 1 carried a depth component per landmark that this engine
        // does not accept (SRS CON-5).
        let text = try jsonl(header: makeHeader(version: 1), frames: [])
        #expect(throws: SessionError.self) { try codec.decode(jsonl: text) }
    }

    @Test("an empty recording is an error, not an empty session")
    func emptyRecordingIsRejected() {
        #expect(throws: SessionError.emptyRecording) { try codec.decode(jsonl: "") }
        #expect(throws: SessionError.emptyRecording) { try codec.decode(jsonl: "\n\n   \n") }
    }

    @Test("a recording that starts with a frame is rejected")
    func headerlessRecordingIsRejected() throws {
        let text = try codec.encode(frame: makeFrames()[0])
        #expect(throws: SessionError.missingHeader) { try codec.decode(jsonl: text) }
    }

    @Test("malformed input produces a typed error rather than a crash")
    func malformedInputIsHandled() throws {
        let header = try codec.encode(header: makeHeader())
        for bad in ["{ not json", "{}", "[]", "{\"type\":\"frame\"}", "{\"type\":\"frame\",\"t\":\"soon\"}"] {
            #expect(throws: SessionError.self) {
                try codec.decode(jsonl: [header, bad].joined(separator: "\n"))
            }
        }
    }

    @Test("malformed landmark arity is rejected")
    func wrongPointArityIsRejected() throws {
        var points = Array(repeating: [0.5, 0.5, 0.9] as [Double], count: HandJoint.allCases.count)
        points[HandJoint.thumbTip.rawValue] = [0.5, 0.5]
        let hand = RecordedHand(handedness: .right, score: 0.9, points: points.map { Optional($0) })
        let text = [
            try codec.encode(header: makeHeader()),
            try codec.encode(frame: RecordedFrame(t: 0, hands: [hand])),
        ]
        .joined(separator: "\n")
        #expect(throws: SessionError.wrongPointArity(line: 2, found: 2)) {
            try codec.decode(jsonl: text)
        }
    }

    @Test("a recording with no display is rejected")
    func emptyDisplayLayoutIsRejected() throws {
        var header = makeHeader()
        header.displays = []
        let text = try codec.encode(header: header)
        #expect(throws: SessionError.self) { try codec.decode(jsonl: text) }
    }

    @Test("a recording with decreasing timestamps is rejected")
    func nonMonotonicFramesAreRejected() throws {
        let text = [
            try codec.encode(header: makeHeader()),
            try codec.encode(frame: RecordedFrame(t: 1, hands: [])),
            try codec.encode(frame: RecordedFrame(t: 0, hands: [])),
        ].joined(separator: "\n")
        #expect(throws: SessionError.invalidFrame(reason: "timestamps must be monotonic")) {
            try codec.decode(jsonl: text)
        }
    }

    // MARK: Replay

    @Test("blank lines in the middle of a recording are skipped")
    func blankLinesAreSkipped() throws {
        let header = try codec.encode(header: makeHeader())
        let frames = try makeFrames().map { try codec.encode(frame: $0) }
        let text = ([header] + frames.flatMap { [$0, ""] }).joined(separator: "\n")
        #expect(try codec.decode(jsonl: text).frames.count == frames.count)
    }

    // MARK: Replay

    /// The regression gate depends on this: a recording replayed through the
    /// engine must produce the same events every time (SRS REC-2, ENG-7).
    @Test("a decoded recording replays to the same events every time")
    func replayIsReproducible() throws {
        let text = try jsonl(header: makeHeader(), frames: makeFrames())
        let decoded = try codec.decode(jsonl: text)

        func replay() -> [PinchEvent] {
            var engine = Engine(layout: .single, frameAspect: decoded.header.camera.aspect)
            return decoded.frames.flatMap { engine.process($0.observation()).events }
        }

        let first = replay()
        #expect(first == replay())
        #expect(first.contains(.press))
        #expect(first.contains(.click))
    }

    @Test("a recording survives the trip through disk encoding")
    func survivesDataRoundTrip() throws {
        let text = try jsonl(header: makeHeader(), frames: makeFrames())
        let data = Data(text.utf8)
        let restored = String(decoding: data, as: UTF8.self)
        #expect(try codec.decode(jsonl: restored).frames == makeFrames())
    }
}
