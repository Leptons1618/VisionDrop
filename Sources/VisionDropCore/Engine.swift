/// Everything the engine knows after one frame.
public struct EngineState: Sendable, Equatable {
    public let timestamp: Duration
    public let handPresent: Bool
    /// True when the hand is in a pose that drives the pointer.
    public let isActive: Bool
    /// True when the hand is resting; all input is suppressed (SRS ENG-11).
    public let isIdle: Bool
    public let features: HandFeatures?
    public let pinch: PinchState?
    public let pointer: ScreenPoint
    /// Continuous pinch closure, 0…1, for the overlay meter (SRS ENG-9).
    public let closure: Double
    /// Smoothed hand speed, normalized units per second.
    public let speed: Double

    public var events: [PinchEvent] { pinch?.events ?? [] }
}

/// The interaction engine: landmarks in, pointer and gesture state out.
///
/// UI-free and platform-free on purpose. The live app, the replay tool and the
/// tests all drive this same `process(_:)`, which is what makes a recorded
/// session a regression test (SRS MNT-1, ENG-7).
public struct Engine: Sendable {
    public var config: EngineConfiguration

    /// Frame width divided by frame height, used to make normalized distances
    /// isotropic.
    public var frameAspect: Double

    public private(set) var pointer: PointerMap
    private var pinch: PinchMachine
    private var velocity = VelocityTracker()
    private var wasActive = false

    public init(
        config: EngineConfiguration = .init(),
        layout: DisplayLayout = .single,
        frameAspect: Double = 16.0 / 9.0
    ) {
        self.config = config
        self.frameAspect = frameAspect
        self.pointer = PointerMap(layout: layout, config: config.pointer, filterConfig: config.filter)
        self.pinch = PinchMachine(config: config.pinch)
    }

    public mutating func reset() {
        pinch.reset()
        pointer.reset()
        velocity.reset()
        wasActive = false
    }

    public mutating func process(_ observation: FrameObservation) -> EngineState {
        let time = observation.timestamp

        guard let hand = observation.primaryHand,
            let features = HandFeatures(hand, aspect: frameAspect, config: config.features),
            features.isComplete
        else {
            // No usable hand. Every machine returns to neutral so that nothing
            // is latched across the gap and a drag cannot stick (SRS ENG-6).
            pinch.reset()
            velocity.reset()
            wasActive = false
            return EngineState(
                timestamp: time,
                handPresent: !observation.hands.isEmpty,
                isActive: false,
                isIdle: true,
                features: nil,
                pinch: nil,
                pointer: pointer.currentPosition,
                closure: 0,
                speed: 0
            )
        }
        let speed = velocity.update(features.pinchPoint, at: time)
        let idle = IdlePose.isIdle(features: features, speed: speed, config: config.idle)
        let openHand = features.isOpenPalm && features.pinchRatio > config.idle.openPinchRatio

        if idle || (openHand && pinch.isClosed) {
            pinch.reset()
            wasActive = false
            return EngineState(
                timestamp: time,
                handPresent: true,
                isActive: false,
                isIdle: true,
                features: features,
                pinch: nil,
                pointer: pointer.currentPosition,
                closure: features.closure(config.pinch),
                speed: speed
            )
        }
        let ratio = features.pinchRatio
        let mapped = pointer.mapToScreen(features.pinchPoint)
        let pinchState = pinch.update(ratio: ratio, position: mapped, at: time)

        let isActive = features.isPointing || pinchState.isClosed

        if isActive && !wasActive {
            // Re-anchor rather than teleport (SRS PTR-6).
            pointer.engage(at: features.pinchPoint)
        }
        wasActive = isActive

        if isActive {
            pointer.update(features.pinchPoint, at: time)
        }

        for event in pinchState.events {
            switch event {
            case .press, .click, .doubleClick:
                pointer.freeze(at: time)
            case .dragStart:
                pointer.unfreeze()
            case .dragEnd:
                break
            }
        }

        return EngineState(
            timestamp: time,
            handPresent: true,
            isActive: isActive,
            isIdle: idle,
            features: features,
            pinch: pinchState,
            pointer: pointer.currentPosition,
            closure: features.closure(config.pinch),
            speed: speed
        )
    }
}
