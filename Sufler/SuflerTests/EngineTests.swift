import XCTest
@testable import Sufler

final class ScrollClockTests: XCTestCase {

    func testProgressAdvancesWithTime() {
        let clock = ScrollClock()
        clock.setRate(0.1, at: 0)
        clock.start(at: 0)
        XCTAssertEqual(clock.progress(at: 5), 0.5, accuracy: 1e-9)
        XCTAssertTrue(clock.snapshot(at: 5).isMoving)
    }

    func testCountdownDelaysTheStart() {
        let clock = ScrollClock()
        clock.setRate(0.1, at: 0)
        clock.start(at: 10, delay: 3)
        XCTAssertEqual(clock.progress(at: 12), 0, accuracy: 1e-9)
        XCTAssertEqual(clock.snapshot(at: 11).countdownRemaining, 2, accuracy: 1e-9)
        XCTAssertFalse(clock.snapshot(at: 12).isMoving)
        XCTAssertTrue(clock.snapshot(at: 14).isMoving)
        XCTAssertEqual(clock.progress(at: 15), 0.2, accuracy: 1e-9)
    }

    func testPauseKeepsThePosition() {
        let clock = ScrollClock()
        clock.setRate(0.1, at: 0)
        clock.start(at: 0)
        clock.pause(at: 4)
        XCTAssertEqual(clock.progress(at: 100), 0.4, accuracy: 1e-9)
        XCTAssertFalse(clock.isRunning)
        clock.start(at: 200)
        XCTAssertEqual(clock.progress(at: 201), 0.5, accuracy: 1e-9)
    }

    func testChangingSpeedDoesNotMoveTheText() {
        let clock = ScrollClock()
        clock.setRate(0.1, at: 0)
        clock.start(at: 0)
        clock.setRate(0.2, at: 2)
        XCTAssertEqual(clock.progress(at: 2), 0.2, accuracy: 1e-9)
        XCTAssertEqual(clock.progress(at: 3), 0.4, accuracy: 1e-9)
    }

    func testStopsAtTheEnd() {
        let clock = ScrollClock()
        clock.setRate(0.5, at: 0)
        clock.start(at: 0)
        XCTAssertEqual(clock.progress(at: 10), 1, accuracy: 1e-9)
        XCTAssertTrue(clock.snapshot(at: 10).isAtEnd)
        XCTAssertFalse(clock.snapshot(at: 10).isMoving)
    }

    func testSeekDuringCountdownKeepsTheCountdown() {
        let clock = ScrollClock()
        clock.setRate(0.1, at: 0)
        clock.start(at: 0, delay: 5)
        clock.setProgress(0.5, at: 1)
        XCTAssertEqual(clock.snapshot(at: 1).countdownRemaining, 4, accuracy: 1e-9)
        XCTAssertEqual(clock.progress(at: 6), 0.6, accuracy: 1e-9)
    }

    func testSeekIsClamped() {
        let clock = ScrollClock()
        clock.setProgress(7, at: 0)
        XCTAssertEqual(clock.progress(at: 0), 1)
        clock.setProgress(-3, at: 0)
        XCTAssertEqual(clock.progress(at: 0), 0)
    }
}

final class TextMetricsTests: XCTestCase {

    func testWordCount() {
        XCTAssertEqual(TextMetrics.wordCount(""), 0)
        XCTAssertEqual(TextMetrics.wordCount("Привет, мир! Это — тест."), 4)
        XCTAssertEqual(TextMetrics.wordCount("one\ntwo\n\nthree   four"), 4)
        XCTAssertEqual(TextMetrics.wordCount("iPhone 15 Pro"), 3)
    }

    func testStageDirectionsAreNotWords() {
        XCTAssertEqual(TextMetrics.wordCount("Раз [пауза, улыбнуться] два"), 2)
        XCTAssertEqual(TextMetrics.cueRanges(in: "a [b] c [d e]").count, 2)
        XCTAssertEqual(TextMetrics.cueRanges(in: "без ремарок").count, 0)
    }

    func testNormalization() {
        XCTAssertEqual(TextMetrics.normalized("a\r\nb\rc"), "a\nb\nc")
        XCTAssertEqual(TextMetrics.normalized("a\tb"), "a    b")
        XCTAssertEqual(TextMetrics.normalized("text \n\n  "), "text")
    }

    func testDuration() {
        XCTAssertEqual(TextMetrics.duration(words: 120, wpm: 120), 60, accuracy: 1e-9)
        XCTAssertEqual(TextMetrics.duration(words: 0, wpm: 120), 0)
        XCTAssertEqual(TextMetrics.formatDuration(75), "1:15")
        XCTAssertEqual(TextMetrics.formatDuration(3725), "1:02:05")
        XCTAssertEqual(TextMetrics.formatDuration(0), "0:00")
    }

