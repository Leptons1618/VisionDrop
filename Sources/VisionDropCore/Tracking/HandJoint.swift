/// The 21 hand joints, in the landmark ordering shared by Apple's Vision
/// framework and MediaPipe.
///
/// The raw values match MediaPipe's indices so that session recordings remain
/// readable by either implementation during the port (ARCHITECTURE §5.3).
/// Code addresses joints by name — `landmarks[.thumbTip]`, never `landmarks[4]`.
public enum HandJoint: Int, CaseIterable, Sendable, Codable {
    case wrist = 0

    case thumbCMC = 1
    case thumbMCP = 2
    case thumbIP = 3
    case thumbTip = 4

    case indexMCP = 5
    case indexPIP = 6
    case indexDIP = 7
    case indexTip = 8

    case middleMCP = 9
    case middlePIP = 10
    case middleDIP = 11
    case middleTip = 12

    case ringMCP = 13
    case ringPIP = 14
    case ringDIP = 15
    case ringTip = 16

    case littleMCP = 17
    case littlePIP = 18
    case littleDIP = 19
    case littleTip = 20
}

/// The four long fingers, excluding the thumb, whose extension is measured the
/// same way (`HandFeatures.isExtended`).
public enum Finger: CaseIterable, Sendable {
    case index, middle, ring, little

    /// Metacarpophalangeal joint — the knuckle.
    public var mcp: HandJoint {
        switch self {
        case .index: .indexMCP
        case .middle: .middleMCP
        case .ring: .ringMCP
        case .little: .littleMCP
        }
    }

    /// Proximal interphalangeal joint — the middle knuckle.
    public var pip: HandJoint {
        switch self {
        case .index: .indexPIP
        case .middle: .middlePIP
        case .ring: .ringPIP
        case .little: .littlePIP
        }
    }

    public var tip: HandJoint {
        switch self {
        case .index: .indexTip
        case .middle: .middleTip
        case .ring: .ringTip
        case .little: .littleTip
        }
    }
}
