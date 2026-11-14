import Foundation

/// One teleprompter text.
struct Script: Identifiable, Codable, Equatable, Hashable {
    var id: UUID
    var title: String
    var text: String
    var createdAt: Date
    var updatedAt: Date

    init(id: UUID = UUID(), title: String = "", text: String = "", createdAt: Date = Date(), updatedAt: Date = Date()) {
        self.id = id
        self.title = title
        self.text = text
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    /// Title for lists: the explicit title, otherwise the first line of the text.
    var displayTitle: String {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedTitle.isEmpty { return trimmedTitle }
        let firstLine = text
            .split(whereSeparator: { $0.isNewline })
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .first(where: { !$0.isEmpty }) ?? ""
        if firstLine.isEmpty { return "Без названия" }
        return firstLine.count > 44 ? String(firstLine.prefix(44)) + "…" : firstLine
    }

    /// A short preview of the body for list rows.
    var preview: String {
        let collapsed = text
            .split(whereSeparator: { $0.isNewline })
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
            .joined(separator: " ")
        return collapsed.count > 160 ? String(collapsed.prefix(160)) + "…" : collapsed
    }

    var isEmpty: Bool {
        title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
