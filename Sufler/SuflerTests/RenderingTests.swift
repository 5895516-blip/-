import XCTest
import CoreVideo
import ImageIO
import UniformTypeIdentifiers
@testable import Sufler

final class ScriptLayoutTests: XCTestCase {

    private let style = PrompterTextStyle(fontSize: 28, bold: true, lineSpacing: 1.25, alignment: .left)
    private let longText = """
    Первый абзац достаточно длинный, чтобы его пришлось переносить на несколько строк в узком окне.

    Второй абзац тоже длинный и тоже переносится, потому что слов в нём заметно больше, чем влезает в строку.
    Третий идёт сразу следом.
    """

    func testWrapsInsideTheWidth() {
        let layout = ScriptLayout(text: longText, width: 300, style: style, cueColor: PrompterPalette.accent)
        XCTAssertGreaterThan(layout.lines.count, 6)
        for line in layout.lines {
            XCTAssertLessThanOrEqual(line.width, 300.5)
        }
        for (previous, next) in zip(layout.lines, layout.lines.dropFirst()) {
            XCTAssertGreaterThanOrEqual(next.top, previous.top + layout.lineHeight - 0.01)
        }
        XCTAssertEqual(layout.totalHeight, layout.lines.last!.top + layout.lineHeight, accuracy: 0.01)
    }

    func testParagraphs() {
        let layout = ScriptLayout(text: longText, width: 300, style: style, cueColor: PrompterPalette.accent)
        XCTAssertEqual(layout.paragraphTops.count, 3)
        XCTAssertEqual(layout.paragraphTops[0], 0)
        let second = layout.paragraphTops[1]
        XCTAssertEqual(layout.paragraphTop(after: 0), second)
        XCTAssertEqual(layout.paragraphTop(before: second + layout.lineHeight * 2), second)
        XCTAssertEqual(layout.paragraphTop(before: second + 1), 0)
        XCTAssertNil(layout.paragraphTop(after: layout.totalHeight))
    }

    func testEmptyText() {
        let layout = ScriptLayout(text: " \n\n ", width: 300, style: style, cueColor: PrompterPalette.accent)
        XCTAssertTrue(layout.isEmpty)
        XCTAssertEqual(layout.totalHeight, 0)
        XCTAssertEqual(layout.lineIndices(from: 0, to: 100), 0..<0)
    }

    func testVisibleLineLookup() {
        let layout = ScriptLayout(text: longText, width: 300, style: style, cueColor: PrompterPalette.accent)
        let height = layout.lineHeight
        XCTAssertEqual(layout.lineIndices(from: 0, to: height * 0.5), 0..<1)
        XCTAssertEqual(layout.lineIndices(from: height * 0.5, to: height * 1.5), 0..<2)
        XCTAssertEqual(layout.lineIndices(from: -1000, to: 100_000), 0..<layout.lines.count)
        XCTAssertEqual(layout.lineIndices(from: layout.totalHeight + 5, to: layout.totalHeight + 50).count, 0)
    }

    func testVeryLongWordIsBroken() {
        let word = String(repeating: "ш", count: 120)
        let layout = ScriptLayout(text: word, width: 200, style: style, cueColor: PrompterPalette.accent)
        XCTAssertGreaterThan(layout.lines.count, 3)
        for line in layout.lines {
            XCTAssertLessThanOrEqual(line.width, 200.5)
        }
    }

    func testCenterAlignment() {
        let centered = PrompterTextStyle(fontSize: 28, bold: true, lineSpacing: 1.25, alignment: .center)
        let layout = ScriptLayout(text: "Да", width: 300, style: centered, cueColor: PrompterPalette.accent)
        XCTAssertEqual(layout.lines.count, 1)
        XCTAssertEqual(layout.lines[0].x, (300 - layout.lines[0].width) / 2, accuracy: 0.01)
    }

