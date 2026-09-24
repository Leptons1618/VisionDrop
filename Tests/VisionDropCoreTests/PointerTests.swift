import Testing

@testable import VisionDropCore

@Suite("Pointer mapping")
struct PointerTests {
    /// The point that sits exactly at the centre of the default active box.
    let boxCentre = NormalizedPoint(x: 0.5, y: 0.475)

    @Test("the centre of the active box is the centre of the screen")
    func boxCentreMapsToScreenCentre() {
        let pointer = PointerMap()
        #expect(pointer.mapToScreen(boxCentre).isClose(to: ScreenPoint(x: 960, y: 540)))
    }

    @Test("the corners of the active box reach the corners of the screen")
    func boxCornersReachScreenCorners() {
        let pointer = PointerMap()
        let config = PointerConfiguration()

        let topLeft = pointer.mapToScreen(NormalizedPoint(x: config.activeBoxLeft, y: config.activeBoxTop))
        let bottomRight = pointer.mapToScreen(
            NormalizedPoint(x: config.activeBoxRight, y: config.activeBoxBottom))

        #expect(topLeft == ScreenPoint(x: 0, y: 0))
        #expect(bottomRight == ScreenPoint(x: 1920, y: 1080))
    }

    /// Reaching past the active box must not do anything surprising — the user
    /// should never have to stretch to the edge of the camera's view.
    @Test("hand positions outside the active box clamp to the screen edge")
    func outsideBoxClamps() {
        let pointer = PointerMap()
        #expect(pointer.mapToScreen(NormalizedPoint(x: 0.0, y: 0.99)) == ScreenPoint(x: 0, y: 0))
        #expect(pointer.mapToScreen(NormalizedPoint(x: 1.0, y: 0.01)) == ScreenPoint(x: 1920, y: 1080))
    }

    @Test("gain expands movement about the centre of the box")
    func gainExpandsAboutCentre() {
        var config = PointerConfiguration()
        config.gain = 2.0
        let pointer = PointerMap(config: config)

        // The centre is a fixed point of the gain transform.
        #expect(pointer.mapToScreen(boxCentre).isClose(to: ScreenPoint(x: 960, y: 540)))

        // A quarter of the way across the box lands at the screen edge once
        // movement is doubled.
        let quarter = NormalizedPoint(x: 0.35, y: 0.475)
        #expect(pointer.mapToScreen(quarter).x == 0)
    }

    @Test("a frozen pointer does not move")
    func freezeHoldsPosition() {
        var pointer = PointerMap()
        pointer.engage(at: boxCentre)
        let before = pointer.update(boxCentre, at: .seconds(0))

        pointer.freeze(at: .seconds(0))
        for index in 1...10 {
            pointer.update(NormalizedPoint(x: 0.25, y: 0.8), at: .seconds(Double(index) / 60.0))
        }
        #expect(pointer.currentPosition == before)

        // And it moves again once the freeze expires.
        #expect(pointer.isFrozen(at: .seconds(0.1)))
        #expect(!pointer.isFrozen(at: .seconds(0.3)))
    }

    @Test("a freeze cannot be shortened by a later, shorter one")
    func freezesExtendRatherThanReplace() {
        var pointer = PointerMap()
        pointer.freeze(at: .seconds(0), duration: .milliseconds(500))
        pointer.freeze(at: .seconds(0), duration: .milliseconds(50))
        #expect(pointer.isFrozen(at: .seconds(0.4)))
    }

    @Test("unfreeze releases the pointer immediately, as a drag must")
    func unfreezeReleasesImmediately() {
        var pointer = PointerMap()
        pointer.freeze(at: .seconds(0), duration: .seconds(10))
        #expect(pointer.isFrozen(at: .seconds(1)))
        pointer.unfreeze()
        #expect(!pointer.isFrozen(at: .seconds(1)))
    }

    /// Clutching is what lets the arm rest: lifting out, repositioning and
    /// coming back must not teleport the pointer (SRS PTR-6).
    @Test("re-engaging after a pause does not move the pointer")
    func clutchPreservesPosition() {
        var pointer = PointerMap()
        pointer.engage(at: boxCentre)
        let anchored = pointer.update(boxCentre, at: .seconds(0))

        // The hand drops out of the active pose and returns somewhere else.
        let elsewhere = NormalizedPoint(x: 0.30, y: 0.70)
        pointer.engage(at: elsewhere)
        let afterClutch = pointer.update(elsewhere, at: .seconds(2))

        #expect(afterClutch == anchored)
    }

    @Test("after clutching, movement is still relative to the new anchor")
    func clutchKeepsRelativeMovement() {
        var pointer = PointerMap()
        pointer.engage(at: boxCentre)
        let anchored = pointer.update(boxCentre, at: .seconds(0))

        let elsewhere = NormalizedPoint(x: 0.30, y: 0.70)
        pointer.engage(at: elsewhere)
        _ = pointer.update(elsewhere, at: .seconds(2))

        // Moving right from the new anchor moves the pointer right.
        for index in 1...30 {
            pointer.update(
                NormalizedPoint(x: 0.30 + Double(index) * 0.004, y: 0.70),
                at: .seconds(2 + Double(index) / 60.0))
        }
        #expect(pointer.currentPosition.x > anchored.x)
    }

    @Test("the pointer traverses a two-display layout continuously")
    func traversesDisplays() {
        var pointer = PointerMap(layout: CoordinateTests.sideBySide)
        let config = PointerConfiguration()

        let left = pointer.mapToScreen(NormalizedPoint(x: config.activeBoxLeft, y: 0.475))
        let right = pointer.mapToScreen(NormalizedPoint(x: config.activeBoxRight, y: 0.475))
        #expect(left.x == 0)
        #expect(right.x == 3840)

        pointer.engage(at: NormalizedPoint(x: config.activeBoxLeft, y: 0.475))
        var seenDisplays = Set<UInt32>()
        for index in 0...60 {
            let x = config.activeBoxLeft + (config.activeBoxRight - config.activeBoxLeft) * Double(index) / 60
            let position = pointer.update(NormalizedPoint(x: x, y: 0.475), at: .seconds(Double(index) / 60.0))
            if let display = CoordinateTests.sideBySide.display(containing: position) {
                seenDisplays.insert(display.id)
            }
        }
        #expect(seenDisplays == [1, 2])
    }

    @Test("the pointer never comes to rest off a display")
    func neverRestsInAGap() {
        var pointer = PointerMap(layout: CoordinateTests.lShaped)
        pointer.engage(at: NormalizedPoint(x: 0.5, y: 0.475))
        for index in 0...120 {
            let t = Double(index) / 60.0
            let position = pointer.update(
                NormalizedPoint(
                    x: 0.2 + 0.6 * Double(index % 61) / 60.0,
                    y: 0.1 + 0.75 * Double(index % 41) / 40.0),
                at: .seconds(t)
            )
            #expect(
                CoordinateTests.lShaped.display(containing: position) != nil,
                "pointer at \(position) is on no display")
        }
    }
}
