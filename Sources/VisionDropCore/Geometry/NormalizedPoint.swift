/// A point in Vision's normalized image space: origin bottom-left, axes 0…1.
///
/// This is one of three coordinate spaces in the system, each with a different
/// origin (SRS §2.7). They are distinct types so that a conversion cannot be
/// skipped by accident; `CoordinateSpace` is the only place conversions live.
public struct NormalizedPoint: Sendable, Equatable {
    public let x: Double
    public let y: Double

    public init(x: Double, y: Double) {
        self.x = x
        self.y = y
    }

    public init(_ landmark: Landmark) {
        self.init(x: landmark.x, y: landmark.y)
    }
}

/// A point in an isotropic space derived from the normalized image by scaling
/// `x` by the frame aspect ratio.
///
/// Normalized image coordinates are anisotropic on a non-square frame: a
/// horizontal span of 0.1 is physically longer than a vertical span of 0.1.
/// Every distance used for gesture recognition is computed here instead, so
/// ratios mean what they appear to mean (SRS ENG-3).
struct IsotropicPoint: Equatable {
    let x: Double
    let y: Double

    /// - Parameters:
    ///   - point: a point in normalized image space.
    ///   - aspect: frame width divided by frame height.
    init(_ point: NormalizedPoint, aspect: Double) {
        self.x = point.x * aspect
        self.y = point.y
    }

    init(x: Double, y: Double) {
        self.x = x
        self.y = y
    }

    func distance(to other: IsotropicPoint) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        return (dx * dx + dy * dy).squareRoot()
    }
}
