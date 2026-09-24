/// Conversions between the three coordinate spaces in the system.
///
/// | Space                | Origin                        | y    | Units  |
/// |----------------------|-------------------------------|------|--------|
/// | Vision normalized    | bottom-left of the image      | up   | 0…1    |
/// | AppKit global        | bottom-left of primary screen | up   | points |
/// | CoreGraphics global  | top-left of primary display   | down | pixels |
///
/// This is the only place these conversions are written (SRS COORD-1). Nothing
/// else in the codebase may flip a y axis.
public enum CoordinateSpace {
    /// Converts an AppKit global point to CoreGraphics global space.
    ///
    /// Both origins sit on the primary display's left edge, so only `y` changes:
    /// it is measured from the opposite edge and grows the other way.
    ///
    /// - Parameters:
    ///   - point: a point in AppKit global space.
    ///   - primaryHeight: height of the primary display, in the same units as
    ///     `point`.
    /// - Returns: the same position in CoreGraphics global space.
    public static func appKitToScreen(_ point: ScreenPoint, primaryHeight: Double) -> ScreenPoint {
        ScreenPoint(x: point.x, y: primaryHeight - point.y)
    }

    /// Converts a CoreGraphics global point to AppKit global space.
    ///
    /// The inverse of ``appKitToScreen(_:primaryHeight:)``, and its own inverse
    /// in form: the same flip applied twice is the identity.
    public static func screenToAppKit(_ point: ScreenPoint, primaryHeight: Double) -> ScreenPoint {
        ScreenPoint(x: point.x, y: primaryHeight - point.y)
    }

    /// Projects a point in Vision's normalized image space onto a rectangle in
    /// CoreGraphics global space.
    ///
    /// Vision's `y` grows upward and CoreGraphics' grows downward, so the
    /// vertical axis is inverted here. Forgetting this inversion puts the
    /// pointer at the wrong end of the screen, which is the single most common
    /// defect this module exists to prevent.
    public static func normalizedToScreen(_ point: NormalizedPoint, in rect: ScreenRect) -> ScreenPoint {
        ScreenPoint(
            x: rect.minX + point.x * rect.width,
            y: rect.minY + (1.0 - point.y) * rect.height)
    }
}
