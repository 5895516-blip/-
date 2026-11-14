import UIKit
import CoreText

/// How the prompter text looks.
struct PrompterTextStyle: Equatable {
    var fontSize: CGFloat
    var bold: Bool
    /// Multiplier of the natural line height.
    var lineSpacing: CGFloat
    var alignment: PrompterAlignment

    var font: UIFont {
        UIFont.systemFont(ofSize: fontSize, weight: bold ? .semibold : .regular)
    }
}

/// A script broken into lines for a given width.
///
/// The same layout code feeds both the on-screen prompter and the floating window, so the text
/// wraps identically in both. Core Text layout objects must stay on one thread: every consumer
/// builds its own `ScriptLayout` instance.
final class ScriptLayout {

    struct Line {
        let ctLine: CTLine
        /// Horizontal offset of the glyphs inside the layout width.
        let x: CGFloat
        /// Distance from the top of the script to the top of this line.
        let top: CGFloat
        /// Width of the visible glyphs.
        let width: CGFloat
        /// Index of the paragraph in the source text.
        let paragraph: Int
    }

    /// Extra space between paragraphs, as a fraction of the line height.
    static let paragraphGap: CGFloat = 0.38
    /// Height of an empty line in the source text, as a fraction of the line height.
    static let blankLineFactor: CGFloat = 0.62

    let width: CGFloat
    let style: PrompterTextStyle
    let lines: [Line]
    let lineHeight: CGFloat
    /// Distance from the top of a line to its baseline.
    let baselineOffset: CGFloat
    /// Height of the whole script.
    let totalHeight: CGFloat
    /// Top offsets of every paragraph that contains text.
    let paragraphTops: [CGFloat]

    init(text: String, width: CGFloat, style: PrompterTextStyle, cueColor: CGColor) {
        self.style = style
        let usableWidth = max(width, style.fontSize * 2)
        self.width = usableWidth

        let font = style.font as CTFont
        let ascent = CTFontGetAscent(font)
        let descent = CTFontGetDescent(font)
        let leading = CTFontGetLeading(font)
        let height = ((ascent + descent + leading) * style.lineSpacing).rounded(.up)
        lineHeight = height
        baselineOffset = (height - (ascent + descent)) / 2 + ascent

        let fontKey = NSAttributedString.Key(kCTFontAttributeName as String)
        let contextColorKey = NSAttributedString.Key(kCTForegroundColorFromContextAttributeName as String)
        let colorKey = NSAttributedString.Key(kCTForegroundColorAttributeName as String)
        let baseAttributes: [NSAttributedString.Key: Any] = [fontKey: font, contextColorKey: true]

        var builtLines: [Line] = []
        var tops: [CGFloat] = []
        var y: CGFloat = 0
        var previousWasText = false

        let paragraphs = TextMetrics.normalized(text).components(separatedBy: "\n")
        for (index, paragraph) in paragraphs.enumerated() {
            if paragraph.trimmingCharacters(in: .whitespaces).isEmpty {
                // Blank lines before the first paragraph are ignored.
                if !builtLines.isEmpty { y += height * ScriptLayout.blankLineFactor }
                previousWasText = false
                continue
            }
            if previousWasText { y += height * ScriptLayout.paragraphGap }
            previousWasText = true
            tops.append(y)

            let attributed = NSMutableAttributedString(string: paragraph, attributes: baseAttributes)
            for range in TextMetrics.cueRanges(in: paragraph) {
                attributed.removeAttribute(contextColorKey, range: range)
                attributed.addAttribute(colorKey, value: cueColor, range: range)
            }

            let typesetter = CTTypesetterCreateWithAttributedString(attributed)
            let length = attributed.length
            var start = 0
            while start < length {
                var count = CTTypesetterSuggestLineBreak(typesetter, start, Double(usableWidth))
                if count <= 0 { count = 1 }
                count = min(count, length - start)
                let ctLine = CTTypesetterCreateLine(typesetter, CFRange(location: start, length: count))
                let typographicWidth = CGFloat(CTLineGetTypographicBounds(ctLine, nil, nil, nil))
                let trailingWhitespace = CGFloat(CTLineGetTrailingWhitespaceWidth(ctLine))
                let visibleWidth = max(0, typographicWidth - trailingWhitespace)
                let x: CGFloat = style.alignment == .center ? max(0, (usableWidth - visibleWidth) / 2) : 0
                builtLines.append(Line(ctLine: ctLine, x: x, top: y, width: visibleWidth, paragraph: index))
                y += height
                start += count
            }
        }

        lines = builtLines
        paragraphTops = tops
        totalHeight = builtLines.last.map { $0.top + height } ?? 0
    }

