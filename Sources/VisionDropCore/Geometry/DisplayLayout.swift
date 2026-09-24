/// One display, described in CoreGraphics global space.
public struct Display: Sendable, Equatable, Identifiable {
    public let id: UInt32
    /// Bounds in CoreGraphics global space (origin top-left of the primary display).
    public let bounds: ScreenRect
    /// Backing scale factor: 2.0 for a Retina display, 1.0 otherwise.
    public let scale: Double
    public let isPrimary: Bool

    public init(id: UInt32, bounds: ScreenRect, scale: Double, isPrimary: Bool) {
        self.id = id
        self.bounds = bounds
        self.scale = scale
        self.isPrimary = isPrimary
    }
}

/// The arrangement of all attached displays.
///
/// Displays may sit above or to the left of the primary, producing negative
/// coordinates, and may have differing scale factors. Both cases are covered by
/// the golden tests (SRS COORD-1).
public struct DisplayLayout: Sendable, Equatable {
    public let displays: [Display]

    public init(displays: [Display]) {
        precondition(!displays.isEmpty, "a layout needs at least one display")
        self.displays = displays
    }

    /// A single 1920×1080 display at the origin. Used by tests and as the
    /// fallback when the real layout cannot be read.
    public static let single = DisplayLayout(displays: [
        Display(
            id: 1,
            bounds: ScreenRect(x: 0, y: 0, width: 1920, height: 1080),
            scale: 2.0,
            isPrimary: true)
    ])

    public var primary: Display {
        displays.first(where: \.isPrimary) ?? displays[0]
    }

    /// The bounding rectangle of every display. This may include gaps: in an
    /// L-shaped arrangement, part of the union belongs to no display.
    public var bounds: ScreenRect {
        displays.dropFirst().reduce(displays[0].bounds) { $0.union($1.bounds) }
    }

    public func display(containing point: ScreenPoint) -> Display? {
        displays.first { $0.bounds.contains(point) }
    }

    /// The nearest point that lies on an actual display.
    ///
    /// Clamping to `bounds` is not enough: the union of an L-shaped arrangement
    /// contains regions no display occupies, and a pointer placed there would
    /// be invisible. This maps such a point onto the closest real display
    /// instead (SRS PTR-3).
    public func clampToVisibleArea(_ point: ScreenPoint) -> ScreenPoint {
        if display(containing: point) != nil { return point }
        return
            displays
            .map { $0.bounds.clamping(point) }
            .min { $0.distance(to: point) < $1.distance(to: point) } ?? point
    }
}
