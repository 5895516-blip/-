import Foundation

/// Pure text helpers: word counting, reading time and Russian plural forms.
enum TextMetrics {

    /// Stage directions such as `[пауза]` are shown in the prompter but are not spoken,
    /// so they do not count as words.
    static let cuePattern = "\\[[^\\]\\n]*\\]"

    /// Converts every kind of line break to `\n`, tabs to spaces and trims trailing whitespace.
    static func normalized(_ text: String) -> String {
        var result = text.replacingOccurrences(of: "\r\n", with: "\n")
        result = result.replacingOccurrences(of: "\r", with: "\n")
        result = result.replacingOccurrences(of: "\u{2028}", with: "\n")
        result = result.replacingOccurrences(of: "\u{2029}", with: "\n")
        result = result.replacingOccurrences(of: "\t", with: "    ")
        while let last = result.unicodeScalars.last, CharacterSet.whitespacesAndNewlines.contains(last) {
            result.unicodeScalars.removeLast()
        }
        return result
    }

    /// UTF-16 ranges of stage directions inside `text`.
    static func cueRanges(in text: String) -> [NSRange] {
        guard text.contains("["), let regex = try? NSRegularExpression(pattern: cuePattern) else { return [] }
        let whole = NSRange(location: 0, length: (text as NSString).length)
        return regex.matches(in: text, range: whole).map { $0.range }
    }

    static func removingCues(_ text: String) -> String {
        guard text.contains("["), let regex = try? NSRegularExpression(pattern: cuePattern) else { return text }
        let whole = NSRange(location: 0, length: (text as NSString).length)
        return regex.stringByReplacingMatches(in: text, range: whole, withTemplate: " ")
    }

    /// Number of spoken words. A word is a whitespace-separated token with at least one letter or digit.
    static func wordCount(_ text: String) -> Int {
        var count = 0
        var hasWordCharacter = false
        for character in removingCues(text) {
            if character.isWhitespace {
                if hasWordCharacter { count += 1 }
                hasWordCharacter = false
            } else if character.isLetter || character.isNumber {
                hasWordCharacter = true
            }
        }
        if hasWordCharacter { count += 1 }
        return count
    }

    /// Seconds needed to read `words` words at `wpm` words per minute.
    static func duration(words: Int, wpm: Double) -> TimeInterval {
        guard wpm > 0, words > 0 else { return 0 }
        return Double(words) / wpm * 60
    }

    /// `75` → `1:15`, `3725` → `1:02:05`.
    static func formatDuration(_ seconds: TimeInterval) -> String {
        guard seconds.isFinite else { return "0:00" }
        let total = max(0, Int(seconds.rounded()))
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let secs = total % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        }
        return String(format: "%d:%02d", minutes, secs)
    }

    /// Russian plural: `plural(1, "слово", "слова", "слов")` → `слово`.
    static func plural(_ number: Int, _ one: String, _ few: String, _ many: String) -> String {
        let n = abs(number) % 100
        let lastDigit = n % 10
        if n >= 11 && n <= 14 { return many }
        if lastDigit == 1 { return one }
        if lastDigit >= 2 && lastDigit <= 4 { return few }
        return many
    }

    static func wordsLabel(_ count: Int) -> String {
        "\(count) \(plural(count, "слово", "слова", "слов"))"
    }

    /// `214 слов · ≈ 1:47`
    static func summary(for text: String, wpm: Double) -> String {
        let words = wordCount(text)
        guard words > 0 else { return "Пока пусто" }
        return "\(wordsLabel(words)) · ≈ \(formatDuration(duration(words: words, wpm: wpm)))"
    }
}
