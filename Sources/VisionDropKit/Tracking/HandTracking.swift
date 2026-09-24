import VisionDropCore

/// A source of hand landmarks.
///
/// This exists so a second tracker can be evaluated against the shipping one on
/// identical recorded input, which is how the hand-tracking decision gets
/// revisited if Vision proves insufficient (SRS SEN-8, ADR 0001 §7).
public protocol HandTracking: Sendable {
    /// Tracker name and model revision, written into session headers so a
    /// recording is never silently replayed as though another tracker made it
    /// (SRS DAT-2).
    nonisolated var identifier: String { get }

    /// Extracts hands from one frame.
    ///
    /// - Parameters:
    ///   - frame: the captured frame.
    ///   - minimumConfidence: joints below this are reported as missing rather
    ///     than as coordinates (SRS SEN-7).
    /// - Returns: the frame's observation, with an empty hand list when none
    ///   were found.
    /// - Throws: whatever the underlying tracker raises for an unusable frame.
    func hands(in frame: CapturedFrame, minimumConfidence: Double) async throws -> FrameObservation
}
