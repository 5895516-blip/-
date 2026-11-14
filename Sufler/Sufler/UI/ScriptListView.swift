import SwiftUI

/// The home screen: all texts, newest edits first.
struct ScriptListView: View {
    @EnvironmentObject private var store: ScriptStore
    @EnvironmentObject private var settings: AppSettings
    @Binding var path: [Route]

    var body: some View {
        Group {
            if store.scripts.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle("Суфлёр")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: addScript) {
                    Image(systemName: "plus")
                        .font(.system(size: 17, weight: .semibold))
                }
                .accessibilityLabel("Новый текст")
            }
        }
    }

    private var list: some View {
        List {
            ForEach(store.scripts) { script in
                ScriptRow(
                    script: script,
                    summary: TextMetrics.summary(for: script.text, wpm: settings.wordsPerMinute),
                    onOpen: { path.append(.editor(script.id)) },
                    onLaunch: { path.append(.floating(script.id)) }
                )
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        store.delete(id: script.id)
                    } label: {
                        Label("Удалить", systemImage: "trash")
                    }
                    Button {
                        store.duplicate(id: script.id)
                    } label: {
                        Label("Копия", systemImage: "doc.on.doc")
                    }
                    .tint(.gray)
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
    }

    private var emptyState: some View {
        VStack(spacing: 14) {
            Image(systemName: "text.alignleft")
                .font(.system(size: 44, weight: .semibold))
                .foregroundColor(Theme.accent)
            Text("Пока нет текстов")
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(.white)
            Text("Добавьте текст, который будете читать на камеру.")
                .font(.system(size: 15))
                .foregroundColor(Theme.secondaryText)
                .multilineTextAlignment(.center)
            Button(action: addScript) {
                Label("Новый текст", systemImage: "plus")
            }
            .buttonStyle(PrimaryButtonStyle())
            .padding(.top, 8)
        }
        .padding(.horizontal, 40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func addScript() {
        let script = store.addScript()
        path.append(.editor(script.id))
    }
}

/// One text in the list: tap the card to edit, tap the round button to open the floating window.
private struct ScriptRow: View {
    let script: Script
    let summary: String
    let onOpen: () -> Void
    let onLaunch: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Button(action: onOpen) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(script.displayTitle)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundColor(.white)
                        .lineLimit(1)
                    if !script.preview.isEmpty {
                        Text(script.preview)
                            .font(.system(size: 14))
                            .foregroundColor(Theme.secondaryText)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                    Text(summary)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(Theme.tertiaryText)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Button(action: onLaunch) {
                Image(systemName: "pip.enter")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.black)
                    .frame(width: 48, height: 48)
                    .background(Circle().fill(Theme.accent))
                    .contentShape(Circle())
            }
            .buttonStyle(PressScaleButtonStyle())
            .accessibilityLabel("Запустить плавающее окно")
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous).fill(Theme.card)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(Theme.cardStroke, lineWidth: 1)
        )
    }
}