    func testRussianPlurals() {
        XCTAssertEqual(TextMetrics.wordsLabel(1), "1 слово")
        XCTAssertEqual(TextMetrics.wordsLabel(2), "2 слова")
        XCTAssertEqual(TextMetrics.wordsLabel(5), "5 слов")
        XCTAssertEqual(TextMetrics.wordsLabel(11), "11 слов")
        XCTAssertEqual(TextMetrics.wordsLabel(21), "21 слово")
        XCTAssertEqual(TextMetrics.wordsLabel(112), "112 слов")
        XCTAssertEqual(TextMetrics.wordsLabel(124), "124 слова")
    }
}

final class PrompterSessionTests: XCTestCase {

    private final class FakeTime {
        var now: CFTimeInterval = 100
    }

    func testPlayCountsDownThenScrollsAndFinishes() {
        let time = FakeTime()
        let session = PrompterSession(now: { time.now })
        session.countdownSeconds = 3
        session.load(text: "раз два три четыре пять шесть")
        session.setSpeed(60) // six words at 60 words per minute: six seconds
        XCTAssertEqual(session.wordCount, 6)
        XCTAssertEqual(session.totalDuration, 6, accuracy: 1e-9)

        session.play()
        XCTAssertEqual(session.phase, .countdown(3))
        XCTAssertTrue(session.isActive)

        time.now += 1.5
        session.refresh()
        XCTAssertEqual(session.phase, .countdown(2))

        time.now += 1.5
        session.refresh()
        XCTAssertEqual(session.phase, .playing)
        XCTAssertEqual(session.progress, 0, accuracy: 1e-9)

        time.now += 3
        session.refresh()
        XCTAssertEqual(session.progress, 0.5, accuracy: 1e-9)

        time.now += 4
        session.refresh()
        XCTAssertEqual(session.phase, .finished)
        XCTAssertFalse(session.isActive)

        // Pressing play at the end starts again from the top.
        session.play()
        XCTAssertEqual(session.progress, 0, accuracy: 1e-9)
        XCTAssertEqual(session.phase, .countdown(3))
        session.pause()
    }

    func testPauseAndRestart() {
        let time = FakeTime()
        let session = PrompterSession(now: { time.now })
        session.countdownSeconds = 0
        session.load(text: "раз два три четыре")
        session.setSpeed(120) // two seconds in total
        session.play()
        time.now += 1
        session.pause()
        XCTAssertEqual(session.phase, .idle)
        XCTAssertEqual(session.progress, 0.5, accuracy: 1e-9)
        time.now += 50
        session.refresh()
        XCTAssertEqual(session.progress, 0.5, accuracy: 1e-9)
        session.restart()
        XCTAssertEqual(session.progress, 0, accuracy: 1e-9)
    }

    func testEmptyTextCannotPlay() {
        let session = PrompterSession(now: { 0 })
        session.load(text: "   \n ")
        session.play()
        XCTAssertEqual(session.phase, .idle)
        XCTAssertFalse(session.hasText)
    }

    func testSpeedChangeKeepsPosition() {
        let time = FakeTime()
        let session = PrompterSession(now: { time.now })
        session.countdownSeconds = 0
        session.load(text: "раз два три четыре пять шесть семь восемь девять десять")
        session.setSpeed(60) // ten seconds
        session.play()
        time.now += 5
        session.setSpeed(120)
        session.refresh()
        XCTAssertEqual(session.progress, 0.5, accuracy: 1e-9)
        time.now += 1
        session.refresh()
        XCTAssertEqual(session.progress, 0.7, accuracy: 1e-9)
        session.pause()
    }
}

final class ScriptStoreTests: XCTestCase {

    private func temporaryDirectory() -> URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("sufler-tests-\(UUID().uuidString)")
    }

    func testChangesSurviveReload() {
        let directory = temporaryDirectory()
        let store = ScriptStore(directory: directory, seedWithSample: false)
        XCTAssertTrue(store.scripts.isEmpty)

        let script = store.addScript(title: "Первый", text: "текст")
        store.update(id: script.id, title: "Новый", text: "другой текст")
        let copy = store.duplicate(id: script.id)
        XCTAssertNotNil(copy)
        store.flush()
        store.waitForPendingWrites()

        let reloaded = ScriptStore(directory: directory, seedWithSample: false)
        XCTAssertEqual(reloaded.scripts.count, 2)
        XCTAssertEqual(reloaded.script(with: script.id)?.title, "Новый")
        XCTAssertEqual(reloaded.script(with: script.id)?.text, "другой текст")

        reloaded.delete(id: script.id)
        XCTAssertEqual(reloaded.scripts.count, 1)
    }

    func testFirstLaunchGetsASample() {
        let store = ScriptStore(directory: temporaryDirectory())
        XCTAssertEqual(store.scripts.count, 1)
        XCTAssertGreaterThan(TextMetrics.wordCount(store.scripts[0].text), 50)
    }

    func testEmptyScriptsAreRemoved() {
        let store = ScriptStore(directory: temporaryDirectory(), seedWithSample: false)
        let empty = store.addScript()
        let filled = store.addScript(title: "", text: "есть текст")
        store.removeIfEmpty(id: empty.id)
        store.removeIfEmpty(id: filled.id)
        XCTAssertEqual(store.scripts.map { $0.id }, [filled.id])
        XCTAssertEqual(filled.displayTitle, "есть текст")
    }
}