    var isEmpty: Bool { lines.isEmpty }

    // MARK: Lookup

    /// Indices of the lines that intersect the vertical span `top..<bottom`.
    func lineIndices(from top: CGFloat, to bottom: CGFloat) -> Range<Int> {
        guard !lines.isEmpty, bottom > top else { return 0..<0 }
        var low = 0
        var high = lines.count
        while low < high {
            let mid = (low + high) / 2
            if lines[mid].top + lineHeight <= top {
                low = mid + 1
            } else {
                high = mid
            }
        }
        var end = low
        while end < lines.count && lines[end].top < bottom {
            end += 1
        }
        return low..<end
    }

    /// Where to land when rewinding from `offset`: the start of the current paragraph, or the
    /// previous one when the current paragraph has only just begun.
    func paragraphTop(before offset: CGFloat) -> CGFloat {
        let threshold = lineHeight * 0.8
        var result: CGFloat = 0
        for top in paragraphTops {
            if top < offset - threshold {
                result = top
            } else {
                break
            }
        }
        return result
    }

    /// Start of the next paragraph after `offset`, or `nil` when there is none.
    func paragraphTop(after offset: CGFloat) -> CGFloat? {
        paragraphTops.first(where: { $0 > offset + 1 })
    }

    /// Lines that have already been read fade out so the eye stays on the current one.
    /// - Returns: 1 for the line being read and everything below it, down to 0.38 for lines above.
    static func readOpacity(lineTop: CGFloat, offset: CGFloat, lineHeight: CGFloat) -> CGFloat {
        guard lineHeight > 0 else { return 1 }
        // 0 when the line sits exactly at the reading mark, 1 when it is one line above it.
        let linesAbove = (offset - lineTop) / lineHeight
        let fade = min(1, max(0, (linesAbove - 1.0) / 0.8))
        return 1 - 0.62 * fade
    }

    // MARK: Drawing

    /// Draws one line with the top-left corner of its box at `origin`.
    /// The context must have a flipped coordinate system (y grows downwards).
    func draw(_ line: Line, in context: CGContext, at origin: CGPoint, color: CGColor, alpha: CGFloat = 1) {
        context.saveGState()
        context.setAlpha(alpha)
        context.setFillColor(color)
        context.textMatrix = CGAffineTransform(scaleX: 1, y: -1)
        context.textPosition = CGPoint(x: origin.x + line.x, y: origin.y + baselineOffset)
        CTLineDraw(line.ctLine, context)
        context.restoreGState()
    }
}

extension PrompterTextColor {
    var cgColor: CGColor {
        let c = components
        return CGColor(srgbRed: c.red, green: c.green, blue: c.blue, alpha: 1)
    }

    var uiColor: UIColor { UIColor(cgColor: cgColor) }
}

enum PrompterPalette {
    /// Accent colour: reading marker, stage directions, progress.
    static let accent = CGColor(srgbRed: 1.0, green: 0.69, blue: 0.125, alpha: 1)
    /// Background of the floating window.
    static let floatingBackground = CGColor(srgbRed: 0.035, green: 0.035, blue: 0.047, alpha: 1)
}
