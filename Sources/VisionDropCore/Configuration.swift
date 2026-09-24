/// Every tunable value in the interaction engine.
///
/// No threshold, timing or gain may appear as a literal in a decision path
/// (SRS CFG-1). Defaults live here; the app layer loads overrides from disk and
/// may change them at runtime without a restart (SRS CFG-4).
///
/// Spatial thresholds are ratios against hand scale, never pixels, so they hold
/// as the hand moves toward or away from the camera (SRS ENG-1). The exceptions
/// are values that are genuinely screen-space, and they say so in their names.
public struct EngineConfiguration: Sendable, Codable, Equatable {
    public var features = FeatureConfiguration()
    public var pinch = PinchConfiguration()
    public var filter = FilterConfiguration()
    public var pointer = PointerConfiguration()
    public var idle = IdleConfiguration()
    public var tracking = TrackingConfiguration()

    public init() {}
}

public struct FeatureConfiguration: Sendable, Codable, Equatable {
    /// How much further from the wrist a fingertip must reach than the joint
    /// below it before the finger counts as extended. Slack absorbs landmark
    /// noise on a straight finger.
    public var fingerExtensionMargin = 0.08

    public init() {}
}

public struct PinchConfiguration: Sendable, Codable, Equatable {
    /// Pinch ratio at or below which an open pinch closes.
    public var enterRatio = 0.45
    /// Pinch ratio at or above which a closed pinch opens.
    ///
    /// Strictly greater than `enterRatio`: the gap is the hysteresis band that
    /// stops the state chattering when the ratio hovers near a threshold
    /// (SRS ENG-4, PLAN.md §2 cause 3).
    public var exitRatio = 0.65
    /// Pinch ratio treated as fully open when driving the continuous meter.
    /// Wider than `exitRatio` so the meter has room to move (SRS ENG-9).
    public var fullyOpenRatio = 0.90

    /// Consecutive frames the ratio must agree before the state closes.
    public var minFramesClosed = 2
    /// Consecutive frames the ratio must agree before the state opens.
    public var minFramesOpen = 2
    /// Dead time after a release during which no transition is evaluated.
    public var cooldown = Duration.milliseconds(120)

    /// Screen-space movement while pressed that converts a click into a drag.
    public var dragThresholdPixels = 10.0
    /// Maximum interval between two presses for the second to be a double click.
    public var doubleClickInterval = Duration.milliseconds(350)

    /// Thumb-to-middle ratios, for the right-click pinch.
    public var middleEnterRatio = 0.42
    public var middleExitRatio = 0.60

    public init() {}
}

public struct FilterConfiguration: Sendable, Codable, Equatable {
    /// Cutoff at rest, in Hz. Lower removes more jitter and adds more lag.
    public var minCutoff = 1.4
    /// How sharply the cutoff rises with speed. Higher reduces lag on fast
    /// movement at the cost of jitter.
    public var beta = 0.007
    public var derivativeCutoff = 1.0

    public init() {}
}

public struct PointerConfiguration: Sendable, Codable, Equatable {
    /// The region of the camera frame that maps to the whole screen, in
    /// normalized image coordinates.
    ///
    /// Mapping only the middle of the frame means the user reaches the screen
    /// edges without stretching to the edges of the camera's view, which
    /// matters most with a laptop lid camera (SRS PTR-1, ASM-4).
    public var activeBoxLeft = 0.20
    public var activeBoxRight = 0.80
    /// Measured from the bottom in Vision's coordinate space, where y grows up.
    public var activeBoxBottom = 0.10
    public var activeBoxTop = 0.85

    /// Control-display gain, applied about the centre of the active box.
    public var gain = 1.0
    /// Radius of the area cursor, in screen pixels (SRS PTR-8).
    public var areaRadiusPixels = 28.0
    /// How long the pointer holds still after a click so the selection lands
    /// where the user aimed (SRS PTR-4).
    public var clickFreeze = Duration.milliseconds(220)

    public init() {}
}

public struct IdleConfiguration: Sendable, Codable, Equatable {
    /// Pinch ratio above which the hand counts as clearly open. A pinching hand
    /// can still have four extended fingers, so an open-palm test alone would
    /// read a deliberate pinch as idle.
    public var openPinchRatio = 0.80
    /// Speed below which the hand counts as still, in normalized units/second.
    public var stillnessSpeed = 1.20

    public init() {}
}

public struct TrackingConfiguration: Sendable, Codable, Equatable {
    /// Landmarks below this confidence are reported as missing (SRS SEN-7).
    public var minimumLandmarkConfidence = 0.5
    public var maximumHands = 2

    public init() {}
}
