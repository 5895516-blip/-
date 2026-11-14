import SwiftUI
import UIKit

/// Hosts the preview layer, which is also the on-screen anchor of the floating window.
struct FloatingSourceView: UIViewRepresentable {
    let view: SampleBufferView

    func makeUIView(context: Context) -> SampleBufferView { view }
    func updateUIView(_ uiView: SampleBufferView, context: Context) {}
}

/// The main screen: preview of the floating window, the launch button and all the controls.
struct FloatingScreen: View {
    let scriptID: UUID

    @EnvironmentObject private var store: ScriptStore
    @EnvironmentObject private var settings: AppSettings
    @StateObject private var floating = FloatingPrompter()
    @State private var showBackTapHelp = false

    private var script: Script? { store.script(with: scriptID) }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                preview
                TransportBar(session: floating.session, floating: floating)
                launchSection
                windowCard
                speedCard
                appearanceCard
                howToCard
                diagnosticsNote
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 36)
        }
        .background(Theme.background.ignoresSafeArea())
        .navigationTitle(script?.displayTitle ?? "Плавающее окно")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            floating.prepare(text: script?.text ?? "")
            UIApplication.shared.isIdleTimerDisabled = true
            if UserDefaults.standard.bool(forKey: "sufler.autoplay") {
                floating.togglePlayback()
            }
        }
        .onDisappear {
            floating.shutDown()
            UIApplication.shared.isIdleTimerDisabled = false
        }
        .sheet(isPresented: $showBackTapHelp) {
            BackTapHelpView()
        }
    }

    // MARK: Preview

    private var preview: some View {
        let shape = RoundedRectangle(cornerRadius: 16, style: .continuous)
        return VStack(spacing: 8) {
            FloatingSourceView(view: floating.sourceView)
                .aspectRatio(settings.windowRatio, contentMode: .fit)
                .clipShape(shape)
                .overlay(shape.stroke(Color.white.opacity(0.12), lineWidth: 1))
                .overlay {
                    if floating.isActive && settings.windowStyle == .player {
                        ZStack {
                            shape.fill(Color.black.opacity(0.78))
                            VStack(spacing: 8) {
                                Image(systemName: "pip.fill")
                                    .font(.system(size: 28))
                                    .foregroundColor(Theme.accent)
                                Text("Окно открыто поверх экрана")
                                    .font(.system(size: 15, weight: .semibold))
                                    .foregroundColor(.white)
                            }
                        }
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(maxHeight: 280)
                .contentShape(Rectangle())
                .onTapGesture {
                    floating.togglePlayback()
                    Haptics.tap()
                }
                .accessibilityLabel("Предпросмотр окна с текстом")

            Text(settings.orientation.isLandscape
                 ? "Так окно выглядит, пока телефон вертикально. Поверните телефон — текст встанет ровно."
                 : "Так текст будет выглядеть в окне. Нажмите, чтобы запустить или остановить.")
                .font(.system(size: 12))
                .foregroundColor(Theme.tertiaryText)
                .multilineTextAlignment(.center)
        }
    }

    // MARK: Launch

    private var hasText: Bool {
        !(script?.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
    }

    private var launchSection: some View {
        VStack(spacing: 10) {
            if floating.isActive {
                Button {
                    floating.openSystemCamera()
                } label: {
                    Label("Открыть Камеру", systemImage: "camera.fill")
                }
                .buttonStyle(PrimaryButtonStyle())

                Button {
                    floating.stop()
                } label: {
                    Label("Убрать окно", systemImage: "pip.exit")
                }
                .buttonStyle(SecondaryButtonStyle())

                if floating.cameraNeedsManualOpen {
                    note("Камера сама не открылась. Смахните вверх и откройте её как обычно — окно останется поверх.")
                } else if settings.autoStart {
                    note("Текст поедет сам через \(settings.countdownSeconds) с после того, как вы уйдёте в Камеру.")
                }
            } else {
                Button {
                    Haptics.strong()
                    floating.start(openCamera: settings.openCameraAfterStart)
                } label: {
                    Label(floating.isStarting ? "Запускаю…" : "Запустить поверх Камеры", systemImage: "pip.enter")
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(floating.isStarting || !hasText || !floating.isSupported)
                .opacity(!hasText || !floating.isSupported ? 0.45 : 1)

                if !hasText {
                    note("В этом тексте пока пусто — вернитесь назад и добавьте текст.")
                } else if !floating.isSupported {
                    note("На этом устройстве режим «Картинка в картинке» недоступен.")
                }
            }
            if let message = floating.message {
                note(message, isWarning: true)
            }
        }
    }

    private func note(_ text: String, isWarning: Bool = false) -> some View {
        Text(text)
            .font(.system(size: 13))
            .foregroundColor(isWarning ? Theme.accent : Theme.secondaryText)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 8)
    }

    // MARK: Cards

    private var windowCard: some View {
        SettingsCard(title: "Окно и запуск") {
            VStack(alignment: .leading, spacing: 6) {
                Picker("Тип окна", selection: $settings.windowStyle) {
                    ForEach(FloatingWindowStyle.allCases) { style in
                        Text(style.title).tag(style)
                    }
                }
                .pickerStyle(.segmented)
                Text(settings.windowStyle.explanation)
                    .font(.system(size: 12))
                    .foregroundColor(Theme.tertiaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Toggle("Запускать текст, когда ухожу в Камеру", isOn: $settings.autoStart)

            VStack(alignment: .leading, spacing: 6) {
                Text("Обратный отсчёт")
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                Picker("Обратный отсчёт", selection: $settings.countdownSeconds) {
                    ForEach(AppSettings.Limits.countdownOptions, id: \.self) { seconds in
                        Text(seconds == 0 ? "Нет" : "\(seconds) с").tag(seconds)
                    }
                }
                .pickerStyle(.segmented)
                Text("Столько времени у вас есть после ухода в Камеру, чтобы нажать запись и встать в кадр. При старте вручную отсчёт не дольше 3 секунд.")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.tertiaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Toggle("Сразу открывать Камеру", isOn: $settings.openCameraAfterStart)

            if settings.windowStyle == .player {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Кнопки «15» в окне")
                        .font(.system(size: 15))
                        .foregroundColor(.white)
                    Picker("Кнопки перемотки", selection: $settings.skipMode) {
                        ForEach(FloatingSkipMode.allCases) { mode in
                            Text(mode.title).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    Text(skipModeExplanation)
                        .font(.system(size: 12))
                        .foregroundColor(Theme.tertiaryText)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            Button {
                showBackTapHelp = true
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: "hand.tap.fill")
                        .foregroundColor(Theme.accent)
                    Text("Пауза и старт стуком по телефону")
                        .foregroundColor(.white)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(Theme.tertiaryText)
                }
                .font(.system(size: 15))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .tint(Theme.accent)
    }

    private var skipModeExplanation: String {
        switch settings.skipMode {
        case .auto:
            return "Пока текст едет — делают его медленнее и быстрее. На паузе — листают по абзацам."
        case .speed:
            return "Всегда меняют скорость: левая медленнее, правая быстрее."
        case .seek:
            return "Всегда листают по абзацам: назад и вперёд."
        }
    }

    private var durationNote: String {
        let words = TextMetrics.wordCount(script?.text ?? "")
        let duration = TextMetrics.formatDuration(TextMetrics.duration(words: words, wpm: settings.wordsPerMinute))
        return "Весь текст займёт примерно \(duration). Обычная речь — 110–140 слов в минуту."
    }

    private var speedCard: some View {
        SettingsCard(title: "Скорость") {
            SpeedControl(settings: settings, showsSlider: true, caption: "слов в минуту")
            Text(durationNote)
                .font(.system(size: 13))
                .foregroundColor(Theme.secondaryText)
        }
    }

    private var appearanceCard: some View {
        SettingsCard(title: "Вид окна") {
            LabeledSlider(
                title: "Размер шрифта",
                valueText: "\(Int(settings.fontSize))",
                value: $settings.fontSize,
                range: AppSettings.Limits.fontSize,
                step: 1
            )

            VStack(alignment: .leading, spacing: 6) {
                Text("Форма окна")
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                Picker("Форма окна", selection: $settings.aspect) {
                    ForEach(FloatingAspect.allCases) { aspect in
                        Text(aspect.title).tag(aspect)
                    }
                }
                .pickerStyle(.segmented)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Как держите телефон")
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                Picker("Как держите телефон", selection: $settings.orientation) {
                    ForEach(FloatingOrientation.allCases) { orientation in
                        Text(orientation.title).tag(orientation)
                    }
                }
                .pickerStyle(.segmented)
                Text("Для горизонтального видео текст поворачивается. Стрелка показывает, куда смотрит верх телефона.")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.tertiaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if floating.isActive && settings.windowStyle == .player {
                Text("Если поменять форму или поворот, окно закроется — запустите его заново.")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.accent)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Цвет текста")
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                HStack(spacing: 14) {
                    ForEach(PrompterTextColor.allCases) { color in
                        Button {
                            settings.textColor = color
                        } label: {
                            Circle()
                                .fill(Color(uiColor: color.uiColor))
                                .frame(width: 34, height: 34)
                                .overlay(
                                    Circle()
                                        .stroke(Theme.accent, lineWidth: settings.textColor == color ? 3 : 0)
                                        .padding(-4)
                                )
                        }
                        .buttonStyle(PressScaleButtonStyle())
                        .accessibilityLabel(color.title)
                    }
                }
                .padding(.vertical, 4)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Выравнивание")
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                Picker("Выравнивание", selection: $settings.alignment) {
                    ForEach(PrompterAlignment.allCases) { alignment in
                        Text(alignment.title).tag(alignment)
                    }
                }
                .pickerStyle(.segmented)
            }

            LabeledSlider(
                title: "Расстояние между строками",
                valueText: String(format: "%.2f", settings.lineSpacing),
                value: $settings.lineSpacing,
                range: AppSettings.Limits.lineSpacing,
                step: 0.05
            )

            Toggle("Жирный шрифт", isOn: $settings.boldText)
            Toggle("Стрелка у текущей строки", isOn: $settings.showReadingGuide)
            Toggle("Приглушать прочитанное", isOn: $settings.dimReadLines)
        }
        .tint(Theme.accent)
    }

    private var howToCard: some View {
        SettingsCard(title: "Как снимать") {
            HelpStep(number: 1, text: "Нажмите «Запустить поверх Камеры». Появится окно с текстом.")
            HelpStep(number: 2, text: "В Камере выберите «Видео». Окно перетащите пальцем ближе к объективу, двумя пальцами растяните.")
            if settings.windowStyle == .camera {
                HelpStep(number: 3, text: "Начните запись. В окне идёт отсчёт — после него текст поедет сам.")
                HelpStep(number: 4, text: "Чтобы остановить текст, вернитесь в приложение или настройте стук по телефону.")
            } else {
                HelpStep(number: 3, text: "Начните запись, коснитесь окна и нажмите ▶. После отсчёта текст поедет.")
                HelpStep(number: 4, text: "Если при записи окно спряталось к краю — выберите тип «Для Камеры».")
            }
            HelpStep(number: 5, text: "Окно видите только вы — в запись оно не попадает.")
        }
    }

    @ViewBuilder
    private var diagnosticsNote: some View {
        if let diagnostics = floating.diagnostics {
            VStack(alignment: .leading, spacing: 4) {
                Text("ПРОШЛЫЙ ЗАПУСК ОКНА")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(Theme.tertiaryText)
                Text(diagnostics)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(Theme.tertiaryText)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 4)
        }
    }
}

/// A numbered instruction line.
struct HelpStep: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(.black)
                .frame(width: 22, height: 22)
                .background(Circle().fill(Theme.accent))
            Text(text)
                .font(.system(size: 15))
                .foregroundColor(.white.opacity(0.88))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Explains how to pause and resume the text by tapping the back of the phone.
struct BackTapHelpView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    Text("В окне «Для Камеры» кнопок нет, поэтому управлять текстом можно стуком по задней крышке iPhone — даже когда открыта Камера. Настраивается один раз.")
                        .font(.system(size: 15))
                        .foregroundColor(.white.opacity(0.88))
                        .frame(maxWidth: .infinity, alignment: .leading)

                    SettingsCard(title: "1. Создайте команду") {
                        HelpStep(number: 1, text: "Откройте приложение «Команды» и нажмите +.")
                        HelpStep(number: 2, text: "Нажмите «Добавить действие», в поиске наберите «Суфлёр» и выберите «Старт или пауза суфлёра».")
                        HelpStep(number: 3, text: "Нажмите «Готово». Команда сохранится.")
                    }

                    SettingsCard(title: "2. Назначьте её на стук") {
                        HelpStep(number: 1, text: "Откройте Настройки → Универсальный доступ → Касание → Касание задней панели.")
                        HelpStep(number: 2, text: "Выберите «Двойное касание» и в списке внизу отметьте свою команду.")
                    }

                    SettingsCard(title: "Что ещё можно назначить") {
                        Text("Таким же способом доступны действия «В начало текста», «Абзац назад», «Суфлёр быстрее» и «Суфлёр медленнее» — например, на тройное касание. На iPhone с кнопкой действия их можно повесить и на неё.")
                            .font(.system(size: 15))
                            .foregroundColor(.white.opacity(0.88))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(16)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Стук по телефону")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Готово") { dismiss() }
                        .font(.system(size: 16, weight: .semibold))
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

/// Play, pause, rewind and the elapsed time.
private struct TransportBar: View {
    @ObservedObject var session: PrompterSession
    let floating: FloatingPrompter

    var body: some View {
        HStack(spacing: 14) {
            GlassIconButton(systemName: "backward.end.fill", size: 44, iconSize: 16, label: "В начало") {
                floating.restart()
                Haptics.tap()
            }
            GlassIconButton(systemName: "backward.fill", size: 44, iconSize: 16, label: "Абзац назад") {
                floating.jumpParagraph(forward: false)
                Haptics.tap()
            }
            GlassIconButton(
                systemName: session.isActive ? "pause.fill" : "play.fill",
                size: 58,
                iconSize: 24,
                filled: true,
                label: session.isActive ? "Пауза" : "Старт"
            ) {
                floating.togglePlayback()
                Haptics.tap()
            }
            .disabled(!session.hasText)
            .opacity(session.hasText ? 1 : 0.45)
            GlassIconButton(systemName: "forward.fill", size: 44, iconSize: 16, label: "Абзац вперёд") {
                floating.jumpParagraph(forward: true)
                Haptics.tap()
            }
            Spacer(minLength: 0)
            VStack(alignment: .trailing, spacing: 2) {
                Text(TextMetrics.formatDuration(session.progress * session.totalDuration))
                    .font(.system(size: 17, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundColor(.white)
                Text("из \(TextMetrics.formatDuration(session.totalDuration))")
                    .font(.system(size: 12, weight: .medium))
                    .monospacedDigit()
                    .foregroundColor(Theme.secondaryText)
            }
        }
    }
}
