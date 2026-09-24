/// The explicit idle pose: an open, relaxed palm held still.
///
/// This is the defence against Midas touch — a hand resting in view of the
/// camera must not produce input. While idle, the engine emits no gesture
/// events and the safety interlock suppresses injection outright
/// (SRS ENG-11, SAF-3).
public enum IdlePose {
    /// - Parameters:
    ///   - features: the hand's scale-free features.
    ///   - speed: smoothed hand speed in normalized units per second.
    ///   - config: idle thresholds.
    /// - Returns: `true` when the hand is resting.
    public static func isIdle(
        features: HandFeatures,
        speed: Double,
        config: IdleConfiguration = .init()
    ) -> Bool {
        // The open-palm test alone is not sufficient: a deliberate pinch can
        // leave all four long fingers extended, and would then read as idle.
        // Requiring the thumb to be clearly clear of the index as well
        // separates a resting hand from a pinching one.
        features.isOpenPalm
            && features.pinchRatio > config.openPinchRatio
            && speed < config.stillnessSpeed
    }
}
