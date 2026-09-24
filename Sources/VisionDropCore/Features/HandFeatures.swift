/// Scale-free, rotation-tolerant description of one hand.
///
/// Every spatial quantity here is a ratio against hand scale, never a pixel or
/// a raw normalized distance, so thresholds hold as the hand moves closer to or
/// further from the camera (SRS ENG-1).
///
/// All distances are computed in isotropic space — normalized coordinates with
/// `x` corrected for the frame aspect ratio — and the correction is applied to
/// every coordinate of every point or to none (SRS ENG-3). There is no depth
/// term; see `Landmark`.
public struct HandFeatures: Sendable, Equatable {
    /// Thumb-tip to index-tip distance, as a multiple of hand scale.
    public let pinchRatio: Double
    /// Thumb-tip to middle-tip distance, as a multiple of hand scale.
    public let middlePinchRatio: Double
    /// Wrist to index MCP, in isotropic units. The normalizer for every ratio.
    public let handScale: Double
    /// Midpoint of thumb tip and index tip, in normalized image space. This is
    /// a position for pointer mapping, not a distance, so it is not corrected.
    public let pinchPoint: NormalizedPoint

    public let indexExtended: Bool
    public let middleExtended: Bool
    public let ringExtended: Bool
    public let littleExtended: Bool
    public let thumbExtended: Bool

    /// True when all 21 joints were present. When false, pose predicates below
    /// are not trustworthy and the engine holds input (SRS SAF-7).
    public let isComplete: Bool

    /// Index extended while the other three long fingers are curled.
    public var isPointing: Bool {
        isComplete && indexExtended && !middleExtended && !ringExtended && !littleExtended
    }

    /// All four long fingers extended.
    public var isOpenPalm: Bool {
        isComplete && indexExtended && middleExtended && ringExtended && littleExtended
    }

    /// How closed the pinch is, 0 (fully open) to 1 (fully closed).
    ///
    /// Drives the continuous pinch meter in the overlay. This is deliberately
    /// separate from the discrete pinch state: the meter must move smoothly
    /// through the hysteresis band where the state does not change (SRS ENG-9).
    public func closure(_ config: PinchConfiguration) -> Double {
        let span = config.fullyOpenRatio - config.enterRatio
        guard span > 0 else { return pinchRatio <= config.enterRatio ? 1 : 0 }
        return min(max((config.fullyOpenRatio - pinchRatio) / span, 0), 1)
    }

    /// Extracts features from a hand.
    ///
    /// Fails, returning `nil`, when a joint required for scale or pinch is
    /// missing or when the hand is too small to normalize against.
    ///
    /// - Parameters:
    ///   - hand: the tracked hand.
    ///   - aspect: frame width divided by frame height.
    ///   - config: feature tuning.
    public init?(_ hand: HandLandmarks, aspect: Double, config: FeatureConfiguration = .init()) {
        func point(_ joint: HandJoint) -> IsotropicPoint? {
            hand[joint].map { IsotropicPoint(NormalizedPoint($0), aspect: aspect) }
        }

        guard let wrist = point(.wrist),
            let indexMCP = point(.indexMCP),
            let thumbTip = point(.thumbTip),
            let indexTipPoint = point(.indexTip),
            let thumbTipLandmark = hand[.thumbTip],
            let indexTipLandmark = hand[.indexTip]
        else { return nil }

        let scale = wrist.distance(to: indexMCP)
        // A hand this small is a tracking artefact, not a hand; dividing by it
        // would produce meaningless ratios.
        guard scale > 1e-6 else { return nil }

        self.handScale = scale
        self.pinchRatio = thumbTip.distance(to: indexTipPoint) / scale
        self.middlePinchRatio = point(.middleTip).map { thumbTip.distance(to: $0) / scale } ?? .infinity
        self.pinchPoint = NormalizedPoint(
            x: (thumbTipLandmark.x + indexTipLandmark.x) / 2,
            y: (thumbTipLandmark.y + indexTipLandmark.y) / 2
        )

        func extended(_ finger: Finger) -> Bool {
            guard let tip = point(finger.tip),
                let pip = point(finger.pip),
                let mcp = point(finger.mcp)
            else { return false }
            return Self.isExtended(
                wrist: wrist, tip: tip, pip: pip, mcp: mcp,
                margin: config.fingerExtensionMargin)
        }

        self.indexExtended = extended(.index)
        self.middleExtended = extended(.middle)
        self.ringExtended = extended(.ring)
        self.littleExtended = extended(.little)

        // The thumb folds across the palm rather than curling along it, so the
        // wrist-distance test used for the fingers does not apply. Instead the
        // tip moves away from the little-finger knuckle as the thumb opens.
        if let thumbIP = point(.thumbIP), let littleMCP = point(.littleMCP) {
            self.thumbExtended = thumbTip.distance(to: littleMCP) > thumbIP.distance(to: littleMCP)
        } else {
            self.thumbExtended = false
        }

        self.isComplete = HandJoint.allCases.allSatisfy { hand[$0] != nil }
    }

    /// Rotation-invariant extension test.
    ///
    /// A straight finger reaches further from the wrist at each successive
    /// joint; a curled one folds back toward the palm. Comparing distances from
    /// the wrist rather than image-space `y` keeps this valid when the hand is
    /// tilted or rotated — the failure that made the original demo reject
    /// natural pinches (PLAN.md §2, cause 2).
    static func isExtended(
        wrist: IsotropicPoint,
        tip: IsotropicPoint,
        pip: IsotropicPoint,
        mcp: IsotropicPoint,
        margin: Double
    ) -> Bool {
        let tipDistance = wrist.distance(to: tip)
        let pipDistance = wrist.distance(to: pip)
        let mcpDistance = wrist.distance(to: mcp)
        return tipDistance > pipDistance * (1 + margin) && pipDistance > mcpDistance * 0.95
    }
}
