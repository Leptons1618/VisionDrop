/// First-order low-pass with an externally supplied smoothing factor.
struct LowPassFilter {
    private var value: Double?

    mutating func filter(_ x: Double, alpha: Double) -> Double {
        let result = value.map { alpha * x + (1 - alpha) * $0 } ?? x
        value = result
        return result
    }

    mutating func reset() { value = nil }
}

/// The 1€ filter (Casiez, Roussel & Vogel, CHI 2012).
///
/// A low cutoff at low speed removes jitter; the cutoff rises with speed so
/// that fast movement is not lagged. This is the trade-off a fixed low-pass
/// cannot make, and the reason the pointer can meet both the jitter and latency
/// targets at once (SRS PERF-1, PERF-3).
public struct OneEuroFilter: Sendable {
    public var minCutoff: Double
    public var beta: Double
    public var derivativeCutoff: Double

    private var x = LowPassFilter()
    private var dx = LowPassFilter()
    private var lastValue: Double?
    private var lastTime: Duration?

    public init(minCutoff: Double = 1.4, beta: Double = 0.007, derivativeCutoff: Double = 1.0) {
        self.minCutoff = minCutoff
        self.beta = beta
        self.derivativeCutoff = derivativeCutoff
    }

    public mutating func reset() {
        x.reset()
        dx.reset()
        lastValue = nil
        lastTime = nil
    }

    /// Smoothing factor for a first-order low-pass at `cutoff` Hz over `dt` seconds.
    static func alpha(cutoff: Double, dt: Double) -> Double {
        let tau = 1.0 / (2.0 * .pi * cutoff)
        return 1.0 / (1.0 + tau / dt)
    }

    /// - Parameters:
    ///   - value: the raw sample.
    ///   - time: capture timestamp. Real elapsed time drives the filter, so a
    ///     dropped frame widens `dt` rather than being silently ignored.
    /// - Returns: the smoothed value.
    public mutating func callAsFunction(_ value: Double, at time: Duration) -> Double {
        // The first sample has no interval to measure; assume 60 Hz until a
        // real one is available.
        let dt = lastTime.map { max((time - $0).seconds, 1e-6) } ?? (1.0 / 60.0)
        let derivative = lastValue.map { (value - $0) / dt } ?? 0
        let smoothedDerivative = dx.filter(derivative, alpha: Self.alpha(cutoff: derivativeCutoff, dt: dt))
        let cutoff = minCutoff + beta * abs(smoothedDerivative)
        let result = x.filter(value, alpha: Self.alpha(cutoff: cutoff, dt: dt))

        lastValue = value
        lastTime = time
        return result
    }
}

/// Two independent 1€ filters for a screen-space pointer.
public struct OneEuroFilter2D: Sendable {
    private var x: OneEuroFilter
    private var y: OneEuroFilter

    public init(minCutoff: Double = 1.4, beta: Double = 0.007, derivativeCutoff: Double = 1.0) {
        x = OneEuroFilter(minCutoff: minCutoff, beta: beta, derivativeCutoff: derivativeCutoff)
        y = OneEuroFilter(minCutoff: minCutoff, beta: beta, derivativeCutoff: derivativeCutoff)
    }

    public mutating func reset() {
        x.reset()
        y.reset()
    }

    public mutating func callAsFunction(_ point: ScreenPoint, at time: Duration) -> ScreenPoint {
        ScreenPoint(x: x(point.x, at: time), y: y(point.y, at: time))
    }
}

/// Smoothed speed of a 2D signal, in input units per second.
public struct VelocityTracker: Sendable {
    private var lastPoint: NormalizedPoint?
    private var lastTime: Duration?
    private let smoothing: Double

    public private(set) var speed: Double = 0

    public init(smoothing: Double = 0.4) {
        self.smoothing = smoothing
    }

    public mutating func reset() {
        lastPoint = nil
        lastTime = nil
        speed = 0
    }

    @discardableResult
    public mutating func update(_ point: NormalizedPoint, at time: Duration) -> Double {
        if let lastPoint, let lastTime {
            let dt = max((time - lastTime).seconds, 1e-6)
            let dx = point.x - lastPoint.x
            let dy = point.y - lastPoint.y
            let instantaneous = (dx * dx + dy * dy).squareRoot() / dt
            speed = smoothing * instantaneous + (1 - smoothing) * speed
        }
        lastPoint = point
        lastTime = time
        return speed
    }
}
