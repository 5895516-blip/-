import SwiftUI

/// Screens that can be pushed onto the navigation stack.
enum Route: Hashable {
    case editor(UUID)
    case floating(UUID)
}

@main
struct SuflerApp: App {
    @StateObject private var store = ScriptStore()
    @StateObject private var settings = AppSettings.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .environmentObject(settings)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
        .onChange(of: scenePhase) { phase in
            if phase != .active {
                store.flush()
            }
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var store: ScriptStore
    @State private var path: [Route] = []

    var body: some View {
        NavigationStack(path: $path) {
            ScriptListView(path: $path)
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .editor(let id):
                        ScriptEditorView(scriptID: id, path: $path)
                    case .floating(let id):
                        FloatingScreen(scriptID: id)
                    }
                }
        }
        .onAppear(perform: applyLaunchArguments)
    }

    /// Opens a given screen right after launch: `-sufler.screen floating`.
    /// Used to take automated screenshots of the app.
    private func applyLaunchArguments() {
        guard path.isEmpty,
              let screen = UserDefaults.standard.string(forKey: "sufler.screen"),
              let first = store.scripts.first else { return }
        switch screen {
        case "editor":
            path = [.editor(first.id)]
        case "floating":
            path = [.floating(first.id)]
        default:
            break
        }
    }
}
