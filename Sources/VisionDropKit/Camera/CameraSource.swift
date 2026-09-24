import AVFoundation
import CoreVideo
import Foundation
import VisionDropCore

/// One frame from the camera.
///
/// Marked `@unchecked Sendable` because `CVPixelBuffer` is a CoreFoundation
/// type without a Sendable conformance. It is safe here by construction: the
/// buffer is produced by the capture queue, handed off once, and only ever read
/// downstream. Nothing mutates it after capture.
public struct CapturedFrame: @unchecked Sendable {
    public let pixelBuffer: CVPixelBuffer
    /// Capture time, from the sample buffer's presentation timestamp. This is
    /// the clock the whole pipeline runs on (SRS SEN-5).
    public let timestamp: Duration
    public let width: Int
    public let height: Int

    public var aspect: Double {
        height > 0 ? Double(width) / Double(height) : 1
    }
}

public enum CameraError: Error, CustomStringConvertible {
    case permissionDenied
    case noDeviceAvailable
    case cannotAddInput
    case cannotAddOutput

    public var description: String {
        switch self {
        case .permissionDenied:
            "camera access was not granted; enable it in System Settings › Privacy & Security › Camera"
        case .noDeviceAvailable: "no camera device is available"
        case .cannotAddInput: "the camera could not be added to the capture session"
        case .cannotAddOutput: "the video output could not be added to the capture session"
        }
    }
}

/// Camera capture with latest-frame handoff.
///
/// Frames are delivered through an `AsyncStream` buffering exactly one element.
/// When the consumer is still working, the newest frame replaces the pending one
/// instead of queueing behind it: in an interactive pointer a stale frame is
/// worse than a dropped one, and a queue would trade latency for throughput
/// (SRS SEN-4).
public final class CameraSource: NSObject, @unchecked Sendable {
    private let session = AVCaptureSession()
    private let output = AVCaptureVideoDataOutput()
    private let queue = DispatchQueue(label: "app.visiondrop.camera", qos: .userInteractive)

    private var continuation: AsyncStream<CapturedFrame>.Continuation?
    private let lock = NSLock()

    /// Frames dropped by AVFoundation because the consumer was still busy.
    /// Reported so the drop rate can be checked against its budget (SRS PERF-8).
    public private(set) var droppedFrames = 0

    public private(set) var deviceIdentifier = "unknown"
    public private(set) var isMirrored = false

    /// The frame rate the device was actually configured for, which may be
    /// below the requested rate if no format supports it (SRS SEN-1).
    public private(set) var frameRate: Double = 0

