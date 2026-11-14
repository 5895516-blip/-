import UIKit
import CoreText
import CoreVideo

/// What the floating window shows, captured on the main thread and handed to the render queue.
struct FloatingContent: Equatable {
    var text: String
    var style: PrompterTextStyle
    var color: PrompterTextColor
    var showGuide: Bool
    var dimReadLines: Bool
    /// Width divided by height of the text area as the reader sees it.
    var canvasAspect: CGFloat
    /// Clockwise quarter turns of the text inside the window (for horizontal shooting).
    var quarterTurns: Int

    /// Width divided by height of the window itself, in the vertical interface of the phone.
    var windowRatio: CGFloat {
        quarterTurns == 0 ? canvasAspect : 1 / canvasAspect
    }
}

/// The changing part of a frame.
struct FloatingFrameState: Equatable {
    var progress: Double
    var isMoving: Bool
    /// Number shown during the countdown.
    var countdown: Int?
    var isFinished: Bool
    /// Short message in a pill, for example the new speed.
    var toast: String?
    /// One quiet line at the bottom of the window.
    var hint: String?
}

/// Draws teleprompter frames into pixel buffers. Not thread-safe: use it from one queue only.
final class FloatingFrameRenderer {

    /// Area of the text canvas in points. A 16:9 canvas is 360 × 202.5 points; other shapes keep
    /// the same area, so the chosen font size looks the same in every window shape.
    static let canvasArea: CGFloat = 360 * 202.5
    /// Fraction of the canvas height at which the line being read sits.
    static let readingLineFraction: CGFloat = 0.30

    private struct LayoutKey: Equatable {
        var text: String
        var style: PrompterTextStyle
        var width: CGFloat
    }

    private var layout: ScriptLayout?
    private var layoutKey: LayoutKey?
    private var pool: CVPixelBufferPool?
    private var poolWidth = 0
    private var poolHeight = 0
    private let colorSpace = CGColorSpace(name: CGColorSpace.sRGB) ?? CGColorSpaceCreateDeviceRGB()
    private lazy var fadeGradient: CGGradient? = {
        let opaque = PrompterPalette.floatingBackground
        let clear = opaque.copy(alpha: 0) ?? opaque
        return CGGradient(colorsSpace: colorSpace, colors: [opaque, clear] as CFArray, locations: [0, 1])
    }()

    // MARK: Geometry

    static func canvasSize(aspect: CGFloat) -> CGSize {
        let safeAspect = max(0.2, min(5, aspect))
        return CGSize(width: (canvasArea * safeAspect).squareRoot(), height: (canvasArea / safeAspect).squareRoot())
    }

    private static func leftPadding(showGuide: Bool) -> CGFloat { showGuide ? 22 : 14 }
    private static let rightPadding: CGFloat = 12

    /// Builds (or reuses) the line layout for `content`.
    @discardableResult
    func prepareLayout(for content: FloatingContent) -> ScriptLayout {
        let canvas = FloatingFrameRenderer.canvasSize(aspect: content.canvasAspect)
        let width = canvas.width - FloatingFrameRenderer.leftPadding(showGuide: content.showGuide) - FloatingFrameRenderer.rightPadding
        let key = LayoutKey(text: content.text, style: content.style, width: width)
        if let layout, key == layoutKey {
            return layout
        }
        let newLayout = ScriptLayout(text: content.text, width: width, style: content.style, cueColor: PrompterPalette.accent)
        layout = newLayout
        layoutKey = key
        return newLayout
    }

    /// Progress of the paragraph start to jump to from `progress`, forwards or backwards.
    func paragraphProgress(for content: FloatingContent, from progress: Double, forward: Bool) -> Double {
        let layout = prepareLayout(for: content)
        guard layout.totalHeight > 0 else { return 0 }
        let offset = CGFloat(progress) * layout.totalHeight
        if forward {
            guard let next = layout.paragraphTop(after: offset) else { return progress }
            return Double(next / layout.totalHeight)
        }
        return Double(layout.paragraphTop(before: offset) / layout.totalHeight)
    }

