/// A point in CoreGraphics global display space: origin top-left of the primary
/// display, `y` increasing downward, units are pixels.
///
/// This is the space `CGEvent` locations use, and therefore the space the
/// pointer is expressed in (SRS §2.7).
public struct ScreenPoint: Sendable, Equatable {
    public let x: Double
    public let y: Double

    public init(x: Double, y: Double) {
        self.x = x
        self.y = y
    }

    public func distance(to other: ScreenPoint) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        return (dx * dx + dy * dy).squareRoot()
    }
}

/// A rectangle in CoreGraphics global display space.
///
/// `minY` is the top edge and `maxY` the bottom, because `y` grows downward.
public struct ScreenRect: Sendable, Equatable {
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double

    public init(x: Double, y: Double, width: Double, height: Double) {
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    }

    public var minX: Double { x }
    public var minY: Double { y }
    public var maxX: Double { x + width }
    public var maxY: Double { y + height }

    public var center: ScreenPoint {
        ScreenPoint(x: x + width / 2, y: y + height / 2)
    }

    public func contains(_ point: ScreenPoint) -> Bool {
        point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY
    }

    /// The nearest point inside this rectangle, which is the point itself when
    /// it already lies inside.
    public func clamping(_ point: ScreenPoint) -> ScreenPoint {
        ScreenPoint(
            x: min(max(point.x, minX), maxX),
            y: min(max(point.y, minY), maxY))
    }

    /// The smallest rectangle containing both.
    public func union(_ other: ScreenRect) -> ScreenRect {
        let x0 = min(minX, other.minX)
        let y0 = min(minY, other.minY)
        let x1 = max(maxX, other.maxX)
        let y1 = max(maxY, other.maxY)
        return ScreenRect(x: x0, y: y0, width: x1 - x0, height: y1 - y0)
    }
}