    /// The current camera authorization, described for a person.
    ///
    /// Reads the state without prompting, so it is safe to call from a status
    /// display (SRS APP-4, APP-5).
    public static var authorizationDescription: String {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: "granted"
        case .notDetermined: "not requested yet"
        case .denied: "denied — enable in System Settings › Privacy & Security › Camera"
        case .restricted: "restricted by policy"
        @unknown default: "unknown"
        }
    }

    /// Cameras the system can capture from (SRS SEN-10).
    public static func availableDevices() -> [(id: String, name: String)] {
        AVCaptureDevice.DiscoverySession(
            deviceTypes: [.builtInWideAngleCamera, .external, .continuityCamera],
            mediaType: .video,
            position: .unspecified
        ).devices.map { ($0.uniqueID, $0.localizedName) }
    }

    /// Requests camera access, prompting the user the first time.
    public static func requestAccess() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: true
        case .notDetermined: await AVCaptureDevice.requestAccess(for: .video)
        default: false
        }
    }

    /// Starts capture and returns the frame stream.
    ///
    /// - Parameters:
    ///   - deviceID: a specific camera's unique ID, or `nil` for the default
    ///     (SRS SEN-10).
    ///   - mirrored: whether to mirror the image. Mirroring is applied here,
    ///     once, at the sensing boundary, and recorded in the session header so
    ///     replay reproduces it (SRS COORD-2).
    ///   - targetFrameRate: frames per second to request. The highest rate the
    ///     device supports is used when it cannot reach this. The built-in
    ///     FaceTime camera tops out at 30 fps at every resolution it offers.
    ///   - maximumWidth: resolution cap. Hand tracking does not benefit from
    ///     more pixels, and every extra one costs inference time.
    /// - Returns: a stream that yields the most recent frame.
    /// - Throws: ``CameraError`` if access was not granted, no device is
    ///   available, or the session rejects the input or output.
    public func start(
        deviceID: String? = nil,
        mirrored: Bool = true,
        targetFrameRate: Double = 60,
        maximumWidth: Int32 = 1280
    ) throws -> AsyncStream<CapturedFrame> {
        guard AVCaptureDevice.authorizationStatus(for: .video) == .authorized else {
            throw CameraError.permissionDenied
        }

        let discovery = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.builtInWideAngleCamera, .external, .continuityCamera],
            mediaType: .video,
            position: .unspecified
        )
        guard
            let device = deviceID.flatMap({ id in discovery.devices.first { $0.uniqueID == id } })
                ?? discovery.devices.first
        else { throw CameraError.noDeviceAvailable }

        deviceIdentifier = device.uniqueID
        isMirrored = mirrored

        session.beginConfiguration()
        // No session preset is set: a preset picks a format for general-purpose
        // capture and, on the built-in camera, lands on one delivering about
        // 16 fps. Setting the device's `activeFormat` below takes precedence
        // and is the only way to get the rate this pipeline needs (SRS SEN-1).
        // `.inputPriority` would say so explicitly, but it is iOS-only.

        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input) else { throw CameraError.cannotAddInput }
        session.addInput(input)

        try configure(device, targetFrameRate: targetFrameRate, maximumWidth: maximumWidth)

        output.alwaysDiscardsLateVideoFrames = true
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(output) else { throw CameraError.cannotAddOutput }
        session.addOutput(output)

        if let connection = output.connection(with: .video), connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = mirrored
        }

        session.commitConfiguration()

        let (stream, continuation) = AsyncStream<CapturedFrame>.makeStream(
            bufferingPolicy: .bufferingNewest(1)
        )
        lock.withLock { self.continuation = continuation }

        session.startRunning()
        return stream
    }

    /// Selects a capture format and pins the frame duration to it.
    ///
    /// Prefers the highest frame rate up to the target, breaking ties by the
    /// larger frame within the width cap.
    private func configure(
        _ device: AVCaptureDevice,
        targetFrameRate: Double,
        maximumWidth: Int32
    ) throws {
        func width(_ format: AVCaptureDevice.Format) -> Int32 {
            CMVideoFormatDescriptionGetDimensions(format.formatDescription).width
        }
        func maximumRate(_ format: AVCaptureDevice.Format) -> Double {
            format.videoSupportedFrameRateRanges.map(\.maxFrameRate).max() ?? 0
        }

        let candidates = device.formats.filter { width($0) <= maximumWidth }
        guard
            let format = (candidates.isEmpty ? device.formats : candidates).max(by: { first, second in
                let firstRate = min(maximumRate(first), targetFrameRate)
                let secondRate = min(maximumRate(second), targetFrameRate)
                if firstRate != secondRate { return firstRate < secondRate }
                return width(first) < width(second)
            })
        else { return }

        try device.lockForConfiguration()
        defer { device.unlockForConfiguration() }
        device.activeFormat = format

        let rate = min(maximumRate(format), targetFrameRate)
        guard rate > 0 else { return }
        // Pinning both bounds to the same duration stops the device dropping to
        // a slower rate on its own when the scene is dim.
        let duration = CMTime(value: 1, timescale: CMTimeScale(rate.rounded()))
        device.activeVideoMinFrameDuration = duration
        device.activeVideoMaxFrameDuration = duration
        frameRate = rate
    }

    public func stop() {
        session.stopRunning()
        lock.withLock {
            continuation?.finish()
            continuation = nil
        }
    }
}

extension CameraSource: AVCaptureVideoDataOutputSampleBufferDelegate {
    public func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let presentation = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        let frame = CapturedFrame(
            pixelBuffer: pixelBuffer,
            timestamp: .seconds(presentation.seconds),
            width: CVPixelBufferGetWidth(pixelBuffer),
            height: CVPixelBufferGetHeight(pixelBuffer)
        )
        // The yield result says whether the frame was buffered or dropped;
        // dropping is the intended behaviour here, so it is discarded.
        lock.withLock { _ = continuation?.yield(frame) }
    }

    public func captureOutput(
        _ output: AVCaptureOutput,
        didDrop sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        lock.withLock { droppedFrames += 1 }
    }
}