    func testReadLinesFade() {
        XCTAssertEqual(ScriptLayout.readOpacity(lineTop: 100, offset: 100, lineHeight: 40), 1, accuracy: 1e-6)
        XCTAssertEqual(ScriptLayout.readOpacity(lineTop: 100, offset: 139, lineHeight: 40), 1, accuracy: 1e-6)
        XCTAssertEqual(ScriptLayout.readOpacity(lineTop: 100, offset: 400, lineHeight: 40), 0.38, accuracy: 1e-6)
    }
}

final class FloatingFrameRendererTests: XCTestCase {

    private let text = """
    Привет! Это пример текста для проверки окна суфлёра.

    Второй абзац нужен, чтобы проверить переходы по абзацам и перенос длинных строк в окне.

    [пауза]

    Третий абзац завершает текст.
    """

    private func content(aspect: FloatingAspect = .wide, turns: Int = 0, fontSize: CGFloat = 28) -> FloatingContent {
        FloatingContent(
            text: text,
            style: PrompterTextStyle(fontSize: fontSize, bold: true, lineSpacing: 1.25, alignment: .left),
            color: .white,
            showGuide: true,
            dimReadLines: true,
            canvasAspect: aspect.ratio,
            quarterTurns: turns
        )
    }

    private func state(progress: Double = 0, moving: Bool = false, countdown: Int? = nil, finished: Bool = false,
                       toast: String? = nil, hint: String? = nil) -> FloatingFrameState {
        FloatingFrameState(progress: progress, isMoving: moving, countdown: countdown, isFinished: finished, toast: toast, hint: hint)
    }

