/// One hand joint in Vision's normalized image space.
///
/// Origin is bottom-left; `x` and `y` are in 0…1 relative to the image.
///
/// There is deliberately **no depth component**. The Python prototype included
/// MediaPipe's `z` in every distance while its test fixtures set `z` to zero,
/// so a firmly-closed pinch could measure as firmly open in live use. Making
/// depth unrepresentable closes that defect at the type level rather than by
/// convention (SRS CON-5, ADR 0001 §1.2).
public struct Landmark: Sendable, Equatable {
    /// Horizontal position, 0…1, increasing to the right.
    public let x: Double
    /// Vertical position, 0…1, increasing upward (Vision's origin is bottom-left).
    public let y: Double
    /// Tracker confidence in this joint, 0…1.
    public let confidence: Double

    public init(x: Double, y: Double, confidence: Double = 1.0) {
        self.x = x
        self.y = y
        self.confidence = confidence
    }
}
