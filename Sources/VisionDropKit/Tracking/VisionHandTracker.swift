import CoreVideo
import Foundation
import Vision
import VisionDropCore

/// Hand tracking through Apple's Vision framework.
///
/// Vision returns the same 21-joint topology as MediaPipe — one wrist plus four
/// joints per finger — on the Neural Engine, with no third-party dependency and
/// no model to ship (ADR 0001 §3, Option A).
///
/// It is an actor because the underlying request is mutable state that the
/// capture and inference contexts both reach for.
public actor VisionHandTracker: HandTracking {
    public nonisolated let identifier: String
    private var request: DetectHumanHandPoseRequest

    public init(maximumHands: Int = 2) {
        var request = DetectHumanHandPoseRequest()
        request.maximumHandCount = maximumHands
        self.request = request
        self.identifier = "vision.handpose.\(request.revision)"
    }

    /// Runs one inference on a blank frame so the model is loaded and compiled
    /// before real frames arrive.
    ///
    /// The first request against a cold model takes seconds, which would
    /// otherwise be paid during the first moments of a session — long enough to
    /// swallow a short recording entirely, and to blow the launch budget
    /// (SRS PERF-7).
    public func warmUp() async {
        var buffer: CVPixelBuffer?
        CVPixelBufferCreate(nil, 640, 480, kCVPixelFormatType_32BGRA, nil, &buffer)
        guard let buffer else { return }
        _ = try? await request.perform(on: buffer, orientation: .up)
    }

    public func hands(in frame: CapturedFrame, minimumConfidence: Double) async throws -> FrameObservation {
        // The frame is already mirrored at the capture boundary if mirroring is
        // enabled, so no orientation correction belongs here (SRS COORD-2).
        let observations = try await request.perform(on: frame.pixelBuffer, orientation: .up)
        return FrameObservation(
            timestamp: frame.timestamp,
            hands: observations.compactMap { Self.landmarks(from: $0, minimumConfidence: minimumConfidence) }
        )
    }

    static func landmarks(
        from observation: HumanHandPoseObservation,
        minimumConfidence: Double
    ) -> HandLandmarks? {
        let joints = observation.allJoints()
        let points: [Landmark?] = HandJoint.allCases.map { joint in
            guard let found = joints[joint.visionJointName] else { return nil }
            let confidence = Double(found.confidence)
            guard confidence >= minimumConfidence else { return nil }
            // Vision's normalized space is already origin-bottom-left with axes
            // in 0…1, which is exactly what `Landmark` is defined in.
            return Landmark(x: Double(found.location.x), y: Double(found.location.y), confidence: confidence)
        }

        return HandLandmarks(
            joints: points,
            chirality: chirality(of: points),
            score: Double(observation.confidence)
        )
    }

    /// Derives handedness from the shape of the hand.
    ///
    /// Vision publishes a `chirality`, but it is widely reported to return
    /// `.right` almost regardless of the hand in view, so it is not used
    /// (SRS SEN-6, ASM-5).
    ///
    /// The sign of the cross product of wrist→index-knuckle and
    /// wrist→little-knuckle says which side of the hand the thumb lies on. That
    /// is enough to tell the hands apart in the palm-toward-camera pose this
    /// application is used in; it flips if the hand is turned over, which two
    /// dimensions cannot detect. Returns `.unknown` rather than guessing when
    /// the knuckles are missing or the triangle is degenerate.
    static func chirality(of points: [Landmark?]) -> HandLandmarks.Chirality {
        guard let wrist = points[HandJoint.wrist.rawValue],
            let index = points[HandJoint.indexMCP.rawValue],
            let little = points[HandJoint.littleMCP.rawValue]
        else { return .unknown }

        let cross = (index.x - wrist.x) * (little.y - wrist.y) - (index.y - wrist.y) * (little.x - wrist.x)
        guard abs(cross) > 1e-6 else { return .unknown }
        return cross > 0 ? .right : .left
    }
}

extension HandJoint {
    /// The Vision joint this landmark index corresponds to.
    ///
    /// The two topologies match one for one. Vision calls the thumb's
    /// metacarpophalangeal joint `thumbMP` where MediaPipe calls it `thumbMCP`;
    /// they are the same joint.
    var visionJointName: HumanHandPoseObservation.JointName {
        switch self {
        case .wrist: .wrist
        case .thumbCMC: .thumbCMC
        case .thumbMCP: .thumbMP
        case .thumbIP: .thumbIP
        case .thumbTip: .thumbTip
        case .indexMCP: .indexMCP
        case .indexPIP: .indexPIP
        case .indexDIP: .indexDIP
        case .indexTip: .indexTip
        case .middleMCP: .middleMCP
        case .middlePIP: .middlePIP
        case .middleDIP: .middleDIP
        case .middleTip: .middleTip
        case .ringMCP: .ringMCP
        case .ringPIP: .ringPIP
        case .ringDIP: .ringDIP
        case .ringTip: .ringTip
        case .littleMCP: .littleMCP
        case .littlePIP: .littlePIP
        case .littleDIP: .littleDIP
        case .littleTip: .littleTip
        }
    }
}
