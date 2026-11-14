import AppIntents

// Actions for the Shortcuts app. They let the prompter be steered while another app, such as the
// Camera, is in front: assign them to Back Tap (Settings › Accessibility › Touch › Back Tap) or
// to the Action Button. They run in the background and do not bring this app to the front.

struct TogglePrompterIntent: AppIntent {
    static let title: LocalizedStringResource = "Старт или пауза суфлёра"
    static let description = IntentDescription("Запускает прокрутку текста в плавающем окне или ставит её на паузу.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult {
        PrompterRemote.toggle()
        return .result()
    }
}

struct RestartPrompterIntent: AppIntent {
    static let title: LocalizedStringResource = "Суфлёр: в начало текста"
    static let description = IntentDescription("Возвращает текст в плавающем окне к началу.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult {
        PrompterRemote.restart()
        return .result()
    }
}

struct PrompterParagraphBackIntent: AppIntent {
    static let title: LocalizedStringResource = "Суфлёр: абзац назад"
    static let description = IntentDescription("Возвращает текст в плавающем окне к началу абзаца.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult {
        PrompterRemote.jumpParagraph(forward: false)
        return .result()
    }
}

struct PrompterFasterIntent: AppIntent {
    static let title: LocalizedStringResource = "Суфлёр быстрее"
    static let description = IntentDescription("Ускоряет прокрутку текста в плавающем окне.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult {
        PrompterRemote.changeSpeed(faster: true)
        return .result()
    }
}

struct PrompterSlowerIntent: AppIntent {
    static let title: LocalizedStringResource = "Суфлёр медленнее"
    static let description = IntentDescription("Замедляет прокрутку текста в плавающем окне.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult {
        PrompterRemote.changeSpeed(faster: false)
        return .result()
    }
}

struct SuflerShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: TogglePrompterIntent(),
            phrases: ["Старт или пауза в \(.applicationName)"],
            shortTitle: "Старт / пауза",
            systemImageName: "playpause.fill"
        )
        AppShortcut(
            intent: RestartPrompterIntent(),
            phrases: ["В начало текста в \(.applicationName)"],
            shortTitle: "В начало",
            systemImageName: "backward.end.fill"
        )
        AppShortcut(
            intent: PrompterParagraphBackIntent(),
            phrases: ["Абзац назад в \(.applicationName)"],
            shortTitle: "Абзац назад",
            systemImageName: "backward.fill"
        )
        AppShortcut(
            intent: PrompterFasterIntent(),
            phrases: ["Быстрее в \(.applicationName)"],
            shortTitle: "Быстрее",
            systemImageName: "hare.fill"
        )
        AppShortcut(
            intent: PrompterSlowerIntent(),
            phrases: ["Медленнее в \(.applicationName)"],
            shortTitle: "Медленнее",
            systemImageName: "tortoise.fill"
        )
    }
}

/// Routes shortcut actions to the floating window that is currently open.
enum PrompterRemote {
    /// The prompter on screen, if any. Set by `FloatingPrompter`.
    static weak var current: FloatingPrompter?

    static func toggle() {
        current?.togglePlayback()
    }

    static func restart() {
        current?.restart()
    }

    static func jumpParagraph(forward: Bool) {
        current?.jumpParagraph(forward: forward)
    }

    static func changeSpeed(faster: Bool) {
        let step = AppSettings.Limits.floatingSpeedStep
        current?.changeSpeed(by: faster ? step : -step)
    }
}
