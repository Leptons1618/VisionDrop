/// A discrete event produced by the pinch machine.
public enum PinchEvent: String, Sendable, Equatable, Codable {
    /// The pinch closed. Fires at the moment of contact, before it is known
    /// whether this becomes a click or a drag.
    case press
    /// The pinch opened without having moved. A click.
    case click
    /// A second press within the double-click interval.
    case doubleClick
    /// The pinch moved far enough while closed to be a drag rather than a click.
    case dragStart
    /// A drag ended.
    case dragEnd
}

/// State of the pinch machine after one frame.
public struct PinchState: Sendable, Equatable {
    public let isClosed: Bool
    public let isDragging: Bool
    public let events: [PinchEvent]
    /// The ratio this decision was made from, for display and diagnostics.
    public let ratio: Double
    public let position: ScreenPoint
    public let pressDuration: Duration

    public var didClick: Bool { events.contains(.click) }
    public var didDoubleClick: Bool { events.contains(.doubleClick) }
}

/// Hysteretic pinch detector with drag and double-click semantics.
///
/// Deliberately conservative, because every event it emits becomes a synthetic
/// click in whatever application has focus. Four mechanisms guard it
/// (SRS ENG-4, ENG-5):
///
/// 1. **Hysteresis** — separate enter and exit thresholds, so the state cannot
///    chatter while the ratio sits near one value.
/// 2. **Debounce** — a transition needs N consecutive agreeing frames.
/// 3. **Cooldown** — dead time after a release, during which no transition is
///    evaluated at all.
/// 4. **Drag disambiguation** — movement past a threshold while closed converts
///    the gesture to a drag, and a drag never emits a click.
///
/// It reads no clock: every decision comes from the timestamp it is handed, so
/// replaying a recording reproduces the event sequence exactly (SRS ENG-7).
public struct PinchMachine: Sendable {
    public var config: PinchConfiguration

    private var closed = false
    private var dragging = false
    private var candidate = false
    private var candidateFrames = 0
    private var pressTime: Duration?
    private var pressPosition: ScreenPoint?
    private var lastClickReleaseTime: Duration?
    private var doubleClickCandidate = false
    private var cooldownUntil: Duration = .zero

    public init(config: PinchConfiguration = .init()) {
        self.config = config
    }

    public var isClosed: Bool { closed }
    public var isDragging: Bool { dragging }

    /// Returns to the neutral state.
    ///
    /// Called when the hand is lost, so that no state is latched across a
    /// tracking gap and a drag cannot stick (SRS ENG-6).
    public mutating func reset() {
        closed = false
        dragging = false
        candidate = false
        candidateFrames = 0
        pressTime = nil
        pressPosition = nil
        lastClickReleaseTime = nil
        doubleClickCandidate = false
        cooldownUntil = .zero
    }

    /// Advances the machine by one frame.
    ///
    /// - Parameters:
    ///   - ratio: thumb-to-index distance over hand scale. Pass `.infinity` to
    ///     force the open state without disturbing the debounce counters.
    ///   - position: the pointer position in screen space, used for drag
    ///     disambiguation.
    ///   - time: capture timestamp of this frame.
    /// - Returns: the machine's state, including any events this frame produced.
    public mutating func update(
        ratio: Double,
        position: ScreenPoint,
        at time: Duration
    ) -> PinchState {
        var events: [PinchEvent] = []

        if time >= cooldownUntil {
            let threshold = closed ? config.exitRatio : config.enterRatio
            let desired = closed ? ratio < threshold : ratio <= threshold

            if desired == candidate {
                candidateFrames += 1
            } else {
                candidate = desired
                candidateFrames = 1
            }

            let needed = desired ? config.minFramesClosed : config.minFramesOpen
            if desired != closed && candidateFrames >= needed {
                events.append(
                    contentsOf: desired
                        ? press(at: position, time: time)
                        : release(at: time))
                closed = desired
            }
        }

        // Drag detection runs only while the ratio itself still reads closed.
        // Once the fingers start separating, the midpoint between the tips
        // travels quickly, and during the release debounce that travel would
        // otherwise be mistaken for a deliberate drag.
        let stillClosed = closed && ratio < config.exitRatio
        if stillClosed, !dragging, let pressPosition,
            position.distance(to: pressPosition) > config.dragThresholdPixels
        {
            dragging = true
            events.append(.dragStart)
        }

        return PinchState(
            isClosed: closed,
            isDragging: dragging,
            events: events,
            ratio: ratio,
            position: position,
            pressDuration: pressTime.map { time - $0 } ?? .zero
        )
    }

    private mutating func press(at position: ScreenPoint, time: Duration) -> [PinchEvent] {
        pressTime = time
        pressPosition = position
        doubleClickCandidate =
            lastClickReleaseTime.map {
                time - $0 <= config.doubleClickInterval
            } ?? false
        return [.press]
    }

    private mutating func release(at time: Duration) -> [PinchEvent] {
        var events: [PinchEvent] = []
        if dragging {
            events.append(.dragEnd)
            lastClickReleaseTime = nil
            doubleClickCandidate = false
        } else if doubleClickCandidate {
            events.append(.doubleClick)
            lastClickReleaseTime = nil
            doubleClickCandidate = false
        } else {
            events.append(.click)
            lastClickReleaseTime = time
        }

        dragging = false
        pressTime = nil
        pressPosition = nil
        cooldownUntil = time + config.cooldown
        return events
    }
}
