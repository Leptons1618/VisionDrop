import Testing

@testable import VisionDropCore

/// Golden geometry tests for the three coordinate spaces (SRS COORD-1).
///
/// Every case here is a layout that has historically produced defects: a
/// display above or left of the primary, so coordinates go negative; mixed
/// backing scale factors; and an arrangement whose bounding box contains a
/// region no display occupies.
@Suite("Coordinate spaces")
struct CoordinateTests {

    // MARK: Layouts

    static let sideBySide = DisplayLayout(displays: [
        Display(
            id: 1, bounds: ScreenRect(x: 0, y: 0, width: 1920, height: 1080), scale: 2.0, isPrimary: true),
        Display(
            id: 2, bounds: ScreenRect(x: 1920, y: 0, width: 1920, height: 1080), scale: 1.0, isPrimary: false),
    ])

    /// Secondary above and to the left of the primary: both axes go negative.
    static let aboveLeft = DisplayLayout(displays: [
        Display(id: 1, bounds: ScreenRect(x: 0, y: 0, width: 1512, height: 982), scale: 2.0, isPrimary: true),
        Display(
            id: 2, bounds: ScreenRect(x: -2560, y: -1440, width: 2560, height: 1440), scale: 1.0,
            isPrimary: false),
    ])

    /// Secondary above and to the right, leaving a region inside the bounding
    /// box that belongs to no display.
    static let lShaped = DisplayLayout(displays: [
        Display(
            id: 1, bounds: ScreenRect(x: 0, y: 0, width: 1920, height: 1080), scale: 2.0, isPrimary: true),
        Display(
            id: 2, bounds: ScreenRect(x: 1920, y: -1080, width: 1920, height: 1080), scale: 1.0,
            isPrimary: false),
    ])

    // MARK: Conversions

    @Test("the AppKit to CoreGraphics flip is its own inverse")
    func appKitFlipRoundTrips() {
        let height = 1080.0
        for point in [
            ScreenPoint(x: 0, y: 0), ScreenPoint(x: 960, y: 540), ScreenPoint(x: 1920, y: 1080),
            ScreenPoint(x: -300, y: -120),
        ] {
            let there = CoordinateSpace.appKitToScreen(point, primaryHeight: height)
            let back = CoordinateSpace.screenToAppKit(there, primaryHeight: height)
            #expect(back == point)
        }
    }

    @Test("AppKit's origin is the bottom-left, CoreGraphics' is the top-left")
    func appKitOriginMapsToBottom() {
        let converted = CoordinateSpace.appKitToScreen(ScreenPoint(x: 0, y: 0), primaryHeight: 1080)
        #expect(converted == ScreenPoint(x: 0, y: 1080))
    }

    /// Vision's y grows upward, CoreGraphics' downward. Getting this wrong puts
    /// the pointer at the opposite end of the screen from the hand.
    @Test("a hand raised in the frame maps to the top of the screen")
    func normalizedYIsInverted() {
        let rect = ScreenRect(x: 0, y: 0, width: 1920, height: 1080)
        let high = CoordinateSpace.normalizedToScreen(NormalizedPoint(x: 0.5, y: 1.0), in: rect)
        let low = CoordinateSpace.normalizedToScreen(NormalizedPoint(x: 0.5, y: 0.0), in: rect)

        #expect(high == ScreenPoint(x: 960, y: 0))
        #expect(low == ScreenPoint(x: 960, y: 1080))
    }

    @Test("normalized projection honours a rectangle with a negative origin")
    func normalizedProjectionWithNegativeOrigin() {
        let rect = ScreenRect(x: -2560, y: -1440, width: 2560, height: 1440)
        let centre = CoordinateSpace.normalizedToScreen(NormalizedPoint(x: 0.5, y: 0.5), in: rect)
        #expect(centre == ScreenPoint(x: -1280, y: -720))
    }

    // MARK: Layout geometry

    @Test("the bounding box spans every display")
    func boundsSpanAllDisplays() {
        #expect(Self.sideBySide.bounds == ScreenRect(x: 0, y: 0, width: 3840, height: 1080))
        #expect(Self.aboveLeft.bounds == ScreenRect(x: -2560, y: -1440, width: 4072, height: 2422))
        #expect(Self.lShaped.bounds == ScreenRect(x: 0, y: -1080, width: 3840, height: 2160))
    }

    @Test("mixed scale factors do not disturb global geometry")
    func mixedScaleFactors() {
        let displays = Self.sideBySide.displays
        #expect(displays[0].scale != displays[1].scale)
        // Global coordinates are in pixels and independent of backing scale;
        // a point on the secondary resolves to the secondary regardless.
        let onSecondary = ScreenPoint(x: 2880, y: 540)
        #expect(Self.sideBySide.display(containing: onSecondary)?.id == 2)
    }

    @Test("a point already on a display is left alone")
    func pointOnDisplayIsUnchanged() {
        let point = ScreenPoint(x: 400, y: 400)
        #expect(Self.lShaped.clampToVisibleArea(point) == point)
    }

    /// The reason clamping to the bounding box is not enough: this point is
    /// inside the bounds and on no display (SRS PTR-3).
    @Test("a point in the gap of an L-shaped layout moves to the nearest display")
    func gapPointSnapsToNearestDisplay() {
        let inGap = ScreenPoint(x: 100, y: -500)
        #expect(Self.lShaped.bounds.contains(inGap))
        #expect(Self.lShaped.display(containing: inGap) == nil)

        let clamped = Self.lShaped.clampToVisibleArea(inGap)
        #expect(clamped == ScreenPoint(x: 100, y: 0))
        #expect(Self.lShaped.display(containing: clamped) != nil)
    }

    @Test("a point outside every display lands on a display")
    func outsidePointLandsOnADisplay() {
        for point in [
            ScreenPoint(x: -9999, y: -9999), ScreenPoint(x: 9999, y: 9999),
            ScreenPoint(x: 500, y: -2000),
        ] {
            let clamped = Self.aboveLeft.clampToVisibleArea(point)
            #expect(
                Self.aboveLeft.display(containing: clamped) != nil,
                "\(point) clamped to \(clamped), which is on no display")
        }
    }
}
