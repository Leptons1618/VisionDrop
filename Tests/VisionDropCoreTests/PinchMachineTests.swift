import Testing

@testable import VisionDropCore

@Suite("Pinch machine")
struct PinchMachineTests {
    let frame = 1.0 / 60.0
    let origin = ScreenPoint(x: 500, y: 500)

    /// Drives the machine at 60 Hz over a ratio sequence and collects events.
    private func run(
        _ ratios: [Double],
        positions: [ScreenPoint]? = nil,
        machine: inout PinchMachine,
        from start: Double = 0
    ) -> [PinchEvent] {
        var events: [PinchEvent] = []
        for (index, ratio) in ratios.enumerated() {
            let position = positions?[index] ?? origin
            let time = Duration.seconds(start + Double(index) * frame)
            events.append(contentsOf: machine.update(ratio: ratio, position: position, at: time).events)
        }
        return events
    }

    @Test("closing and opening without moving produces a click")
    func clickSequence() {
        var machine = PinchMachine()
        let events = run([0.9, 0.9, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9], machine: &machine)

        #expect(events == [.press, .click])
        #expect(!machine.isClosed)
        #expect(!machine.isDragging)
    }

    @Test("moving while closed produces a drag, and a drag never clicks")
    func dragSuppressesClick() {
        var machine = PinchMachine()
        let ratios = [0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9]
        let positions = [
            origin, origin, origin, origin,
            ScreenPoint(x: 540, y: 500), ScreenPoint(x: 580, y: 500),
            ScreenPoint(x: 580, y: 500), ScreenPoint(x: 580, y: 500), ScreenPoint(x: 580, y: 500),
        ]
        let events = run(ratios, positions: positions, machine: &machine)

        #expect(events == [.press, .dragStart, .dragEnd])
        #expect(!events.contains(.click))
    }

    @Test("movement below the threshold stays a click")
    func smallMovementStaysAClick() {
        var machine = PinchMachine()
        let nudged = ScreenPoint(x: origin.x + 4, y: origin.y + 3)  // 5 px, under the 10 px threshold
        let events = run(
            [0.9, 0.9, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9],
            positions: [origin, origin, origin, nudged, nudged, nudged, nudged, nudged],
            machine: &machine
        )
        #expect(events == [.press, .click])
    }

    @Test("a second press inside the double-click interval double-clicks once")
    func doubleClick() {
        var machine = PinchMachine()
        var events = run([0.9, 0.9, 0.1, 0.1, 0.9, 0.9], machine: &machine)
        // Wait out the release cooldown, then press again.
        events += run([0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.9, 0.9], machine: &machine, from: 0.14)

        #expect(events.filter { $0 == .doubleClick }.count == 1)
        // The press that completes a double click must not also emit a click.
        #expect(events.filter { $0 == .click }.count == 1)
    }

    @Test("a second press that becomes a drag does not double-click")
    func secondPressDragSuppressesDoubleClick() {
        var machine = PinchMachine()
        let firstEvents = run([0.9, 0.9, 0.1, 0.1, 0.9, 0.9], machine: &machine)
        let secondEvents = run(
            [0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9],
            positions: [
                origin,
                origin,
                ScreenPoint(x: 540, y: 500),
                ScreenPoint(x: 580, y: 500),
                origin,
                origin,
                origin,
            ],
            machine: &machine,
            from: 0.3
        )
        #expect(firstEvents == [.press, .click])
        #expect(!secondEvents.contains(.doubleClick))
        #expect(!secondEvents.contains(.click))
        #expect(secondEvents.contains(.dragStart))
        #expect(secondEvents.contains(.dragEnd))
    }

    @Test("a drag clears click timing")
    func dragClearsClickTiming() {
        var machine = PinchMachine()
        _ = run(
            [0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9],
            positions: [
                origin, origin, origin, origin,
                ScreenPoint(x: 540, y: 500), ScreenPoint(x: 580, y: 500),
                origin, origin, origin,
            ],
            machine: &machine
        )
        let events = run([0.9, 0.9, 0.1, 0.1, 0.9, 0.9], machine: &machine, from: 0.3)
        #expect(events == [.press, .click])
    }

    @Test("the exit threshold opens a closed pinch")
    func exitThresholdIsInclusive() {
        var machine = PinchMachine()
        _ = run([0.9, 0.9, 0.1, 0.1], machine: &machine)
        #expect(machine.isClosed)
        let events = run([PinchConfiguration().exitRatio, 0.9], machine: &machine, from: 0.1)
        #expect(events == [.click])
        #expect(!machine.isClosed)
    }

    /// The hysteresis band is the whole point: a ratio wandering between the
    /// two thresholds must not toggle the state (SRS ENG-4).
    @Test("a ratio oscillating inside the hysteresis band emits nothing")
    func hysteresisBandIsQuiet() {
        var machine = PinchMachine()
        let config = PinchConfiguration()
        _ = run([0.9, 0.9, 0.1, 0.1], machine: &machine)
        #expect(machine.isClosed)

        // Every value here sits strictly between enterRatio and exitRatio.
        let band = (0..<40).map { index -> Double in
            let middle = (config.enterRatio + config.exitRatio) / 2
            return middle + (index.isMultiple(of: 2) ? 0.09 : -0.09)
        }
        #expect(band.allSatisfy { $0 > config.enterRatio && $0 < config.exitRatio })

        let events = run(band, machine: &machine, from: 1.0)
        #expect(events.isEmpty)
        #expect(machine.isClosed)
    }

    @Test("a single stray frame does not trip the machine")
    func debounceRejectsSingleFrames() {
        var machine = PinchMachine()
        let events = run([0.9, 0.9, 0.1, 0.9, 0.9, 0.1, 0.9, 0.9], machine: &machine)
        #expect(events.isEmpty)
        #expect(!machine.isClosed)
    }

    @Test("a press arriving inside the release cooldown is ignored")
    func cooldownSuppressesImmediateRepress() {
        var machine = PinchMachine()
        _ = run([0.9, 0.9, 0.1, 0.1, 0.9, 0.9], machine: &machine)
        let releaseTime = 5 * frame

        // Re-close well inside the 120 ms cooldown.
        var machineCopy = machine
        let events = run([0.1, 0.1, 0.1], machine: &machineCopy, from: releaseTime + 0.01)
        #expect(events.isEmpty)
        #expect(!machineCopy.isClosed)
    }

    /// Losing the hand mid-drag must not leave the drag latched, or the next
    /// re-acquisition continues a drag the user already ended (SRS ENG-6).
    @Test("reset clears a drag in progress")
    func resetClearsDrag() {
        var machine = PinchMachine()
        // The press lands on the fourth frame, so the move must come after it.
        _ = run(
            [0.9, 0.9, 0.1, 0.1, 0.1],
            positions: [origin, origin, origin, origin, ScreenPoint(x: 600, y: 500)],
            machine: &machine
        )
        #expect(machine.isDragging)

        machine.reset()
        #expect(!machine.isDragging)
        #expect(!machine.isClosed)

        // And nothing is emitted for the transition it never saw.
        let events = run([0.9, 0.9, 0.9], machine: &machine, from: 1.0)
        #expect(events.isEmpty)
    }

    @Test("an infinite ratio holds the machine open")
    func infiniteRatioIsOpen() {
        var machine = PinchMachine()
        let events = run([.infinity, .infinity, .infinity, .infinity], machine: &machine)
        #expect(events.isEmpty)
        #expect(!machine.isClosed)
    }
}
