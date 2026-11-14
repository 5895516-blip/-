import Foundation
import Combine
import QuartzCore

/// Playback state of one script: start, pause, countdown, speed and position.
///
/// The session lives on the main thread. The actual position is kept by `clock`, which is
/// thread-safe and is read directly by the renderers.
final class PrompterSession: ObservableObject {

    enum Phase: Equatable {
        /// Not started or paused.
        case idle
        /// Counting down before the text starts moving; the value is the number on screen.
        case countdown(Int)
        case playing
        /// The end of the script has been reached.
        case finished
    }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var progress: Double = 0
    @Published private(set) var text: String = ""
    @Published private(set) var wordCount: Int = 0
    @Published private(set) var wordsPerMinute: Double = 120

    let clock = ScrollClock()
    var countdownSeconds: Int = 3

    private let now: () -> CFTimeInterval
    private var ticker: Timer?
    private var scrubWasRunning = false
    private var cancellables = Set<AnyCancellable>()

    init(now: @escaping () -> CFTimeInterval = ScrollClock.now) {
        self.now = now
    }

    deinit {
        ticker?.invalidate()
    }

    /// Follows the speed and countdown preferences.
    func bind(to settings: AppSettings) {
        cancellables.removeAll()
        settings.$wordsPerMinute
            .sink { [weak self] value in self?.setSpeed(value) }
            .store(in: &cancellables)
        settings.$countdownSeconds
            .sink { [weak self] value in self?.countdownSeconds = value }
            .store(in: &cancellables)
    }

    // MARK: Content

    /// Loads a script. Loading the same text again keeps the current position.
    func load(text newText: String) {
        let normalized = TextMetrics.normalized(newText)
        guard normalized != text else { return }
        text = normalized
        wordCount = TextMetrics.wordCount(normalized)
        let time = now()
        clock.pause(at: time)
        clock.setProgress(0, at: time)
        applyRate()
        stopTicker()
        refresh()
    }

    func setSpeed(_ wpm: Double) {
        wordsPerMinute = wpm
        applyRate()
    }

    private func applyRate() {
        // The whole script takes `words / wpm` minutes, whatever the font size and line count.
        let words = Double(max(1, wordCount))
        clock.setRate(wordsPerMinute / 60 / words, at: now())
    }

    // MARK: Derived values

    /// Seconds needed to read the whole script at the current speed.
    var totalDuration: TimeInterval {
        TextMetrics.duration(words: max(1, wordCount), wpm: wordsPerMinute)
    }

    var remainingDuration: TimeInterval {
        (1 - progress) * totalDuration
    }

    /// `true` while the text is moving or the countdown is running.
    var isActive: Bool {
        switch phase {
        case .playing, .countdown: return true
        case .idle, .finished: return false
        }
    }

    var hasText: Bool { wordCount > 0 }

    // MARK: Transport

    /// Starts (after the countdown) from the current position, or from the top when at the end.
    /// - Parameter countdown: seconds to count down first; `nil` uses `countdownSeconds`.
    func play(countdown: Int? = nil) {
        guard hasText else { return }
        let time = now()
        if clock.progress(at: time) >= 0.9995 {
            clock.pause(at: time)
            clock.setProgress(0, at: time)
        }
        clock.start(at: time, delay: Double(max(0, countdown ?? countdownSeconds)))
        startTicker()
        refresh()
    }

    func pause() {
        clock.pause(at: now())
        stopTicker()
        refresh()
    }

    func toggle(countdown: Int? = nil) {
        if clock.isRunning {
            pause()
        } else {
            play(countdown: countdown)
        }
    }

    /// Returns to the beginning and stops.
    func restart() {
        let time = now()
        clock.pause(at: time)
        clock.setProgress(0, at: time)
        stopTicker()
        refresh()
    }

    func seek(to newProgress: Double) {
        clock.setProgress(newProgress, at: now())
        refresh()
    }

    // MARK: Manual scrolling

    func beginScrub() {
        scrubWasRunning = clock.isRunning
        if scrubWasRunning {
            clock.pause(at: now())
        }
    }

    func scrub(to newProgress: Double) {
        clock.setProgress(newProgress, at: now())
        refresh()
    }

    func endScrub() {
        if scrubWasRunning {
            scrubWasRunning = false
            let time = now()
            if clock.progress(at: time) < 0.9995 {
                clock.start(at: time, delay: 0)
                startTicker()
            }
        }
        refresh()
    }

    // MARK: State refresh

    /// Recomputes `phase` and `progress` from the clock. Called by the ticker and after every action.
    func refresh() {
        let time = now()
        let snapshot = clock.snapshot(at: time)
        let newPhase: Phase
        if snapshot.isRunning {
            if snapshot.countdownRemaining > 0 {
                newPhase = .countdown(Int(snapshot.countdownRemaining.rounded(.up)))
            } else if snapshot.progress >= 1 {
                clock.pause(at: time)
                stopTicker()
                newPhase = .finished
            } else {
                newPhase = .playing
            }
        } else {
            newPhase = snapshot.progress >= 1 ? .finished : .idle
        }
        if newPhase != phase { phase = newPhase }
        if snapshot.progress != progress { progress = snapshot.progress }
    }

    private func startTicker() {
        guard ticker == nil else { return }
        let timer = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.refresh()
        }
        timer.tolerance = 0.02
        RunLoop.main.add(timer, forMode: .common)
        ticker = timer
    }

    private func stopTicker() {
        ticker?.invalidate()
        ticker = nil
    }
}
