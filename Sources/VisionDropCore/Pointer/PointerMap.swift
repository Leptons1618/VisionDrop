/// Maps the hand onto the screen and holds the pointer's state.
///
/// Four things happen between a fingertip and a cursor position: the active box
/// crops the usable part of the frame, gain scales movement about its centre,
/// the 1€ filter smooths the result, and a freeze holds the pointer still while
/// a click is delivered.
public struct PointerMap: Sendable {
    public var config: PointerConfiguration
    public var layout: DisplayLayout

    private var filter: OneEuroFilter2D
    private var position: ScreenPoint
    private var frozenUntil: Duration = .zero
    /// Offset applied to the mapped position so that re-engaging after a
    /// disengage does not teleport the pointer (SRS PTR-6).
    private var clutchOffset: (x: Double, y: Double) = (0, 0)

    public init(
        layout: DisplayLayout = .single,
        config: PointerConfiguration = .init(),
        filterConfig: FilterConfiguration = .init()
    ) {
        self.layout = layout
        self.config = config
        self.filter = OneEuroFilter2D(
            minCutoff: filterConfig.minCutoff,
            beta: filterConfig.beta,
            derivativeCutoff: filterConfig.derivativeCutoff
        )
        self.position = layout.primary.bounds.center
    }

    /// Current pointer position in CoreGraphics global space.
    public var currentPosition: ScreenPoint { position }

    /// Radius of the area cursor, in screen pixels (SRS PTR-8).
    public var areaRadius: Double { config.areaRadiusPixels }

    public mutating func reset() {
        filter.reset()
        position = layout.primary.bounds.center
        frozenUntil = .zero
        clutchOffset = (0, 0)
    }

    // MARK: - Freezing

    /// Holds the pointer still, so a click lands where the user aimed rather
    /// than where the hand drifted while the fingers closed (SRS PTR-4).
    ///
    /// Freezes extend rather than replace each other: a second click during a
    /// freeze cannot shorten it.
    public mutating func freeze(at time: Duration, duration: Duration? = nil) {
        frozenUntil = max(frozenUntil, time + (duration ?? config.clickFreeze))
    }

    /// Releases a freeze immediately, which a drag must do the moment it starts
    /// or the drag would begin by not moving (SRS PTR-5).
    public mutating func unfreeze() {
        frozenUntil = .zero
    }

    public func isFrozen(at time: Duration) -> Bool {
        time < frozenUntil
    }

    // MARK: - Mapping

    /// Projects a point in the camera frame onto the screen, without smoothing,
    /// clutch or freeze.
    ///
    /// Vision's y axis grows upward and CoreGraphics' grows downward; the
    /// inversion happens in `CoordinateSpace`, never here (SRS COORD-1).
    public func mapToScreen(_ point: NormalizedPoint) -> ScreenPoint {
        let left = config.activeBoxLeft
        let right = config.activeBoxRight
        let bottom = config.activeBoxBottom
        let top = config.activeBoxTop

        // Clamp into the active box, then rescale the box to the full 0…1 range.
        var x = min(max(point.x, left), right)
        var y = min(max(point.y, bottom), top)
        x = (right - left) > 0 ? (x - left) / (right - left) : 0.5
        y = (top - bottom) > 0 ? (y - bottom) / (top - bottom) : 0.5

        // Gain expands or contracts movement about the centre of the box, so
        // the neutral hand position stays at the centre of the screen.
        x = 0.5 + (x - 0.5) * config.gain
        y = 0.5 + (y - 0.5) * config.gain

        let clamped = NormalizedPoint(x: min(max(x, 0), 1), y: min(max(y, 0), 1))
        return CoordinateSpace.normalizedToScreen(clamped, in: layout.bounds)
    }

    /// Re-anchors the pointer at its current position.
    ///
    /// Called when the hand becomes active after a pause. Without this the
    /// pointer would jump to wherever the hand happens to be, which makes it
    /// impossible to rest the arm — the clutching behaviour that keeps extended
    /// use tolerable (SRS PTR-6, R6).
    public mutating func engage(at point: NormalizedPoint) {
        let mapped = mapToScreen(point)
        clutchOffset = (position.x - mapped.x, position.y - mapped.y)
        filter.reset()
    }

    /// Advances the pointer by one frame and returns its new position.
    @discardableResult
    public mutating func update(_ point: NormalizedPoint, at time: Duration) -> ScreenPoint {
        let mapped = mapToScreen(point)
        let offset = ScreenPoint(x: mapped.x + clutchOffset.x, y: mapped.y + clutchOffset.y)
        let smoothed = filter(offset, at: time)

        // Clamping to the union of all displays is not enough: an L-shaped
        // arrangement has regions inside the union that no display occupies,
        // and a pointer there would be invisible (SRS PTR-3).
        let visible = layout.clampToVisibleArea(smoothed)

        if !isFrozen(at: time) {
            position = visible
        }
        return position
    }
}
