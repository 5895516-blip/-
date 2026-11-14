import Foundation
import Combine
import CoreGraphics

// MARK: - Option types

enum PrompterAlignment: String, CaseIterable, Identifiable {
    case left
    case center

    var id: String { rawValue }
    var title: String {
        switch self {
        case .left: return "Слева"
        case .center: return "По центру"
        }
    }
}

enum PrompterTextColor: String, CaseIterable, Identifiable {
    case white
    case yellow
    case green
    case cyan

    var id: String { rawValue }
    var title: String {
        switch self {
        case .white: return "Белый"
        case .yellow: return "Жёлтый"
        case .green: return "Зелёный"
        case .cyan: return "Голубой"
        }
    }

    /// sRGB components.
    var components: (red: CGFloat, green: CGFloat, blue: CGFloat) {
        switch self {
        case .white: return (1.0, 1.0, 1.0)
        case .yellow: return (1.0, 0.92, 0.35)
        case .green: return (0.55, 1.0, 0.60)
        case .cyan: return (0.55, 0.92, 1.0)
        }
    }
}

/// Shape of the floating window as the reader sees it.
enum FloatingAspect: String, CaseIterable, Identifiable {
    case wide
    case standard
    case square
    case tall

    var id: String { rawValue }
    var title: String {
        switch self {
        case .wide: return "16:9"
        case .standard: return "4:3"
        case .square: return "1:1"
        case .tall: return "3:4"
        }
    }

    /// Width divided by height.
    var ratio: CGFloat {
        switch self {
        case .wide: return 16.0 / 9.0
        case .standard: return 4.0 / 3.0
        case .square: return 1.0
        case .tall: return 3.0 / 4.0
        }
    }
}

/// How the phone is held while shooting. The system Camera keeps its interface vertical, so for
/// horizontal video the text inside the floating window has to be turned by the app itself.
enum FloatingOrientation: String, CaseIterable, Identifiable {
    case portrait
    /// Horizontal, the top of the phone (front camera) points to the left.
    case landscapeTopLeft
    /// Horizontal, the top of the phone (front camera) points to the right.
    case landscapeTopRight

    var id: String { rawValue }
    var title: String {
        switch self {
        case .portrait: return "Вертикально"
        case .landscapeTopLeft: return "Гориз. ◀︎"
        case .landscapeTopRight: return "Гориз. ▶︎"
        }
    }

    /// Clockwise quarter turns applied to the text inside the window.
    var quarterTurns: Int {
        switch self {
        case .portrait: return 0
        case .landscapeTopLeft: return 1
        case .landscapeTopRight: return -1
        }
    }

    var isLandscape: Bool { self != .portrait }
}

/// What the ⏪ ⏩ buttons of the floating window do.
enum FloatingSkipMode: String, CaseIterable, Identifiable {
    /// Speed while the text is moving, paragraph jumps while it is paused.
    case auto
    case speed
    case seek

    var id: String { rawValue }
    var title: String {
        switch self {
        case .auto: return "Авто"
        case .speed: return "Скорость"
        case .seek: return "Перемотка"
        }
    }
}

// MARK: - Settings

/// User preferences, persisted in `UserDefaults`.
final class AppSettings: ObservableObject {

    static let shared = AppSettings()

    enum Limits {
        static let wordsPerMinute: ClosedRange<Double> = 40...300
        static let fontSize: ClosedRange<Double> = 16...52
        static let lineSpacing: ClosedRange<Double> = 1.0...1.8
        static let countdownOptions = [0, 3, 5, 10]
        static let speedStep: Double = 5
        static let floatingSpeedStep: Double = 10
    }

    private enum Key {
        static let wordsPerMinute = "wordsPerMinute"
        static let fontSize = "floatingFontSize"
        static let lineSpacing = "lineSpacing"
        static let alignment = "alignment"
        static let textColor = "textColor"
        static let boldText = "boldText"
        static let showReadingGuide = "showReadingGuide"
        static let dimReadLines = "dimReadLines"
        static let countdownSeconds = "countdownSeconds"
        static let aspect = "floatingAspect"
        static let orientation = "floatingOrientation"
        static let skipMode = "floatingSkipMode"
        static let openCameraAfterStart = "openCameraAfterStart"
    }

    private let defaults: UserDefaults

