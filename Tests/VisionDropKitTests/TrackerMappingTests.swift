import Testing
import Vision
import VisionDropCore

@testable import VisionDropKit

/// These run headless: the joint mapping and the handedness geometry are pure
/// functions, so no camera or permission is needed to verify them (SRS MNT-1).
@Suite("Vision tracker mapping")
struct TrackerMappingTests {

    @Test("every joint maps to a distinct Vision joint")
    func mappingIsInjective() {
        let mapped = HandJoint.allCases.map(\.visionJointName)
        #expect(mapped.count == 21)
        #expect(Set(mapped).count == 21, "two landmarks map to the same Vision joint")
    }

    /// If Vision ever grows or renames a joint, this fails rather than silently
    /// dropping landmarks.
    @Test("the mapping covers every joint Vision reports")
    func mappingCoversVisionsJoints() {
        let ours = Set(HandJoint.allCases.map(\.visionJointName))
        let theirs = Set(DetectHumanHandPoseRequest().supportedJointNames)
        #expect(
            theirs.subtracting(ours).isEmpty,
            "Vision reports joints this build ignores: \(theirs.subtracting(ours))")
    }

    @Test("the thumb knuckle maps across the naming difference")
    func thumbKnuckleMapsAcrossNaming() {
        // Vision calls it thumbMP, MediaPipe calls it thumbMCP; same joint.
        #expect(HandJoint.thumbMCP.visionJointName == .thumbMP)
    }

    // MARK: Handedness

    /// Anchors matching an upright hand in Vision's space, thumb to the left.
    private func knuckles(mirrored: Bool) -> [Landmark?] {
        func flip(_ x: Double) -> Double { mirrored ? 1 - x : x }
        var points = [Landmark?](repeating: nil, count: 21)
        points[HandJoint.wrist.rawValue] = Landmark(x: flip(0.50), y: 0.12, confidence: 0.9)
        points[HandJoint.indexMCP.rawValue] = Landmark(x: flip(0.53), y: 0.30, confidence: 0.9)
        points[HandJoint.littleMCP.rawValue] = Landmark(x: flip(0.44), y: 0.28, confidence: 0.9)
        return points
    }

    @Test("handedness is derived from geometry, not from Vision's chirality")
    func handednessFlipsWithTheHand() {
        let upright = VisionHandTracker.chirality(of: knuckles(mirrored: false))
        let flipped = VisionHandTracker.chirality(of: knuckles(mirrored: true))

        #expect(upright != .unknown)
        #expect(flipped != .unknown)
        #expect(upright != flipped, "mirroring the hand must change which hand it is")
    }

    @Test("handedness is unknown rather than guessed when knuckles are missing")
    func handednessUnknownWithoutKnuckles() {
        var points = knuckles(mirrored: false)
        points[HandJoint.littleMCP.rawValue] = nil
        #expect(VisionHandTracker.chirality(of: points) == .unknown)
    }

    @Test("a collapsed hand yields unknown handedness rather than a coin flip")
    func degenerateHandednessIsUnknown() {
        let collapsed = [Landmark?](
            repeating: Landmark(x: 0.5, y: 0.5, confidence: 0.9), count: 21)
        #expect(VisionHandTracker.chirality(of: collapsed) == .unknown)
    }
}
