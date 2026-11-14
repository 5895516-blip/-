import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Title and body of one text, with the button that opens the floating window.
struct ScriptEditorView: View {
    let scriptID: UUID
    @Binding var path: [Route]

    @EnvironmentObject private var store: ScriptStore
    @EnvironmentObject private var settings: AppSettings

    @State private var title = ""
    @State private var text = ""
    @State private var isLoaded = false
    @State private var showImporter = false
    @State private var showClearConfirmation = false
    @State private var importError: String?
    @FocusState private var focusedField: Field?

    private enum Field {
        case title
        case body
    }

    private var hasText: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var body: some View {
        VStack(spacing: 0) {
            TextField("Название", text: $title)
                .font(.system(size: 24, weight: .bold))
                .foregroundColor(.white)
                .submitLabel(.next)
                .focused($focusedField, equals: .title)
                .onSubmit { focusedField = .body }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 10)

            Rectangle()
                .fill(Theme.cardStroke)
                .frame(height: 1)
                .padding(.horizontal, 20)

            ZStack(alignment: .topLeading) {
                TextEditor(text: $text)
                    .font(.system(size: 19))
                    .lineSpacing(5)
                    .foregroundColor(.white)
                    .scrollContentBackground(.hidden)
                    .focused($focusedField, equals: .body)
                    .padding(.horizontal, 15)
                    .padding(.top, 4)
                if text.isEmpty {
                    Text("Вставьте или напишите текст, который будете читать…")
                        .font(.system(size: 19))
                        .foregroundColor(Theme.tertiaryText)
                        .padding(.horizontal, 20)
                        .padding(.top, 12)
                        .allowsHitTesting(false)
                }
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .safeAreaInset(edge: .bottom, spacing: 0) {
            // While typing, the keyboard needs the room; "Готово" on its toolbar brings the bar back.
            if focusedField == nil {
                bottomBar
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button {
                        pasteFromClipboard()
                    } label: {
                        Label("Вставить из буфера", systemImage: "doc.on.clipboard")
                    }
                    Button {
                        showImporter = true
                    } label: {
                        Label("Загрузить из файла…", systemImage: "folder")
                    }
                    Button(role: .destructive) {
                        showClearConfirmation = true
                    } label: {
                        Label("Очистить текст", systemImage: "trash")
                    }
                    .disabled(!hasText)
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
                .accessibilityLabel("Действия с текстом")
            }
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Готово") {
                    focusedField = nil
                }
                .font(.system(size: 16, weight: .semibold))
            }
        }
        .onAppear(perform: load)
        .onDisappear {
            save()
            store.flush()
            store.removeIfEmpty(id: scriptID)
        }
        .onChange(of: title) { _ in save() }
        .onChange(of: text) { _ in save() }
        .fileImporter(isPresented: $showImporter, allowedContentTypes: [.plainText, .text]) { result in
            importFile(result)
        }
        .confirmationDialog("Очистить весь текст?", isPresented: $showClearConfirmation, titleVisibility: .visible) {
            Button("Очистить", role: .destructive) {
                text = ""
            }
            Button("Отмена", role: .cancel) {}
        }
        .alert("Не удалось открыть файл", isPresented: Binding(
            get: { importError != nil },
            set: { if !$0 { importError = nil } }
        )) {
            Button("Понятно", role: .cancel) {}
        } message: {
            Text(importError ?? "")
        }
    }

    private var bottomBar: some View {
        VStack(spacing: 10) {
            Text(TextMetrics.summary(for: text, wpm: settings.wordsPerMinute))
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(Theme.secondaryText)
            Button {
                focusedField = nil
                save()
                path.append(.floating(scriptID))
            } label: {
                Label("Плавающее окно", systemImage: "pip.enter")
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!hasText)
            .opacity(hasText ? 1 : 0.45)
        }
        .padding(.horizontal, 16)
        .padding(.top, 10)
        .padding(.bottom, 8)
        .background(Theme.background.opacity(0.96))
    }

    // MARK: Actions

    private func load() {
        guard !isLoaded, let script = store.script(with: scriptID) else { return }
        isLoaded = true
        title = script.title
        text = script.text
        if script.isEmpty {
            focusedField = .body
        }
    }

    private func save() {
        guard isLoaded else { return }
        store.update(id: scriptID, title: title, text: text)
    }

    private func pasteFromClipboard() {
        guard let pasted = UIPasteboard.general.string, !pasted.isEmpty else { return }
        if hasText {
            text += "\n\n" + pasted
        } else {
            text = pasted
        }
    }

    private func importFile(_ result: Result<URL, Error>) {
        switch result {
        case .failure(let error):
            importError = error.localizedDescription
        case .success(let url):
            let needsStop = url.startAccessingSecurityScopedResource()
            defer {
                if needsStop { url.stopAccessingSecurityScopedResource() }
            }
            guard let data = try? Data(contentsOf: url) else {
                importError = "Файл не читается."
                return
            }
            // Plain-text files in Russian are often saved in Windows-1251.
            let decoded = String(data: data, encoding: .utf8)
                ?? String(data: data, encoding: .utf16)
                ?? String(data: data, encoding: .windowsCP1251)
            guard let decoded, !decoded.isEmpty else {
                importError = "В файле нет текста, который получилось прочитать."
                return
            }
            if hasText {
                text += "\n\n" + decoded
            } else {
                text = decoded
            }
            if title.trimmingCharacters(in: .whitespaces).isEmpty {
                title = url.deletingPathExtension().lastPathComponent
            }
        }
    }
}
