/// One frame's tracking result: a capture timestamp and the hands found in it.
///
/// The timestamp is taken at the sensing boundary and is the only clock the
/// engine sees. Nothing downstream reads wall-clock time, which is what makes
/// replay deterministic (SRS SEN-5, ENG-7).
public struct FrameObservation: Sendable, Equatable {
    /// Monotonic capture time, measured from an arbitrary session epoch.
    public let timestamp: Duration

    /// Hands detected in this frame, at most two (SRS SEN-3).
    public let hands: [HandLandmarks]

    public init(timestamp: Duration, hands: [HandLandmarks]) {
        self.timestamp = timestamp
        self.hands = hands
    }

    /// The hand the pointer follows: the highest-scoring hand with a usable
    /// set of joints.
    public var primaryHand: HandLandmarks? {
        hands.filter(\.hasRequiredJoints).max { $0.score < $1.score }
    }
}

extension Duration {
    /// This duration expressed in seconds.
    ///
    /// `Duration` stores attoseconds as integers, so this conversion is exact
    /// to within a double's precision and never accumulates drift.
    public var seconds: Double {
        let (whole, attos) = components
        return Double(whole) + Double(attos) * 1e-18
    }
}
