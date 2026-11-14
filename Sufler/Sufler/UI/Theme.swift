import SwiftUI
import UIKit

/// Colours and shared building blocks of the interface.
enum Theme {
    static let accent = Color(red: 1.0, green: 0.69, blue: 0.125)
    static let background = Color(red: 0.031, green: 0.031, blue: 0.039)
    static let card = Color(red: 0.105, green: 0.105, blue: 0.125)
    static let cardStroke = Color.white.opacity(0.08)
    static let secondaryText = Color.white.opacity(0.62)
    static let tertiaryText = Color.white.opacity(0.38)
}

enum Haptics {
    static func tap() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    static func strong() {
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }
}

/// Filled capsule button: the main action of a screen.
struct PrimaryButtonStyle: ButtonStyle {
    var tint: Color = Theme.accent
    var foreground: Color = .black

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 17, weight: .semibold))
            .foregroundColor(foreground)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(tint.opacity(configuration.isPressed ? 0.75 : 1))
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Quiet button on a dark card.
struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 17, weight: .semibold))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.18 : 0.11))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(Theme.cardStroke, lineWidth: 1)
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Round translucent button.
struct GlassIconButton: View {
    let systemName: String
    var size: CGFloat = 46
    var iconSize: CGFloat = 19
    var tint: Color = .white
    var filled: Bool = false
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: iconSize, weight: .semibold))
                .foregroundColor(filled ? .black : tint)
                .frame(width: size, height: size)
                .background(
                    Circle().fill(filled ? AnyShapeStyle(Theme.accent) : AnyShapeStyle(Material.ultraThinMaterial))
                )
                .overlay(Circle().stroke(Color.white.opacity(filled ? 0 : 0.14), lineWidth: 1))
                .contentShape(Circle())
        }
        .buttonStyle(PressScaleButtonStyle())
        .accessibilityLabel(label)
    }
}

struct PressScaleButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.9 : 1)
            .opacity(configuration.isPressed ? 0.8 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Speed control: minus, value, plus and (optionally) a slider.
struct SpeedControl: View {
    @ObservedObject var settings: AppSettings
    var showsSlider: Bool = true
    var caption: String?
    var onInteraction: () -> Void = {}

    var body: some View {
        HStack(spacing: 10) {
            stepButton(systemName: "minus", label: "Медленнее", delta: -AppSettings.Limits.speedStep)

            if showsSlider {
                VStack(spacing: 2) {
                    valueLabel
                    Slider(
                        value: Binding(
                            get: { settings.wordsPerMinute },
                            set: { newValue in
                                let step = AppSettings.Limits.speedStep
                                let snapped = (newValue / step).rounded() * step
                                if snapped != settings.wordsPerMinute {
                                    settings.wordsPerMinute = snapped
                                }
                                onInteraction()
                            }
                        ),
                        in: AppSettings.Limits.wordsPerMinute
                    )
                    .tint(Theme.accent)
                    .accessibilityLabel("Скорость")
                    .accessibilityValue("\(Int(settings.wordsPerMinute)) слов в минуту")
                }
            } else {
                valueLabel
                    .frame(minWidth: 74)
            }

            stepButton(systemName: "plus", label: "Быстрее", delta: AppSettings.Limits.speedStep)
        }
    }

    private var valueLabel: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text("\(Int(settings.wordsPerMinute))")
                .font(.system(size: 17, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundColor(.white)
            Text(caption ?? "сл/мин")
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(Theme.secondaryText)
                .lineLimit(1)
        }
    }

    private func stepButton(systemName: String, label: String, delta: Double) -> some View {
        Button {
            settings.nudgeSpeed(by: delta)
            Haptics.tap()
            onInteraction()
        } label: {
            Image(systemName: systemName)
                .font(.system(size: 17, weight: .bold))
                .foregroundColor(.white)
                .frame(width: 42, height: 42)
                .background(Circle().fill(Color.white.opacity(0.14)))
                .contentShape(Circle())
        }
        .buttonStyle(PressScaleButtonStyle())
        .accessibilityLabel(label)
    }
}

/// A titled group of controls on a dark card.
struct SettingsCard<Content: View>: View {
    let title: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(Theme.tertiaryText)
                .padding(.leading, 4)
            VStack(alignment: .leading, spacing: 14) {
                content()
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous).fill(Theme.card)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(Theme.cardStroke, lineWidth: 1)
            )
        }
    }
}

/// Slider with a caption and the current value on the right.
struct LabeledSlider: View {
    let title: String
    let valueText: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    var step: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                    .font(.system(size: 15))
                    .foregroundColor(.white)
                Spacer()
                Text(valueText)
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundColor(Theme.secondaryText)
            }
            if let step {
                Slider(value: $value, in: range, step: step)
                    .tint(Theme.accent)
                    .accessibilityLabel(title)
            } else {
                Slider(value: $value, in: range)
                    .tint(Theme.accent)
                    .accessibilityLabel(title)
            }
        }
    }
}
