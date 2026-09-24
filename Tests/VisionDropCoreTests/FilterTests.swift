import Foundation
import Testing

@testable import VisionDropCore

@Suite("Filters")
struct FilterTests {
    let frame = 1.0 / 60.0

    @Test("a constant signal converges to its value")
    func constantSignalConverges() {
        var filter = OneEuroFilter()
        var output = 0.0
        for index in 0..<120 {
            output = filter(100.0, at: .seconds(Double(index) * frame))
        }
        #expect(abs(output - 100.0) < 0.01)
    }

    /// The jitter half of the 1€ trade-off: a stationary hand must produce a
    /// stationary pointer (SRS PERF-3).
    @Test("a noisy stationary signal is smoothed")
    func jitterIsReduced() {
        var filter = OneEuroFilter()
        var generator = SystemRandomNumberGenerator()
        var inputs: [Double] = []
        var outputs: [Double] = []

        for index in 0..<300 {
            let noise = Double.random(in: -2...2, using: &generator)
            let sample = 500.0 + noise
            inputs.append(sample)
            outputs.append(filter(sample, at: .seconds(Double(index) * frame)))
        }

        // Compare the settled portion, after the filter has converged.
        func spread(_ values: [Double]) -> Double {
            let settled = values.suffix(200)
            let mean = settled.reduce(0, +) / Double(settled.count)
            return (settled.map { ($0 - mean) * ($0 - mean) }.reduce(0, +) / Double(settled.count))
                .squareRoot()
        }

        #expect(
            spread(outputs) < spread(inputs) / 2,
            "filtered spread \(spread(outputs)) should be well under input spread \(spread(inputs))")
    }

    /// The lag half of the trade-off: the cutoff rises with speed, so fast
    /// movement is not smoothed into treacle (SRS PERF-1).
    @Test("fast movement is tracked without excessive lag")
    func fastMovementTracks() {
        var filter = OneEuroFilter()
        var output = 0.0
        // 2000 px/s ramp, roughly a fast flick across a screen.
        for index in 0..<30 {
            output = filter(Double(index) * 2000 * frame, at: .seconds(Double(index) * frame))
        }
        let target = 29 * 2000 * frame
        #expect(output > target * 0.75, "output \(output) lags too far behind \(target)")
    }

    @Test("reset discards history")
    func resetDiscardsHistory() {
        var filter = OneEuroFilter()
        for index in 0..<60 { _ = filter(1000.0, at: .seconds(Double(index) * frame)) }
        filter.reset()
        // The first sample after a reset passes through untouched.
        #expect(filter(0.0, at: .seconds(10)) == 0.0)
    }

    @Test("the 2D filter treats its axes independently")
    func twoDimensionalFilterIsSeparable() {
        var filter2D = OneEuroFilter2D()
        var filterX = OneEuroFilter()

        var last2D = ScreenPoint(x: 0, y: 0)
        var lastX = 0.0
        for index in 0..<40 {
            let time = Duration.seconds(Double(index) * frame)
            let value = Double(index) * 7
            last2D = filter2D(ScreenPoint(x: value, y: -value), at: time)
            lastX = filterX(value, at: time)
        }
        #expect(abs(last2D.x - lastX) < 1e-9)
        #expect(abs(last2D.y + lastX) < 1e-9)
    }

    @Test("a stationary point has no speed and a moving one does")
    func velocityTracksMovement() {
        var stationary = VelocityTracker()
        for index in 0..<30 {
            stationary.update(NormalizedPoint(x: 0.5, y: 0.5), at: .seconds(Double(index) * frame))
        }
        #expect(stationary.speed < 1e-9)

        var moving = VelocityTracker()
        for index in 0..<30 {
            moving.update(
                NormalizedPoint(x: 0.5 + Double(index) * 0.01, y: 0.5),
                at: .seconds(Double(index) * frame))
        }
        #expect(moving.speed > 0.4)
    }
}