    /// Counts pixels by kind: nearly white text and the amber accent.
    private func pixelStatistics(_ buffer: CVPixelBuffer) -> (white: Int, accent: Int) {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return (0, 0) }
        let width = CVPixelBufferGetWidth(buffer)
        let height = CVPixelBufferGetHeight(buffer)
        let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
        let bytes = base.assumingMemoryBound(to: UInt8.self)
        var white = 0
        var accent = 0
        for y in 0..<height {
            for x in 0..<width {
                let pixel = bytes + y * rowBytes + x * 4
                let blue = Int(pixel[0]), green = Int(pixel[1]), red = Int(pixel[2])
                if red > 215 && green > 215 && blue > 215 {
                    white += 1
                } else if red > 215 && green > 140 && green < 205 && blue < 90 {
                    accent += 1
                }
            }
        }
        return (white, accent)
    }

    /// Saves the frame as PNG when `SUFLER_FRAME_DIR` is set, so the pictures can be inspected.
    private func export(_ buffer: CVPixelBuffer, name: String) {
        guard let directory = ProcessInfo.processInfo.environment["SUFLER_FRAME_DIR"], !directory.isEmpty else { return }
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let context = CGContext(
            data: CVPixelBufferGetBaseAddress(buffer),
            width: CVPixelBufferGetWidth(buffer),
            height: CVPixelBufferGetHeight(buffer),
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: CGColorSpace(name: CGColorSpace.sRGB) ?? CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue
        ), let image = context.makeImage() else { return }
        let folder = URL(fileURLWithPath: directory, isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let url = folder.appendingPathComponent("\(name).png")
        guard let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else { return }
        CGImageDestinationAddImage(destination, image, nil)
        CGImageDestinationFinalize(destination)
    }

    func testDrawsTextAndMarker() throws {
        let renderer = FloatingFrameRenderer()
        let buffer = try XCTUnwrap(renderer.render(content: content(), state: state(), pixelWidth: 1080, pixelHeight: 608))
        XCTAssertEqual(CVPixelBufferGetWidth(buffer), 1080)
        XCTAssertEqual(CVPixelBufferGetHeight(buffer), 608)
        let stats = pixelStatistics(buffer)
        XCTAssertGreaterThan(stats.white, 3000, "the text must be visible")
        XCTAssertGreaterThan(stats.accent, 100, "the reading marker must be visible")
        export(buffer, name: "01-start")
    }

    func testScrolledFrameDiffersFromStart() throws {
        let renderer = FloatingFrameRenderer()
        let start = try XCTUnwrap(renderer.render(content: content(), state: state(), pixelWidth: 720, pixelHeight: 404))
        let startStats = pixelStatistics(start)
        let middle = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.5, moving: true), pixelWidth: 720, pixelHeight: 404))
        let middleStats = pixelStatistics(middle)
        XCTAssertGreaterThan(middleStats.white, 500)
        XCTAssertNotEqual(startStats.white, middleStats.white)
        export(middle, name: "02-middle")
    }

    func testOverlays() throws {
        let renderer = FloatingFrameRenderer()
        let plain = pixelStatistics(try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.3), pixelWidth: 1080, pixelHeight: 608)))

        let countdown = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.3, countdown: 3), pixelWidth: 1080, pixelHeight: 608))
        XCTAssertGreaterThan(pixelStatistics(countdown).accent, plain.accent + 2000, "the countdown digit is drawn in the accent colour")
        export(countdown, name: "03-countdown")

        let toast = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.3, moving: true, toast: "Скорость 130"), pixelWidth: 1080, pixelHeight: 608))
        XCTAssertGreaterThan(pixelStatistics(toast).accent, plain.accent + 2000, "the speed pill is drawn in the accent colour")
        export(toast, name: "04-speed")

        let hint = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.3, hint: "Кнопки «15» листают абзацы"), pixelWidth: 1080, pixelHeight: 608))
        export(hint, name: "05-hint")

        let finished = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 1, finished: true), pixelWidth: 1080, pixelHeight: 608))
        XCTAssertGreaterThan(pixelStatistics(finished).white, 300)
        export(finished, name: "06-finished")
    }

    func testOtherShapesAndRotation() throws {
        let renderer = FloatingFrameRenderer()
        let tall = try XCTUnwrap(renderer.render(content: content(aspect: .tall), state: state(progress: 0.2), pixelWidth: 810, pixelHeight: 1080))
        XCTAssertGreaterThan(pixelStatistics(tall).white, 3000)
        export(tall, name: "07-tall")

        // Horizontal shooting: a 16:9 reading area inside a 9:16 window, turned by a quarter.
        let clockwise = try XCTUnwrap(renderer.render(content: content(turns: 1), state: state(progress: 0.2), pixelWidth: 608, pixelHeight: 1080))
        XCTAssertGreaterThan(pixelStatistics(clockwise).white, 3000)
        export(clockwise, name: "08-landscape-top-left")

        let counterClockwise = try XCTUnwrap(renderer.render(content: content(turns: -1), state: state(progress: 0.2), pixelWidth: 608, pixelHeight: 1080))
        XCTAssertGreaterThan(pixelStatistics(counterClockwise).white, 3000)
        export(counterClockwise, name: "09-landscape-top-right")

        // The same text, the same number of white pixels: turning must not clip or rescale it.
        let upright = try XCTUnwrap(renderer.render(content: content(), state: state(progress: 0.2), pixelWidth: 1080, pixelHeight: 608))
        let uprightWhite = Double(pixelStatistics(upright).white)
        XCTAssertEqual(Double(pixelStatistics(clockwise).white), uprightWhite, accuracy: uprightWhite * 0.10)
        XCTAssertEqual(Double(pixelStatistics(counterClockwise).white), uprightWhite, accuracy: uprightWhite * 0.10)
    }

    func testCanvasKeepsItsArea() {
        for aspect in FloatingAspect.allCases {
            let size = FloatingFrameRenderer.canvasSize(aspect: aspect.ratio)
            XCTAssertEqual(size.width * size.height, FloatingFrameRenderer.canvasArea, accuracy: 0.5)
            XCTAssertEqual(size.width / size.height, aspect.ratio, accuracy: 0.001)
        }
        XCTAssertEqual(FloatingFrameRenderer.canvasSize(aspect: 16.0 / 9.0).width, 360, accuracy: 0.01)
    }

    func testParagraphJumps() {
        let renderer = FloatingFrameRenderer()
        let content = content()
        let second = renderer.paragraphProgress(for: content, from: 0, forward: true)
        XCTAssertGreaterThan(second, 0)
        XCTAssertLessThan(second, 1)
        let third = renderer.paragraphProgress(for: content, from: second, forward: true)
        XCTAssertGreaterThan(third, second)
        XCTAssertEqual(renderer.paragraphProgress(for: content, from: third + 0.01, forward: false), second, accuracy: 0.02)
        XCTAssertEqual(renderer.paragraphProgress(for: content, from: second, forward: false), 0, accuracy: 1e-9)
        // Nothing after the last paragraph: stay where we are.
        XCTAssertEqual(renderer.paragraphProgress(for: content, from: 0.99, forward: true), 0.99, accuracy: 1e-9)
    }

    func testRenderingIsFastEnoughForSixtyFramesPerSecond() throws {
        let renderer = FloatingFrameRenderer()
        let frames = 120
        let started = CFAbsoluteTimeGetCurrent()
        for index in 0..<frames {
            _ = try XCTUnwrap(renderer.render(
                content: content(),
                state: state(progress: Double(index) / Double(frames), moving: true),
                pixelWidth: 1080,
                pixelHeight: 608
            ))
        }
        let perFrame = (CFAbsoluteTimeGetCurrent() - started) / Double(frames)
        print("SUFLER_RENDER_MS_PER_FRAME=\(String(format: "%.2f", perFrame * 1000))")
        // Generous limit: a slow CI simulator must still pass, a phone is several times faster.
        XCTAssertLessThan(perFrame, 0.012)
    }
}

