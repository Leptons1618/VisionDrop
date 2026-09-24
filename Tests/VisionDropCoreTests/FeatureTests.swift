import Testing

@testable import VisionDropCore

@Suite("Hand features")
struct FeatureTests {
    let aspect = 16.0 / 9.0

    @Test("a pinch pose reads closed and an open hand reads open")
    func pinchSeparatesFromOpen() throws {
        let pinched = try #require(HandFeatures(SyntheticHand.make(pose: .pinch), aspect: aspect))
        let open = try #require(HandFeatures(SyntheticHand.make(pose: .open), aspect: aspect))
        let config = PinchConfiguration()

        #expect(pinched.pinchRatio <= config.enterRatio)
        #expect(open.pinchRatio >= config.exitRatio)
    }

    /// The property the whole threshold scheme rests on. If ratios moved with
    /// camera distance, every threshold in `PinchConfiguration` would be a lie
    /// (SRS ENG-1).
    @Test("pinch ratio is invariant to hand size", arguments: [0.5, 0.75, 1.0, 1.5, 2.2])
    func ratioInvariantToScale(scale: Double) throws {
        let reference = try #require(HandFeatures(SyntheticHand.make(pose: .pinch), aspect: aspect))
        let scaled = try #require(
            HandFeatures(SyntheticHand.make(pose: .pinch, scale: scale), aspect: aspect)
        )
        #expect(abs(scaled.pinchRatio - reference.pinchRatio) < 1e-9)
    }

    /// Comparing image-space y was the original demo's second failure: a tilted
    /// hand made a natural pinch fail the extension test (PLAN.md §2 cause 2).
    @Test("finger extension survives rotation", arguments: [-75.0, -30.0, 0.0, 30.0, 75.0, 140.0])
    func extensionInvariantToRotation(degrees: Double) throws {
        let pointing = try #require(
            HandFeatures(SyntheticHand.make(pose: .point, rotationDegrees: degrees), aspect: aspect)
        )
        #expect(pointing.isPointing)

        let open = try #require(
            HandFeatures(SyntheticHand.make(pose: .open, rotationDegrees: degrees), aspect: aspect)
        )
        #expect(open.isOpenPalm)
    }

    @Test("pinch ratio survives rotation", arguments: [-60.0, 0.0, 45.0, 120.0])
    func ratioInvariantToRotation(degrees: Double) throws {
        let reference = try #require(HandFeatures(SyntheticHand.make(pose: .pinch), aspect: 1.0))
        let rotated = try #require(
            HandFeatures(SyntheticHand.make(pose: .pinch, rotationDegrees: degrees), aspect: 1.0)
        )
        // Aspect correction is anisotropic by construction, so this invariance
        // only holds on a square frame. Verified at aspect 1.0 deliberately.
        #expect(abs(rotated.pinchRatio - reference.pinchRatio) < 1e-9)
    }

    @Test("a hand moving across the frame does not change its ratios")
    func ratioInvariantToTranslation() throws {
        let reference = try #require(HandFeatures(SyntheticHand.make(pose: .pinch), aspect: aspect))
        let moved = try #require(
            HandFeatures(SyntheticHand.make(pose: .pinch, translation: (0.2, -0.05)), aspect: aspect)
        )
        #expect(abs(moved.pinchRatio - reference.pinchRatio) < 1e-9)
    }

    @Test("thumb-to-middle pinch is distinguishable from thumb-to-index")
    func middlePinchIsDistinct() throws {
        let features = try #require(HandFeatures(SyntheticHand.make(pose: .middlePinch), aspect: aspect))
        let config = PinchConfiguration()
        #expect(features.middlePinchRatio <= config.middleEnterRatio)
        #expect(features.pinchRatio > config.middleEnterRatio)
    }

    @Test("a hand missing a joint needed for scale yields no features")
    func missingRequiredJointFailsExtraction() {
        for joint in HandLandmarks.requiredJoints {
            let hand = SyntheticHand.make(pose: .pinch, missing: [joint])
            #expect(
                HandFeatures(hand, aspect: aspect) == nil,
                "missing \(joint) should prevent feature extraction")
        }
    }

    /// A partially tracked hand still points, but the engine must know the pose
    /// predicates are not trustworthy so it can hold input (SRS SAF-7).
    @Test("a hand missing a non-essential joint extracts, but is not complete")
    func missingOptionalJointMarksIncomplete() throws {
        let hand = SyntheticHand.make(pose: .pinch, missing: [.littleDIP])
        let features = try #require(HandFeatures(hand, aspect: aspect))
        #expect(!features.isComplete)
        #expect(!features.isPointing)
        #expect(!features.isOpenPalm)
    }

    @Test("closure runs from 0 fully open to 1 fully closed")
    func closureSpansTheRange() throws {
        let config = PinchConfiguration()
        let pinched = try #require(HandFeatures(SyntheticHand.make(pose: .pinch), aspect: aspect))
        let open = try #require(HandFeatures(SyntheticHand.make(pose: .open), aspect: aspect))

        #expect(pinched.closure(config) == 1.0)
        #expect(open.closure(config) < 0.5)
        #expect((0...1).contains(open.closure(config)))
    }

    @Test("a degenerate hand does not produce infinite ratios")
    func degenerateHandIsRejected() {
        let collapsed = HandLandmarks(
            joints: HandJoint.allCases.map { _ in Landmark(x: 0.5, y: 0.5, confidence: 0.9) }
        )
        #expect(HandFeatures(collapsed, aspect: aspect) == nil)
    }
}