    @Published var wordsPerMinute: Double { didSet { defaults.set(wordsPerMinute, forKey: Key.wordsPerMinute) } }
    /// Font size in points for a window that is 360 points wide; it scales with the window.
    @Published var fontSize: Double { didSet { defaults.set(fontSize, forKey: Key.fontSize) } }
    @Published var lineSpacing: Double { didSet { defaults.set(lineSpacing, forKey: Key.lineSpacing) } }
    @Published var alignment: PrompterAlignment { didSet { defaults.set(alignment.rawValue, forKey: Key.alignment) } }
    @Published var textColor: PrompterTextColor { didSet { defaults.set(textColor.rawValue, forKey: Key.textColor) } }
    @Published var boldText: Bool { didSet { defaults.set(boldText, forKey: Key.boldText) } }
    @Published var showReadingGuide: Bool { didSet { defaults.set(showReadingGuide, forKey: Key.showReadingGuide) } }
    @Published var dimReadLines: Bool { didSet { defaults.set(dimReadLines, forKey: Key.dimReadLines) } }
    @Published var countdownSeconds: Int { didSet { defaults.set(countdownSeconds, forKey: Key.countdownSeconds) } }
    @Published var aspect: FloatingAspect { didSet { defaults.set(aspect.rawValue, forKey: Key.aspect) } }
    @Published var orientation: FloatingOrientation { didSet { defaults.set(orientation.rawValue, forKey: Key.orientation) } }
    @Published var skipMode: FloatingSkipMode { didSet { defaults.set(skipMode.rawValue, forKey: Key.skipMode) } }
    /// Jump to the system Camera right after the floating window appears.
    @Published var openCameraAfterStart: Bool { didSet { defaults.set(openCameraAfterStart, forKey: Key.openCameraAfterStart) } }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults

        wordsPerMinute = AppSettings.double(defaults, Key.wordsPerMinute, 120, Limits.wordsPerMinute)
        fontSize = AppSettings.double(defaults, Key.fontSize, 28, Limits.fontSize)
        lineSpacing = AppSettings.double(defaults, Key.lineSpacing, 1.25, Limits.lineSpacing)
        alignment = PrompterAlignment(rawValue: defaults.string(forKey: Key.alignment) ?? "") ?? .left
        textColor = PrompterTextColor(rawValue: defaults.string(forKey: Key.textColor) ?? "") ?? .white
        boldText = AppSettings.bool(defaults, Key.boldText, true)
        showReadingGuide = AppSettings.bool(defaults, Key.showReadingGuide, true)
        dimReadLines = AppSettings.bool(defaults, Key.dimReadLines, true)
        let storedCountdown = (defaults.object(forKey: Key.countdownSeconds) as? Int) ?? 3
        countdownSeconds = Limits.countdownOptions.contains(storedCountdown) ? storedCountdown : 3
        aspect = FloatingAspect(rawValue: defaults.string(forKey: Key.aspect) ?? "") ?? .wide
        orientation = FloatingOrientation(rawValue: defaults.string(forKey: Key.orientation) ?? "") ?? .portrait
        skipMode = FloatingSkipMode(rawValue: defaults.string(forKey: Key.skipMode) ?? "") ?? .auto
        openCameraAfterStart = AppSettings.bool(defaults, Key.openCameraAfterStart, true)
    }

    // MARK: Derived values

    var textStyle: PrompterTextStyle {
        PrompterTextStyle(
            fontSize: CGFloat(fontSize),
            bold: boldText,
            lineSpacing: CGFloat(lineSpacing),
            alignment: alignment
        )
    }

    /// Width divided by height of the window in the vertical interface of the phone.
    /// For horizontal shooting the window is turned, so the ratio is inverted.
    var windowRatio: CGFloat {
        orientation.isLandscape ? 1 / aspect.ratio : aspect.ratio
    }

    /// Changes the speed by `delta` words per minute, snapped to 5 and kept inside the limits.
    func nudgeSpeed(by delta: Double) {
        let step = Limits.speedStep
        let snapped = ((wordsPerMinute + delta) / step).rounded() * step
        wordsPerMinute = min(Limits.wordsPerMinute.upperBound, max(Limits.wordsPerMinute.lowerBound, snapped))
    }

    // MARK: Helpers

    private static func double(_ defaults: UserDefaults, _ key: String, _ fallback: Double, _ range: ClosedRange<Double>) -> Double {
        let value = (defaults.object(forKey: key) as? Double) ?? fallback
        return min(range.upperBound, max(range.lowerBound, value))
    }

    private static func bool(_ defaults: UserDefaults, _ key: String, _ fallback: Bool) -> Bool {
        (defaults.object(forKey: key) as? Bool) ?? fallback
    }
}
