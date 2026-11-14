import Foundation
import Combine

/// Keeps all scripts in memory and mirrors them to a JSON file in Application Support.
final class ScriptStore: ObservableObject {

    @Published private(set) var scripts: [Script] = []

    private let fileURL: URL
    private var pendingSave: DispatchWorkItem?
    private let saveQueue = DispatchQueue(label: "sufler.store.save", qos: .utility)

    /// - Parameter directory: where `scripts.json` lives. Tests pass a temporary folder.
    init(directory: URL? = nil, seedWithSample: Bool = true) {
        let folder = directory ?? ScriptStore.defaultDirectory()
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        fileURL = folder.appendingPathComponent("scripts.json")

        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? ScriptStore.decoder.decode([Script].self, from: data) {
            scripts = decoded
        } else if seedWithSample {
            scripts = [ScriptStore.sampleScript()]
            saveNow()
        }
    }

    // MARK: Queries

    func script(with id: UUID) -> Script? {
        scripts.first(where: { $0.id == id })
    }

    // MARK: Mutations

    /// Creates an empty script at the top of the list and returns it.
    @discardableResult
    func addScript(title: String = "", text: String = "") -> Script {
        let script = Script(title: title, text: text)
        scripts.insert(script, at: 0)
        scheduleSave()
        return script
    }

    /// Stores new content for an existing script. Does nothing when the content did not change.
    func update(id: UUID, title: String, text: String) {
        guard let index = scripts.firstIndex(where: { $0.id == id }) else { return }
        guard scripts[index].title != title || scripts[index].text != text else { return }
        scripts[index].title = title
        scripts[index].text = text
        scripts[index].updatedAt = Date()
        scheduleSave()
    }

    func delete(id: UUID) {
        scripts.removeAll(where: { $0.id == id })
        scheduleSave()
    }

    @discardableResult
    func duplicate(id: UUID) -> Script? {
        guard let index = scripts.firstIndex(where: { $0.id == id }) else { return nil }
        let original = scripts[index]
        let copy = Script(title: original.displayTitle + " — копия", text: original.text)
        scripts.insert(copy, at: index + 1)
        scheduleSave()
        return copy
    }

    /// Removes scripts that were created but left completely empty.
    func removeIfEmpty(id: UUID) {
        guard let script = script(with: id), script.isEmpty else { return }
        delete(id: id)
    }

    // MARK: Persistence

    /// Writes pending changes immediately (used when the app goes to the background).
    func flush() {
        pendingSave?.cancel()
        pendingSave = nil
        saveNow()
    }

    private func scheduleSave() {
        pendingSave?.cancel()
        let work = DispatchWorkItem { [weak self] in self?.saveNow() }
        pendingSave = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6, execute: work)
    }

    private func saveNow() {
        let snapshot = scripts
        let url = fileURL
        saveQueue.async {
            guard let data = try? ScriptStore.encoder.encode(snapshot) else { return }
            try? data.write(to: url, options: .atomic)
        }
    }

    /// Blocks until queued writes are on disk. Used by tests.
    func waitForPendingWrites() {
        saveQueue.sync { }
    }

    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }()

    private static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    private static func defaultDirectory() -> URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("Sufler", isDirectory: true)
    }

    // MARK: Sample

    static func sampleScript() -> Script {
        Script(title: "Как пользоваться суфлёром", text: sampleText)
    }

    static let sampleText = """
    Привет! Это пример текста. Прочитайте его вслух — так вы сразу подберёте удобную скорость.

    Нажмите «Запустить поверх Камеры». Текст появится в маленьком окне, которое висит поверх обычной Камеры. Окно можно двигать пальцем и растягивать двумя.

    Читайте строку рядом с жёлтой стрелкой. Поставьте окно ближе к объективу — тогда кажется, что вы смотрите прямо в камеру.

    Когда вы уйдёте в Камеру, в окне пойдёт обратный отсчёт. Успейте нажать запись — после отсчёта текст поедет сам.

    [пауза]

    Ремарки в квадратных скобках подсвечиваются и не считаются словами — в них удобно писать подсказки самому себе.

    В запись окно не попадает: его видите только вы.

    Удалите этот текст, вставьте свой — и в кадр. Удачной съёмки!
    """
}
