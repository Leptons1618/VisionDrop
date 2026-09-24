import Foundation

@testable import VisionDropCore

extension ScreenPoint {
    /// Compares positions with a sub-pixel tolerance.
    ///
    /// The active-box mapping divides by values like 0.75 that have no exact
    /// binary representation, so results land a few ULPs from the arithmetic
    /// answer. A pointer is addressed in whole pixels, so anything under half a
    /// pixel is the same position.
    func isClose(to other: ScreenPoint, tolerance: Double = 0.5) -> Bool {
        abs(x - other.x) <= tolerance && abs(y - other.y) <= tolerance
    }
}
