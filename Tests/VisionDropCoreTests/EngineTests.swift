import Testing

@testable import VisionDropCore

@Suite("Engine")
struct EngineTests {
    let frame = 1.0 / 60.0

    private func makeEngine() -> Engine {
        Engine(layout: .single, frameAspect: 16.0 / 9.0)
    }

    private func observation(
        _ pose: SyntheticHand.Pose,
        at index: Int,
        translation: (x: Double, y: Double) = (0, 0)
    ) -> FrameObservation {
        FrameObservation(
            timestamp: .seconds(Double(index) * frame),
            hands: [SyntheticHand.make(pose: pose, translation: translation)]
        )
    }

    /// Drives a pose sequence and returns everything the engine emitted.
    private func drive(
        _ poses: [SyntheticHand.Pose],
        engine: inout Engine
    ) -> (events: [PinchEvent], states: [EngineState]) {
        var events: [PinchEvent] = []
        var states: [EngineState] = []
        for (index, pose) in poses.enumerated() {
            let state = engine.process(observation(pose, at: index))
            events.append(contentsOf: state.events)
            states.append(state)
        }
        return (events, states)
    }

    @Test("pointing then pinching then releasing is a click")
    func clickSequence() {
        var engine = makeEngine()
        let poses: [SyntheticHand.Pose] =
            Array(repeating: .point, count: 3)
            + Array(repeating: .pinch, count: 6)
            + Array(repeating: .point, count: 4)

        let (events, _) = drive(poses, engine: &engine)
        #expect(events.contains(.press))
        #expect(events.contains(.click))
        #expect(!events.contains(.dragStart))
    }

    /// Without this the pointer drifts between aiming and clicking, and the
    /// selection lands somewhere the user did not choose (SRS PTR-4).
    @Test("the pointer freezes when a click fires")
    func pointerFreezesOnClick() {
        var engine = makeEngine()
        var positionAtClick: ScreenPoint?
        var framesChecked = 0

        for index in 0..<30 {
            let pose: SyntheticHand.Pose = (3..<9).contains(index) ? .pinch : .point
            // Held still through the pinch so it stays a click rather than
            // becoming a drag, then drifting steadily once released.
            let drift = index >= 9 ? Double(index - 9) * 0.004 : 0
            let state = engine.process(observation(pose, at: index, translation: (drift, 0)))

            if state.events.contains(.click) {
                positionAtClick = state.pointer
            } else if let frozen = positionAtClick,
                engine.pointer.isFrozen(at: state.timestamp)
            {
                #expect(state.pointer == frozen)
                framesChecked += 1
            }
        }

        #expect(positionAtClick != nil)
        #expect(framesChecked > 0, "the freeze should span at least one frame after the click")
    }

    @Test("a resting open palm is idle and emits nothing")
    func restingHandIsIdle() {
        var engine = makeEngine()
        let (events, states) = drive(Array(repeating: .open, count: 30), engine: &engine)

        #expect(events.isEmpty)
        #expect(states.allSatisfy { $0.isIdle })
        #expect(states.allSatisfy { !$0.isActive })
    }

    /// A deliberate pinch leaves all four long fingers extended, so an
    /// open-palm test alone would classify it as resting and swallow the click.
    @Test("a pinching hand is not idle")
    func pinchingHandIsNotIdle() {
        var engine = makeEngine()
        let (_, states) = drive(Array(repeating: .pinch, count: 10), engine: &engine)
        #expect(states.allSatisfy { !$0.isIdle })
    }

    @Test("losing the hand clears every machine")
    func handLossResets() {
        var engine = makeEngine()

        // Establish a drag: pinch, then move far enough to cross the threshold.
        for index in 0..<4 { _ = engine.process(observation(.pinch, at: index)) }
        for index in 4..<8 {
            _ = engine.process(observation(.pinch, at: index, translation: (Double(index - 3) * 0.02, 0)))
        }

        // The hand disappears.
        let lost = engine.process(FrameObservation(timestamp: .seconds(0.2), hands: []))
        #expect(!lost.handPresent)
        #expect(!lost.isActive)
        #expect(lost.pinch == nil)

        // A fresh pinch afterwards starts from scratch: a new press, and no
        // drag left over from before.
        var events: [PinchEvent] = []
        for index in 20..<28 {
            events.append(contentsOf: engine.process(observation(.pinch, at: index)).events)
        }
        #expect(events.first == .press)
        #expect(!events.contains(.dragEnd))
    }

    @Test("a hand with too few joints to measure is treated as absent")
    func unusableHandIsInactive() {
        var engine = makeEngine()
        let crippled = FrameObservation(
            timestamp: .seconds(0),
            hands: [SyntheticHand.make(pose: .point, missing: [.wrist])]
        )
        let state = engine.process(crippled)
        #expect(!state.isActive)
        #expect(state.features == nil)
    }

    @Test("an incomplete hand cannot click")
    func incompleteHandCannotClick() {
        var engine = makeEngine()
        let poses: [SyntheticHand.Pose] = Array(repeating: .pinch, count: 6)
        var events: [PinchEvent] = []
        for index in 0..<poses.count {
            let hand = SyntheticHand.make(pose: poses[index], missing: [.ringDIP])
            events.append(
                contentsOf: engine.process(
                    FrameObservation(timestamp: .seconds(Double(index) * frame), hands: [hand])
                ).events)
        }
        #expect(events.isEmpty)
    }

    @Test("entering idle does not emit a click or drag end")
    func idleTransitionEmitsNoEvents() {
        var engine = makeEngine()
        var events: [PinchEvent] = []
        for index in 0..<8 {
            let pose: SyntheticHand.Pose = index < 4 ? .pinch : .open
            events.append(contentsOf: engine.process(observation(pose, at: index)).events)
        }
        #expect(events == [.press])
    }

    /// The property the whole replay-based regression gate rests on: the same
    /// landmarks in must always produce the same events out (SRS ENG-7).
    @Test("replaying the same landmarks produces the same events")
    func processingIsDeterministic() {
        let poses: [SyntheticHand.Pose] = [
            .open, .open, .point, .point, .pinch, .pinch, .pinch, .point,
            .point, .pinch, .pinch, .open, .open, .middlePinch, .middlePinch,
            .fist, .fist, .point, .pinch, .pinch, .point,
        ]

        var first = makeEngine()
        var second = makeEngine()
        let runA = drive(poses, engine: &first)
        let runB = drive(poses, engine: &second)

        #expect(runA.events == runB.events)
        #expect(runA.states.map(\.pointer) == runB.states.map(\.pointer))
        #expect(runA.states.map(\.isIdle) == runB.states.map(\.isIdle))
        #expect(runA.states.map(\.closure) == runB.states.map(\.closure))
    }

    @Test("closure tracks the pinch continuously through the hysteresis band")
    func closureIsContinuous() {
        var engine = makeEngine()
        let (_, openStates) = drive(Array(repeating: .open, count: 4), engine: &engine)
        let (_, pinchStates) = drive(Array(repeating: .pinch, count: 4), engine: &engine)

        #expect(openStates.allSatisfy { $0.closure < 0.5 })
        #expect(pinchStates.allSatisfy { $0.closure > 0.9 })
    }

    @Test("an empty frame leaves the pointer where it was")
    func pointerHoldsPositionWhenHandIsLost() {
        var engine = makeEngine()
        for index in 0..<10 { _ = engine.process(observation(.point, at: index)) }
        let before = engine.pointer.currentPosition

        let lost = engine.process(FrameObservation(timestamp: .seconds(1), hands: []))
        #expect(lost.pointer == before)
    }
}
