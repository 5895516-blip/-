import Foundation
import QuartzCore

/// Time-based scroll position shared by the on-screen prompter and the floating window.
///
/// The position is a normalised `progress`: 0 is the beginning of the script and 1 is the end.
/// It is computed from the current time instead of being advanced frame by frame, so the scroll
/// stays perfectly even regardless of the frame rate and never drifts.
///
/// All methods are thread-safe: the floating window reads the clock from its render queue while
/// the UI changes it on the main thread.
final class ScrollClock {

    struct Snapshot: Equatable {
        var progress: Double
        /// `true` while scrolling or waiting for the countdown to finish.
        var isRunning: Bool
        /// Seconds left before the text starts moving, 0 when it is already moving.
        var countdownRemaining: Double
        /// Progress units per second.
        var rate: Double
        /// `true` when the end of the script has been reached.
        var isAtEnd: Bool { progress >= 1 }
        /// `true` only while the text is actually moving.
        var isMoving: Bool { isRunning && countdownRemaining <= 0 && progress < 1 }
    }

    private let lock = NSLock()
    private var baseProgress: Double = 0
    private var baseTime: CFTimeInterval = 0
    private var rate: Double = 0
    private var running = false

    /// The time source used everywhere in the app (same time base as `CADisplayLink`).
    static func now() -> CFTimeInterval { CACurrentMediaTime() }

    // MARK: Reading

    func progress(at time: CFTimeInterval) -> Double {
        lock.lock()
        defer { lock.unlock() }
        return lockedProgress(at: time)
    }

    func snapshot(at time: CFTimeInterval) -> Snapshot {
        lock.lock()
        defer { lock.unlock() }
        return Snapshot(
            progress: lockedProgress(at: time),
            isRunning: running,
            countdownRemaining: running ? max(0, baseTime - time) : 0,
            rate: rate
        )
    }

    var isRunning: Bool {
        lock.lock()
        defer { lock.unlock() }
        return running
    }

    // MARK: Control

    /// Starts scrolling `delay` seconds after `time` (the delay is the countdown).
    func start(at time: CFTimeInterval, delay: CFTimeInterval = 0) {
        lock.lock()
        defer { lock.unlock() }
        baseProgress = lockedProgress(at: time)
        baseTime = time + max(0, delay)
        running = true
    }

    func pause(at time: CFTimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        baseProgress = lockedProgress(at: time)
        baseTime = time
        running = false
    }

    /// Changes the speed without moving the text.
    func setRate(_ newRate: Double, at time: CFTimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        lockedRebase(at: time)
        rate = max(0, newRate)
    }

    /// Jumps to `progress` (clamped to 0...1). A pending countdown keeps running.
    func setProgress(_ progress: Double, at time: CFTimeInterval) {
        lock.lock()
        defer { lock.unlock() }
        lockedRebase(at: time)
        baseProgress = min(1, max(0, progress))
    }

    // MARK: Private

    private func lockedProgress(at time: CFTimeInterval) -> Double {
        guard running else { return baseProgress }
        let elapsed = max(0, time - baseTime)
        return min(1, max(0, baseProgress + rate * elapsed))
    }

    /// Re-anchors the clock at `time` so that later changes do not affect the past.
    private func lockedRebase(at time: CFTimeInterval) {
        baseProgress = lockedProgress(at: time)
        // While the countdown is still running the start moment must not move.
        baseTime = running ? max(baseTime, time) : time
    }
}
