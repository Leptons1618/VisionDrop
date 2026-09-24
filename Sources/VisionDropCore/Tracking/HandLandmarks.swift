/// The 21 landmarks of a single detected hand, in Vision normalized coordinates.
///
/// A joint the tracker did not report, or reported below the confidence
/// threshold, is stored as `nil`. Missing and low-confidence are therefore
/// distinguishable from a coordinate that happens to sit at the origin
/// (SRS SEN-7, DAT-5).
public struct HandLandmarks: Sendable, Equatable {
    /// Indexed by `HandJoint.rawValue`. Always 21 entries.
    private let joints: [Landmark?]

    /// Which hand this is, derived geometrically rather than from Vision's
    /// `chirality`, which is documented as unreliable (SRS SEN-6, ASM-5).
    public let chirality: Chirality

    /// Tracker confidence for the hand as a whole, 0…1.
    public let score: Double

    public enum Chirality: String, Sendable, Codable {
        case left, right, unknown
    }

    /// - Parameters:
    ///   - joints: exactly 21 entries, ordered by `HandJoint.rawValue`.
    ///   - chirality: which hand this is.
    ///   - score: tracker confidence for the hand as a whole.
    public init(joints: [Landmark?], chirality: Chirality = .unknown, score: Double = 1.0) {
        precondition(
            joints.count == HandJoint.allCases.count,
            "HandLandmarks requires exactly \(HandJoint.allCases.count) joints")
        self.joints = joints
        self.chirality = chirality
        self.score = score
    }

    public subscript(joint: HandJoint) -> Landmark? {
        joints[joint.rawValue]
    }

    /// True when every joint required for feature extraction is present.
    public var hasRequiredJoints: Bool {
        Self.requiredJoints.allSatisfy { self[$0] != nil }
    }

    /// The joints without which no scale-free feature can be computed: the
    /// hand-scale reference pair plus the pinch pair.
    static let requiredJoints: [HandJoint] = [.wrist, .indexMCP, .thumbTip, .indexTip]
}