    // MARK: Rendering

    /// Renders one frame. Returns `nil` only when a pixel buffer cannot be allocated.
    func render(content: FloatingContent, state: FloatingFrameState, pixelWidth: Int, pixelHeight: Int) -> CVPixelBuffer? {
        guard pixelWidth > 0, pixelHeight > 0, let buffer = makePixelBuffer(width: pixelWidth, height: pixelHeight) else {
            return nil
        }
        CVPixelBufferLockBaseAddress(buffer, [])
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }

        guard let context = CGContext(
            data: CVPixelBufferGetBaseAddress(buffer),
            width: pixelWidth,
            height: pixelHeight,
            bitsPerComponent: 8,
            bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue
        ) else {
            return nil
        }

        // Top-left origin, y grows downwards, units are pixels.
        context.translateBy(x: 0, y: CGFloat(pixelHeight))
        context.scaleBy(x: 1, y: -1)
        draw(content: content, state: state, in: context,
             size: CGSize(width: pixelWidth, height: pixelHeight), pixelsPerUnit: 1)
        return buffer
    }

    /// Draws one frame into any context whose origin is the top-left corner with y growing
    /// downwards (a pixel buffer after flipping, or a `UIView` in `draw(_:)`).
    ///
    /// - Parameters:
    ///   - size: the drawable area in context units.
    ///   - pixelsPerUnit: resolution of the context, used to keep resting text on whole pixels.
    func draw(content: FloatingContent, state: FloatingFrameState, in context: CGContext, size: CGSize, pixelsPerUnit: CGFloat) {
        guard size.width > 1, size.height > 1 else { return }
        context.saveGState()
        defer { context.restoreGState() }

        context.setFillColor(PrompterPalette.floatingBackground)
        context.fill(CGRect(origin: .zero, size: size))

        let canvas = FloatingFrameRenderer.canvasSize(aspect: content.canvasAspect)
        let turned = content.quarterTurns != 0
        // The drawable area as the reader sees it once the phone is turned.
        let visible = turned ? CGSize(width: size.height, height: size.width) : size
        // The canvas is fitted inside and centred, so a window whose shape is slightly off
        // (the system rounds window sizes) never clips or stretches the text.
        let scale = min(visible.width / canvas.width, visible.height / canvas.height)

        // Turn the canvas for horizontal shooting.
        if content.quarterTurns > 0 {
            context.translateBy(x: size.width, y: 0)
            context.rotate(by: .pi / 2)
        } else if content.quarterTurns < 0 {
            context.translateBy(x: 0, y: size.height)
            context.rotate(by: -.pi / 2)
        }
        // Centre on whole pixels, otherwise resting text would be drawn slightly blurred.
        let resolution = max(1, pixelsPerUnit)
        let insetX = ((visible.width - canvas.width * scale) / 2 * resolution).rounded(.down) / resolution
        let insetY = ((visible.height - canvas.height * scale) / 2 * resolution).rounded(.down) / resolution
        context.translateBy(x: insetX, y: insetY)
        context.scaleBy(x: scale, y: scale)
        context.clip(to: CGRect(origin: .zero, size: canvas))
        context.setShouldSmoothFonts(false)
        context.setAllowsFontSubpixelPositioning(true)
        context.setShouldSubpixelPositionFonts(true)
        context.setAllowsFontSubpixelQuantization(false)
        context.setShouldSubpixelQuantizeFonts(false)

        draw(content: content, state: state, canvas: canvas, scale: scale * pixelsPerUnit, in: context)
    }

    private func draw(content: FloatingContent, state: FloatingFrameState, canvas: CGSize, scale: CGFloat, in context: CGContext) {
        let layout = prepareLayout(for: content)
        let bounds = CGRect(origin: .zero, size: canvas)

        context.setFillColor(PrompterPalette.floatingBackground)
        context.fill(bounds.insetBy(dx: -2, dy: -2))

        let leftPadding = FloatingFrameRenderer.leftPadding(showGuide: content.showGuide)
        let readingY = (canvas.height * FloatingFrameRenderer.readingLineFraction).rounded()
        var offset = CGFloat(state.progress) * layout.totalHeight
        if !state.isMoving {
            // A resting text is snapped to whole pixels so that it stays sharp.
            offset = (offset * scale).rounded() / scale
        }

        // Text
        let textColor = content.color.cgColor
        let top = offset - readingY
        for index in layout.lineIndices(from: top - layout.lineHeight, to: top + canvas.height + layout.lineHeight) {
            let line = layout.lines[index]
            let alpha = content.dimReadLines
                ? ScriptLayout.readOpacity(lineTop: line.top, offset: offset, lineHeight: layout.lineHeight)
                : 1
            var lineY = line.top - top
            if !state.isMoving {
                // Each resting line sits on a whole pixel; while moving they must slide together.
                lineY = (lineY * scale).rounded() / scale
            }
            layout.draw(line, in: context, at: CGPoint(x: leftPadding, y: lineY), color: textColor, alpha: alpha)
        }

        // Soft edges at the top and bottom
        if let fadeGradient {
            let topFade = canvas.height * 0.13
            let bottomFade = canvas.height * 0.20
            context.saveGState()
            context.clip(to: CGRect(x: 0, y: 0, width: canvas.width, height: topFade))
            context.drawLinearGradient(fadeGradient, start: .zero, end: CGPoint(x: 0, y: topFade), options: [])
            context.restoreGState()
            context.saveGState()
            context.clip(to: CGRect(x: 0, y: canvas.height - bottomFade, width: canvas.width, height: bottomFade))
            context.drawLinearGradient(
                fadeGradient,
                start: CGPoint(x: 0, y: canvas.height),
                end: CGPoint(x: 0, y: canvas.height - bottomFade),
                options: []
            )
            context.restoreGState()
        }

        // Reading marker
        if content.showGuide, !layout.isEmpty {
            let size = min(13, max(8, layout.lineHeight * 0.32))
            let centerY = readingY + layout.lineHeight / 2
            context.setFillColor(PrompterPalette.accent)
            context.beginPath()
            context.move(to: CGPoint(x: 6, y: centerY - size / 2))
            context.addLine(to: CGPoint(x: 6 + size * 0.82, y: centerY))
            context.addLine(to: CGPoint(x: 6, y: centerY + size / 2))
            context.closePath()
            context.fillPath()
        }

        // Progress
        let barHeight: CGFloat = 2.5
        context.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.12))
        context.fill(CGRect(x: 0, y: canvas.height - barHeight, width: canvas.width, height: barHeight))
        context.setFillColor(PrompterPalette.accent)
        context.fill(CGRect(x: 0, y: canvas.height - barHeight, width: canvas.width * CGFloat(min(1, max(0, state.progress))), height: barHeight))

        // Messages
        let white = CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1)
        let quiet = CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.6)

        if layout.isEmpty {
            drawText("Текст пустой", font: .systemFont(ofSize: 17, weight: .medium), color: quiet,
                     centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height / 2), in: context)
        } else if state.isFinished {
            drawText("Конец текста", font: .systemFont(ofSize: 17, weight: .semibold), color: white,
                     centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height * 0.58), in: context)
            drawText("Нажмите ▶ — начать сначала", font: .systemFont(ofSize: 11.5, weight: .medium), color: quiet,
                     centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height * 0.58 + 22), in: context)
        }

        if let countdown = state.countdown {
            context.setFillColor(CGColor(srgbRed: 0, green: 0, blue: 0, alpha: 0.62))
            context.fill(bounds)
            let size = min(canvas.height * 0.62, canvas.width * 0.5)
            drawText("\(countdown)", font: FloatingFrameRenderer.roundedFont(size: size, weight: .bold), color: PrompterPalette.accent,
                     centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height / 2), in: context)
        }

        if let toast = state.toast {
            drawPill(toast, centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height - 30), in: context)
        } else if let hint = state.hint {
            drawText(hint, font: .systemFont(ofSize: 11, weight: .medium), color: quiet,
                     centeredAt: CGPoint(x: canvas.width / 2, y: canvas.height - 13), in: context)
        }
    }

    // MARK: Drawing helpers

    private static func roundedFont(size: CGFloat, weight: UIFont.Weight) -> UIFont {
        let base = UIFont.systemFont(ofSize: size, weight: weight)
        if let descriptor = base.fontDescriptor.withDesign(.rounded) {
            return UIFont(descriptor: descriptor, size: size)
        }
        return base
    }

    private func makeLine(_ string: String, font: UIFont, color: CGColor) -> CTLine {
        let attributes: [NSAttributedString.Key: Any] = [
            NSAttributedString.Key(kCTFontAttributeName as String): font as CTFont,
            NSAttributedString.Key(kCTForegroundColorAttributeName as String): color,
        ]
        return CTLineCreateWithAttributedString(NSAttributedString(string: string, attributes: attributes))
    }

    /// Draws a single line of text centred on `point`. Returns the width of the text.
    @discardableResult
    private func drawText(_ string: String, font: UIFont, color: CGColor, centeredAt point: CGPoint, in context: CGContext) -> CGFloat {
        let line = makeLine(string, font: font, color: color)
        var ascent: CGFloat = 0
        var descent: CGFloat = 0
        let width = CGFloat(CTLineGetTypographicBounds(line, &ascent, &descent, nil))
        context.saveGState()
        context.textMatrix = CGAffineTransform(scaleX: 1, y: -1)
        context.textPosition = CGPoint(x: point.x - width / 2, y: point.y + (ascent - descent) / 2)
        CTLineDraw(line, context)
        context.restoreGState()
        return width
    }

    private func drawPill(_ string: String, centeredAt point: CGPoint, in context: CGContext) {
        let font = FloatingFrameRenderer.roundedFont(size: 15, weight: .bold)
        let line = makeLine(string, font: font, color: CGColor(srgbRed: 0, green: 0, blue: 0, alpha: 1))
        let width = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
        let rect = CGRect(x: point.x - width / 2 - 14, y: point.y - 15, width: width + 28, height: 30)
        context.setFillColor(PrompterPalette.accent)
        let radius = min(15, rect.width / 2, rect.height / 2)
        context.addPath(CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil))
        context.fillPath()
        drawText(string, font: font, color: CGColor(srgbRed: 0, green: 0, blue: 0, alpha: 1), centeredAt: point, in: context)
    }

    // MARK: Pixel buffers

    private func makePixelBuffer(width: Int, height: Int) -> CVPixelBuffer? {
        if pool == nil || poolWidth != width || poolHeight != height {
            let attributes: [CFString: Any] = [
                kCVPixelBufferPixelFormatTypeKey: kCVPixelFormatType_32BGRA,
                kCVPixelBufferWidthKey: width,
                kCVPixelBufferHeightKey: height,
                kCVPixelBufferIOSurfacePropertiesKey: [CFString: Any](),
                kCVPixelBufferCGBitmapContextCompatibilityKey: true,
                kCVPixelBufferCGImageCompatibilityKey: true,
            ]
            var newPool: CVPixelBufferPool?
            CVPixelBufferPoolCreate(kCFAllocatorDefault, nil, attributes as CFDictionary, &newPool)
            pool = newPool
            poolWidth = width
            poolHeight = height
        }
        guard let pool else { return nil }
        var buffer: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, &buffer)
        return buffer
    }
}
