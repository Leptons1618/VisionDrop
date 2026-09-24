import Foundation

@testable import VisionDropCore

/// Deterministic synthetic hands for tests.
///
/// Coordinates are in Vision's space: origin bottom-left, y growing upward, so
/// a hand held upright has its wrist at a low y and its fingertips at a high one.
///
/// **Every field the production path can carry is populated** — confidence is
/// never a flat 1.0, joints can be absent, and pose, rotation, scale and
/// position are all variable (SRS MNT-8).
///
/// This rule exists because of a specific failure. The Python suite built every
/// hand with `z = 0.0` while the live tracker supplied real depth, so 36 green
/// tests coexisted with a pinch detector that could read a closed pinch as open
/// (ADR 0001 §1.2). A fixture that cannot express a value cannot test it.
enum SyntheticHand {
    enum Pose: CaseIterable {
        case open, point, pinch, middlePinch, fist
    }

    /// Anchor positions for an upright right hand at the reference scale.
    private static let wrist = (x: 0.50, y: 0.12)

    private static let thumb = (
        cmc: (0.47, 0.18), mcp: (0.45, 0.22), ip: (0.40, 0.26),
        tipOpen: (0.34, 0.30), tipPinch: (0.525, 0.465),
        tipMiddlePinch: (0.505, 0.455), tipFist: (0.46, 0.28)
    )

    private static func anchors(
        for finger: Finger
    )
        -> (mcp: (Double, Double), pip: (Double, Double), tip: (Double, Double), curled: (Double, Double))
    {
        switch finger {
        case .index: ((0.53, 0.30), (0.53, 0.38), (0.53, 0.46), (0.53, 0.32))
        case .middle: ((0.50, 0.31), (0.50, 0.40), (0.50, 0.49), (0.50, 0.34))
        case .ring: ((0.47, 0.30), (0.47, 0.38), (0.47, 0.46), (0.47, 0.32))
        case .little: ((0.44, 0.28), (0.44, 0.35), (0.44, 0.42), (0.44, 0.28))
        }
    }

    /// Builds a hand.
    ///
    /// - Parameters:
    ///   - pose: the hand shape to build.
    ///   - rotationDegrees: rotation about the wrist. Scale-free features must
    ///     be invariant to it.
    ///   - scale: size multiplier about the wrist, standing in for the hand
    ///     moving toward or away from the camera. Ratios must not change with it.
    ///   - translation: rigid offset, standing in for the hand moving across
    ///     the frame.
    ///   - confidence: per-joint confidence written into every landmark.
    ///   - missing: joints the tracker failed to report.
    /// - Returns: a hand with all 21 joints, minus those in `missing`.
    static func make(
        pose: Pose = .open,
        rotationDegrees: Double = 0,
        scale: Double = 1.0,
        translation: (x: Double, y: Double) = (0, 0),
        confidence: Double = 0.87,
        missing: Set<HandJoint> = []
    ) -> HandLandmarks {
        var points = [(Double, Double)](repeating: (0, 0), count: 21)
        let curled = pose == .point || pose == .fist || pose == .middlePinch

        points[HandJoint.wrist.rawValue] = wrist

        let thumbTip: (Double, Double) =
            switch pose {
            case .pinch: thumb.tipPinch
            case .middlePinch: thumb.tipMiddlePinch
            case .fist: thumb.tipFist
            default: thumb.tipOpen
            }
        points[HandJoint.thumbCMC.rawValue] = thumb.cmc
        points[HandJoint.thumbMCP.rawValue] = thumb.mcp
        points[HandJoint.thumbIP.rawValue] = thumb.ip
        points[HandJoint.thumbTip.rawValue] = thumbTip

        for finger in Finger.allCases {
            let a = anchors(for: finger)
            // The index stays extended for a pinch — the thumb comes to meet it.
            let isCurled = finger == .index ? (pose == .fist || pose == .middlePinch) : curled
            let tip = isCurled ? a.curled : a.tip
            let dip = midpoint(a.pip, tip)
            points[finger.mcp.rawValue] = a.mcp
            points[finger.pip.rawValue] = a.pip
            points[finger.tip.rawValue - 1] = dip
            points[finger.tip.rawValue] = tip
        }

        if pose == .middlePinch {
            let tip = (0.512, 0.448)
            points[HandJoint.middleTip.rawValue] = tip
            points[HandJoint.middleDIP.rawValue] = midpoint(points[HandJoint.middlePIP.rawValue], tip)
        }

        let radians = rotationDegrees * .pi / 180
        let cosine = cos(radians), sine = sin(radians)

        let joints: [Landmark?] = HandJoint.allCases.map { joint in
            guard !missing.contains(joint) else { return nil }
            let (px, py) = points[joint.rawValue]
            // Scale and rotate about the wrist, then translate, so the hand
            // stays a rigid body under every transform.
            let dx = (px - wrist.x) * scale
            let dy = (py - wrist.y) * scale
            return Landmark(
                x: wrist.x + dx * cosine - dy * sine + translation.x,
                y: wrist.y + dx * sine + dy * cosine + translation.y,
                confidence: confidence
            )
        }

        return HandLandmarks(joints: joints, chirality: .right, score: 0.94)
    }

    static func observation(
        pose: Pose = .open,
        at seconds: Double,
        rotationDegrees: Double = 0,
        scale: Double = 1.0
    ) -> FrameObservation {
        FrameObservation(
            timestamp: .seconds(seconds),
            hands: [make(pose: pose, rotationDegrees: rotationDegrees, scale: scale)]
        )
    }

    static func empty(at seconds: Double) -> FrameObservation {
        FrameObservation(timestamp: .seconds(seconds), hands: [])
    }

    private static func midpoint(_ a: (Double, Double), _ b: (Double, Double)) -> (Double, Double) {
        ((a.0 + b.0) / 2, (a.1 + b.1) / 2)
    }
}