final class SettingsTests: XCTestCase {

    private func freshDefaults() -> UserDefaults {
        let name = "sufler-tests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    func testDefaultsAndPersistence() {
        let defaults = freshDefaults()
        let settings = AppSettings(defaults: defaults)
        XCTAssertEqual(settings.wordsPerMinute, 120)
        XCTAssertEqual(settings.aspect, .wide)
        XCTAssertEqual(settings.orientation, .portrait)
        XCTAssertEqual(settings.countdownSeconds, 3)

        settings.wordsPerMinute = 150
        settings.aspect = .tall
        settings.orientation = .landscapeTopLeft
        settings.countdownSeconds = 5

        let reloaded = AppSettings(defaults: defaults)
        XCTAssertEqual(reloaded.wordsPerMinute, 150)
        XCTAssertEqual(reloaded.aspect, .tall)
        XCTAssertEqual(reloaded.orientation, .landscapeTopLeft)
        XCTAssertEqual(reloaded.countdownSeconds, 5)
    }

    func testSpeedStaysInsideLimits() {
        let settings = AppSettings(defaults: freshDefaults())
        settings.wordsPerMinute = 298
        settings.nudgeSpeed(by: 5)
        XCTAssertEqual(settings.wordsPerMinute, 300)
        settings.nudgeSpeed(by: 5)
        XCTAssertEqual(settings.wordsPerMinute, 300)
        settings.wordsPerMinute = 42
        settings.nudgeSpeed(by: -5)
        XCTAssertEqual(settings.wordsPerMinute, 40)
    }

    func testWindowRatioIsInvertedForHorizontalShooting() {
        let settings = AppSettings(defaults: freshDefaults())
        settings.aspect = .wide
        XCTAssertEqual(settings.windowRatio, 16.0 / 9.0, accuracy: 1e-6)
        settings.orientation = .landscapeTopRight
        XCTAssertEqual(settings.windowRatio, 9.0 / 16.0, accuracy: 1e-6)
        XCTAssertEqual(FloatingOrientation.landscapeTopLeft.quarterTurns, 1)
        XCTAssertEqual(FloatingOrientation.landscapeTopRight.quarterTurns, -1)
    }
}
