import AVFoundation
import AVKit
import Combine
import UIKit

/// A view backed by `AVSampleBufferDisplayLayer`: the preview inside the app and the on-screen
/// anchor of the floating window.
final class SampleBufferView: UIView {
    var onMoveToWindow: (() -> Void)?

    override class var layerClass: AnyClass {
        AVSampleBufferDisplayLayer.self
    }

    var displayLayer: AVSampleBufferDisplayLayer {
        // The layer class is fixed above, so the cast cannot fail.
        layer as! AVSampleBufferDisplayLayer
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            onMoveToWindow?()
        }
    }
}

/// Shows the script in a Picture in Picture window that floats over any other app.
///
/// Two kinds of system window are supported (see `FloatingWindowStyle`):
///
/// - **camera**: a video-call window hosting an ordinary view (`FloatingCanvasView`). iOS keeps
///   it running while the Camera records. It has no buttons, so scrolling starts by itself after
///   the countdown, and Shortcuts actions (Back Tap, Action Button) can pause and resume it.
/// - **player**: a video-player window fed with frames through `AVSampleBufferDisplayLayer`.
///   It has play/pause and skip buttons, but iOS tends to pause and hide it once a recording starts.
///
/// The preview inside the app always uses the sample-buffer layer.
final class FloatingPrompter: NSObject, ObservableObject {

    /// `true` while the floating window is on screen.
    @Published private(set) var isActive = false
    @Published private(set) var isStarting = false
    @Published private(set) var isSupported = AVPictureInPictureController.isPictureInPictureSupported()
    /// A problem to show to the user.
    @Published var message: String?
    /// Set when the system Camera could not be opened automatically.
    @Published private(set) var cameraNeedsManualOpen = false
    /// One-line report about the last time the window was open, for troubleshooting.
    @Published private(set) var diagnostics: String? = UserDefaults.standard.string(forKey: FloatingPrompter.diagnosticsKey)

    let session = PrompterSession()
    let sourceView: SampleBufferView

    private static let diagnosticsKey = "sufler.lastWindowSession"

    private let settings: AppSettings
    private let displayLayer: AVSampleBufferDisplayLayer
    private var controller: AVPictureInPictureController?
    private var controllerStyle: FloatingWindowStyle?
    private var possibleObservation: NSKeyValueObservation?
    private var cancellables = Set<AnyCancellable>()
    private var observers: [NSObjectProtocol] = []
    private var pendingStart = false
    private var openCameraOnStart = false
    private var retriedWithExclusiveAudio = false
    private var startAttempt = 0
    private var housekeeping: Timer?
    private var isPrepared = false
    private var activeSince: Date?

    // Camera-friendly window
    private let callController = AVPictureInPictureVideoCallViewController()
    private let canvasView = FloatingCanvasView()

    // MARK: Render queue state (preview and player window)

    private struct TimedMessage {
        var text: String
        var until: CFTimeInterval
    }

    private struct Signature: Equatable {
        var state: FloatingFrameState
        var contentVersion: Int
        var width: Int
        var height: Int
    }

    private struct SharedState {
        var content: FloatingContent
        var version: Int
        var renderWidth: Int?
        var toast: String?
        var hint: String?
        var previewPaused: Bool
    }

    private let renderQueue = DispatchQueue(label: "sufler.floating.render", qos: .userInteractive)
    private let renderer = FloatingFrameRenderer()
    private var timer: DispatchSourceTimer?
    private var nextSlot: Int64 = 0
    private var lastPTS = CMTime.invalid
    private var lastSignature: Signature?
    private var lastEnqueueTime: CFTimeInterval = 0
    private var formatDescription: CMVideoFormatDescription?

    // MARK: State shared between the main thread and the render queue

    private let lock = NSLock()
    private var content: FloatingContent
    private var contentVersion = 0
    private var renderWidth: Int?
    private var toast: TimedMessage?
    private var hint: TimedMessage?
    private var totalDuration: Double = 1
    private var isInBackground = false
    private var sharedStyle: FloatingWindowStyle?
    private var framesEnqueued = 0
    private var framesEnqueuedInBackground = 0
    private var layerRecoveries = 0

    /// Frames are prepared this long before they are shown, which hides timer jitter.
    private static let lead: CFTimeInterval = 2.0 / 60.0
    private static let frameRate: Double = 60

    init(settings: AppSettings = .shared) {
        self.settings = settings
        let view = SampleBufferView()
        sourceView = view
        displayLayer = view.displayLayer
        content = FloatingPrompter.makeContent(text: "", settings: settings)
        super.init()

        displayLayer.videoGravity = .resizeAspect
        sourceView.backgroundColor = UIColor(cgColor: PrompterPalette.floatingBackground)
        sourceView.onMoveToWindow = { [weak self] in
            self?.makeControllerIfNeeded()
        }

        callController.view.backgroundColor = UIColor(cgColor: PrompterPalette.floatingBackground)
        canvasView.frame = callController.view.bounds
        canvasView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        callController.view.addSubview(canvasView)
        canvasView.frameProvider = { [weak self] time in
            self?.frame(at: time)
        }
        updateCallWindowSize()

        session.bind(to: settings)

        // `objectWillChange` fires before the value changes, so read the new values a moment later.
        settings.objectWillChange
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.syncContent() }
            .store(in: &cancellables)
        session.$phase
            .dropFirst()
            .removeDuplicates()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] phase in self?.phaseChanged(phase) }
            .store(in: &cancellables)

        let center = NotificationCenter.default
        let backgroundObserver = center.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
            self?.appDidEnterBackground()
        }
        let foregroundObserver = center.addObserver(forName: UIApplication.willEnterForegroundNotification, object: nil, queue: .main) { [weak self] _ in
            self?.appWillEnterForeground()
        }
        observers = [backgroundObserver, foregroundObserver]
    }

    deinit {
        timer?.cancel()
        housekeeping?.invalidate()
        possibleObservation?.invalidate()
        for observer in observers {
            NotificationCenter.default.removeObserver(observer)
        }
    }

    // MARK: Lifecycle

    /// Loads the script and starts drawing the preview. Call when the screen appears.
    func prepare(text: String) {
        session.load(text: text)
        syncContent()
        PrompterRemote.current = self
        guard !isPrepared else { return }
        isPrepared = true
        KeepAlive.activateSession()
        startRendering()
        // The window needs its anchor view on screen, which happens right after this call.
        DispatchQueue.main.async { [weak self] in
            self?.makeControllerIfNeeded()
        }
    }

    /// Closes the window and stops drawing. Call when the screen goes away.
    func shutDown() {
        isPrepared = false
        pendingStart = false
        if PrompterRemote.current === self {
            PrompterRemote.current = nil
        }
        if let controller, controller.isPictureInPictureActive {
            controller.stopPictureInPicture()
        }
        session.pause()
        stopRendering()
        canvasView.stop()
        housekeeping?.invalidate()
        housekeeping = nil
        KeepAlive.shared.stop()
        try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
    }

    // MARK: Floating window

    /// Opens the floating window. `openCamera` jumps to the system Camera once the window is up.
    func start(openCamera: Bool) {
        message = nil
        cameraNeedsManualOpen = false
        guard isSupported else {
            message = "На этом устройстве режим «Картинка в картинке» недоступен."
            return
        }
        makeControllerIfNeeded()
        guard let controller else {
            message = "Не удалось подготовить плавающее окно. Закройте этот экран и откройте снова."
            return
        }
        if controller.isPictureInPictureActive {
            if openCamera { openSystemCamera() }
            return
        }
        KeepAlive.activateSession()
        KeepAlive.shared.start()
        openCameraOnStart = openCamera
        isStarting = true
        retriedWithExclusiveAudio = false
        startAttempt += 1
        let attempt = startAttempt
        if controller.isPictureInPicturePossible {
            controller.startPictureInPicture()
        } else {
            // The system may need a moment (a first frame, an active audio session).
            pendingStart = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in
                guard let self, self.startAttempt == attempt, self.pendingStart else { return }
                // Still not possible: some iOS versions want an audio session that does not mix.
                self.retriedWithExclusiveAudio = true
                KeepAlive.activateSession(mixWithOthers: false)
            }
        }
        // Whatever happens, never leave the button stuck in the "starting" state.
        DispatchQueue.main.asyncAfter(deadline: .now() + 4.5) { [weak self] in
            guard let self, self.startAttempt == attempt, self.isStarting, !self.isActive else { return }
            self.pendingStart = false
            self.isStarting = false
            self.openCameraOnStart = false
            KeepAlive.shared.stop()
            self.message = "Окно не запустилось. Проверьте: Настройки → Основные → «Картинка в картинке» — и попробуйте ещё раз."
        }
    }

    func stop() {
        pendingStart = false
        controller?.stopPictureInPicture()
    }

    /// Tries to bring the system Camera to the front. There is no official way to do that, so a
    /// failure only shows a hint.
    func openSystemCamera() {
        guard let url = URL(string: "camera://") else { return }
        UIApplication.shared.open(url, options: [:]) { [weak self] opened in
            DispatchQueue.main.async {
                self?.cameraNeedsManualOpen = !opened
            }
        }
    }

    // MARK: Transport (in-app buttons, window buttons and Shortcuts actions)

    func togglePlayback() {
        session.toggle()
    }

    func restart() {
        session.restart()
        refreshPlayerState()
    }

    /// Jumps to the next or previous paragraph.
    func jumpParagraph(forward: Bool) {
        let current = session.clock.progress(at: ScrollClock.now())
        let content = currentContent()
        renderQueue.async { [weak self] in
            guard let self else { return }
            let target = self.renderer.paragraphProgress(for: content, from: current, forward: forward)
            DispatchQueue.main.async {
                self.session.seek(to: target)
                self.refreshPlayerState()
            }
        }
    }

    /// Changes the speed and shows the new value inside the window.
    func changeSpeed(by delta: Double) {
        let limits = AppSettings.Limits.wordsPerMinute
        let newValue = min(limits.upperBound, max(limits.lowerBound, settings.wordsPerMinute + delta))
        settings.wordsPerMinute = newValue
        showToast("Скорость \(Int(newValue))")
    }

    // MARK: Leaving and returning to the app

    private func appDidEnterBackground() {
        lock.lock()
        isInBackground = true
        lock.unlock()
        autoStartIfNeeded()
    }

    private func appWillEnterForeground() {
        lock.lock()
        isInBackground = false
        lock.unlock()
        if isActive {
            // Back in the app: stop the text so nothing runs away while settings are changed.
            session.pause()
        }
    }

    /// With the window open and the app left behind (the user is in the Camera now), the text
    /// starts by itself after the countdown.
    private func autoStartIfNeeded() {
        guard isActive, settings.autoStart, session.hasText, !session.isActive else { return }
        guard UIApplication.shared.applicationState == .background else { return }
        session.play()
    }

    // MARK: Content

    private static func makeContent(text: String, settings: AppSettings) -> FloatingContent {
        FloatingContent(
            text: text,
            style: settings.textStyle,
            color: settings.textColor,
            showGuide: settings.showReadingGuide,
            dimReadLines: settings.dimReadLines,
            canvasAspect: settings.aspect.ratio,
            quarterTurns: settings.orientation.quarterTurns
        )
    }

    private func currentContent() -> FloatingContent {
        lock.lock()
        defer { lock.unlock() }
        return content
    }

    private func syncContent() {
        let newContent = FloatingPrompter.makeContent(text: session.text, settings: settings)
        let duration = max(1, session.totalDuration)
        lock.lock()
        let shapeChanged = newContent.windowRatio != content.windowRatio
        if newContent != content {
            content = newContent
            contentVersion += 1
        }
        if shapeChanged {
            renderWidth = nil
        }
        let durationChanged = duration != totalDuration
        totalDuration = duration
        lock.unlock()

        if shapeChanged {
            updateCallWindowSize()
            if controllerStyle == .player, let controller, controller.isPictureInPictureActive {
                // A player window cannot change its shape on the fly: close it, the user reopens it.
                controller.stopPictureInPicture()
            }
        }
        if controllerStyle != settings.windowStyle {
            if let controller, controller.isPictureInPictureActive {
                // The new kind of window is set up as soon as this one has closed.
                controller.stopPictureInPicture()
            } else {
                makeControllerIfNeeded()
            }
        }
        if durationChanged {
            refreshPlayerState()
        }
    }

    /// Reads everything a frame needs in one locked step. Expired messages are dropped.
    private func readShared(at time: CFTimeInterval) -> SharedState {
        lock.lock()
        defer { lock.unlock() }
        if let current = toast, current.until <= time { toast = nil }
        if let current = hint, current.until <= time { hint = nil }
        return SharedState(
            content: content,
            version: contentVersion,
            renderWidth: renderWidth,
            toast: toast?.text,
            hint: hint?.text,
            previewPaused: isInBackground && sharedStyle != .player
        )
    }

    /// The frame of the camera-friendly window for a given moment. Main thread.
    private func frame(at time: CFTimeInterval) -> (content: FloatingContent, version: Int, state: FloatingFrameState) {
        let shared = readShared(at: time)
        let state = FloatingPrompter.frameState(session.clock.snapshot(at: time), toast: shared.toast, hint: shared.hint)
        return (shared.content, shared.version, state)
    }

    private func showToast(_ text: String, duration: CFTimeInterval = 1.6) {
        lock.lock()
        toast = TimedMessage(text: text, until: ScrollClock.now() + duration)
        lock.unlock()
    }

    private func showHint(_ text: String?, duration: CFTimeInterval = 4) {
        lock.lock()
        hint = text.map { TimedMessage(text: $0, until: ScrollClock.now() + duration) }
        lock.unlock()
    }

    private func phaseChanged(_ phase: PrompterSession.Phase) {
        refreshPlayerState()
        guard isActive, let style = controllerStyle else {
            showHint(nil)
            return
        }
        switch style {
        case .player:
            switch phase {
            case .playing:
                showHint(settings.skipMode == .seek ? "Кнопки «15» листают абзацы" : "Кнопки «15» меняют скорость")
            case .idle:
                showHint(settings.skipMode == .speed ? "Кнопки «15» меняют скорость" : "Кнопки «15» листают абзацы")
            case .countdown, .finished:
                showHint(nil)
            }
        case .camera:
            switch phase {
            case .idle:
                showHint(settings.autoStart ? "Откройте Камеру — текст поедет сам" : "Старт — кнопкой в приложении", duration: 12)
            case .playing, .countdown, .finished:
                showHint(nil)
            }
        }
    }

    // MARK: Picture in Picture set-up

    private func updateCallWindowSize() {
        let ratio = max(0.2, min(5, currentContent().windowRatio))
        let size = ratio >= 1
            ? CGSize(width: 360, height: (360 / ratio).rounded())
            : CGSize(width: (360 * ratio).rounded(), height: 360)
        callController.preferredContentSize = size
        if !isActive {
            // Give the view a real size before the window opens so the first frame is laid out.
            callController.view.frame = CGRect(origin: .zero, size: size)
            canvasView.frame = callController.view.bounds
        }
    }

    private func makeControllerIfNeeded() {
        guard isSupported else { return }
        let style = settings.windowStyle
        if controller != nil, controllerStyle == style { return }
        if let controller, controller.isPictureInPictureActive { return }

        let source: AVPictureInPictureController.ContentSource
        switch style {
        case .camera:
            // A video-call window is anchored to a view that must already be on screen.
            guard sourceView.window != nil else { return }
            updateCallWindowSize()
            source = AVPictureInPictureController.ContentSource(
                activeVideoCallSourceView: sourceView,
                contentViewController: callController
            )
        case .player:
            source = AVPictureInPictureController.ContentSource(
                sampleBufferDisplayLayer: displayLayer,
                playbackDelegate: self
            )
        }

        possibleObservation?.invalidate()
        let newController = AVPictureInPictureController(contentSource: source)
        newController.delegate = self
        newController.requiresLinearPlayback = false
        newController.canStartPictureInPictureAutomaticallyFromInline = true
        controller = newController
        controllerStyle = style
        lock.lock()
        sharedStyle = style
        lock.unlock()
        possibleObservation = newController.observe(\.isPictureInPicturePossible, options: [.new]) { [weak self] observed, _ in
            let possible = observed.isPictureInPicturePossible
            DispatchQueue.main.async {
                guard let self, possible, self.pendingStart, self.controller === observed else { return }
                self.pendingStart = false
                observed.startPictureInPicture()
            }
        }
    }

    /// Tells the player window that position or play state changed.
    private func refreshPlayerState() {
        guard controllerStyle == .player else { return }
        controller?.invalidatePlaybackState()
    }

    private func startHousekeeping() {
        housekeeping?.invalidate()
        let timer = Timer(timeInterval: 1, repeats: true) { [weak self] _ in
            guard let self, self.isActive else { return }
            KeepAlive.shared.restartIfNeeded()
            // While the text stands still the layer clock keeps running; refresh the timeline.
            if !self.session.clock.snapshot(at: ScrollClock.now()).isMoving {
                self.refreshPlayerState()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        housekeeping = timer
    }

    private func saveDiagnostics() {
        guard let activeSince, let style = controllerStyle else { return }
        let seconds = Int(Date().timeIntervalSince(activeSince))
        let frames: String
        switch style {
        case .camera:
            frames = "кадров \(canvasView.framesDrawn), из них в фоне \(canvasView.framesDrawnInBackground)"
        case .player:
            lock.lock()
            let total = framesEnqueued
            let background = framesEnqueuedInBackground
            let recoveries = layerRecoveries
            lock.unlock()
            frames = "кадров \(total), из них в фоне \(background), восстановлений \(recoveries)"
        }
        let audio = "звук: прерываний \(KeepAlive.shared.interruptions), перезапусков \(KeepAlive.shared.restarts)"
        let text = "\(style.title) · \(seconds) с · \(frames) · \(audio)"
        diagnostics = text
        UserDefaults.standard.set(text, forKey: FloatingPrompter.diagnosticsKey)
    }

    // MARK: Rendering (preview and player window)

    private func startRendering() {
        guard timer == nil else { return }
        let source = DispatchSource.makeTimerSource(flags: .strict, queue: renderQueue)
        source.schedule(deadline: .now(), repeating: 1.0 / FloatingPrompter.frameRate, leeway: .milliseconds(1))
        source.setEventHandler { [weak self] in
            self?.renderTick()
        }
        source.resume()
        timer = source
    }

    private func stopRendering() {
        timer?.cancel()
        timer = nil
    }

    private static func bufferSize(ratio: CGFloat, requestedWidth: Int?) -> (width: Int, height: Int) {
        let safeRatio = max(0.2, min(5, ratio))
        var width: CGFloat
        if let requestedWidth {
            width = CGFloat(requestedWidth)
        } else {
            width = safeRatio >= 1 ? 1080 : 1080 * safeRatio
        }
        width = min(1440, max(240, width))
        var height = width / safeRatio
        if height > 1440 {
            height = 1440
            width = height * safeRatio
        }
        return (max(2, Int(width / 2) * 2), max(2, Int(height / 2) * 2))
    }

    /// Runs on `renderQueue` 60 times a second.
    private func renderTick() {
        let now = ScrollClock.now()
        let shared = readShared(at: now)
        // The preview is invisible while the app is in the background; only a player window
        // (which shows these very frames) has to keep going.
        if shared.previewPaused { return }

        let size = FloatingPrompter.bufferSize(ratio: shared.content.windowRatio, requestedWidth: shared.renderWidth)
        let clock = session.clock
        let rate = FloatingPrompter.frameRate

        // Frames can be scheduled ahead only when the layer runs on the same clock as the app.
        let layerTime = CMTimebaseGetTime(displayLayer.timebase)
        let followsHostClock = layerTime.isNumeric
            && CMTimebaseGetRate(displayLayer.timebase) == 1
            && abs(layerTime.seconds - now) < 0.5
        let lead = followsHostClock ? FloatingPrompter.lead : 0

        if clock.snapshot(at: now + lead).isMoving {
            if followsHostClock {
                // Moving text: frames get exact timestamps on a 60 Hz grid, slightly in the future.
                // The layer shows each one at its moment, so timer jitter never reaches the screen.
                let lastSlot = Int64(((now + lead) * rate).rounded(.down))
                var slot = max(nextSlot, lastSlot - 1)
                while slot <= lastSlot {
                    let time = Double(slot) / rate
                    let state = FloatingPrompter.frameState(clock.snapshot(at: time), toast: shared.toast, hint: shared.hint)
                    enqueue(content: shared.content, state: state, size: size, time: time, scheduled: true)
                    slot += 1
                }
                nextSlot = lastSlot + 1
            } else {
                // Unknown layer clock: show every frame as soon as it is ready.
                let state = FloatingPrompter.frameState(clock.snapshot(at: now), toast: shared.toast, hint: shared.hint)
                enqueue(content: shared.content, state: state, size: size, time: now, scheduled: false)
            }
            lastSignature = nil
        } else {
            // Still text: draw only when something changed, plus a keep-alive twice a second.
            let state = FloatingPrompter.frameState(clock.snapshot(at: now), toast: shared.toast, hint: shared.hint)
            let signature = Signature(state: state, contentVersion: shared.version, width: size.width, height: size.height)
            if signature != lastSignature || now - lastEnqueueTime > 0.5 {
                enqueue(content: shared.content, state: state, size: size, time: now, scheduled: false)
                lastSignature = signature
            }
        }
    }

    private static func frameState(_ snapshot: ScrollClock.Snapshot, toast: String?, hint: String?) -> FloatingFrameState {
        var countdown: Int?
        if snapshot.isRunning, snapshot.countdownRemaining > 0 {
            countdown = Int(snapshot.countdownRemaining.rounded(.up))
        }
        return FloatingFrameState(
            progress: snapshot.progress,
            isMoving: snapshot.isMoving,
            countdown: countdown,
            isFinished: snapshot.progress >= 1,
            toast: toast,
            hint: hint
        )
    }

    private func enqueue(content: FloatingContent, state: FloatingFrameState, size: (width: Int, height: Int), time: CFTimeInterval, scheduled: Bool) {
        guard let buffer = renderer.render(content: content, state: state, pixelWidth: size.width, pixelHeight: size.height) else {
            return
        }

        // Timestamps must only grow.
        var pts = CMTime(seconds: time, preferredTimescale: 600)
        var displayImmediately = !scheduled
        if lastPTS.isValid, CMTimeCompare(pts, lastPTS) <= 0 {
            pts = CMTimeAdd(lastPTS, CMTime(value: 1, timescale: 600))
            displayImmediately = false
        }
        lastPTS = pts

        guard let sample = makeSampleBuffer(buffer, pts: pts, displayImmediately: displayImmediately) else { return }

        // iOS takes video resources away from background apps, which leaves the layer failed
        // (a black window). Flushing brings it back.
        var recovered = false
        if displayLayer.status == .failed || displayLayer.requiresFlushToResumeDecoding {
            displayLayer.flush()
            recovered = true
        }
        guard displayLayer.isReadyForMoreMediaData else { return }
        displayLayer.enqueue(sample)
        lastEnqueueTime = ScrollClock.now()

        lock.lock()
        framesEnqueued += 1
        if isInBackground { framesEnqueuedInBackground += 1 }
        if recovered { layerRecoveries += 1 }
        lock.unlock()
    }

    private func makeSampleBuffer(_ buffer: CVPixelBuffer, pts: CMTime, displayImmediately: Bool) -> CMSampleBuffer? {
        if let existing = formatDescription, CMVideoFormatDescriptionMatchesImageBuffer(existing, imageBuffer: buffer) {
            // Reuse the description: the layer treats a new one as a format change.
        } else {
            var description: CMVideoFormatDescription?
            CMVideoFormatDescriptionCreateForImageBuffer(allocator: kCFAllocatorDefault, imageBuffer: buffer, formatDescriptionOut: &description)
            formatDescription = description
        }
        guard let formatDescription else { return nil }

        var timing = CMSampleTimingInfo(
            duration: CMTime(value: 1, timescale: CMTimeScale(FloatingPrompter.frameRate)),
            presentationTimeStamp: pts,
            decodeTimeStamp: .invalid
        )
        var sample: CMSampleBuffer?
        CMSampleBufferCreateReadyWithImageBuffer(
            allocator: kCFAllocatorDefault,
            imageBuffer: buffer,
            formatDescription: formatDescription,
            sampleTiming: &timing,
            sampleBufferOut: &sample
        )
        guard let sample else { return nil }

        if displayImmediately,
           let attachments = CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: true),
           CFArrayGetCount(attachments) > 0 {
            let dictionary = unsafeBitCast(CFArrayGetValueAtIndex(attachments, 0), to: CFMutableDictionary.self)
            CFDictionarySetValue(
                dictionary,
                Unmanaged.passUnretained(kCMSampleAttachmentKey_DisplayImmediately).toOpaque(),
                Unmanaged.passUnretained(kCFBooleanTrue).toOpaque()
            )
        }
        return sample
    }
}

// MARK: - AVPictureInPictureControllerDelegate

extension FloatingPrompter: AVPictureInPictureControllerDelegate {

    func pictureInPictureControllerWillStartPictureInPicture(_ pictureInPictureController: AVPictureInPictureController) {
        DispatchQueue.main.async {
            KeepAlive.shared.start()
            if self.controllerStyle == .camera {
                self.canvasView.start()
            }
        }
    }

    func pictureInPictureControllerDidStartPictureInPicture(_ pictureInPictureController: AVPictureInPictureController) {
        DispatchQueue.main.async {
            self.isStarting = false
            self.pendingStart = false
            self.isActive = true
            self.activeSince = Date()
            self.lock.lock()
            self.framesEnqueued = 0
            self.framesEnqueuedInBackground = 0
            self.layerRecoveries = 0
            self.lock.unlock()
            KeepAlive.shared.start()
            if self.controllerStyle == .camera {
                self.canvasView.start()
            }
            self.startHousekeeping()
            self.phaseChanged(self.session.phase)
            if self.openCameraOnStart {
                self.openCameraOnStart = false
                self.openSystemCamera()
            }
            // The window may have opened by itself while the user was already leaving the app.
            self.autoStartIfNeeded()
        }
    }

    func pictureInPictureController(_ pictureInPictureController: AVPictureInPictureController, failedToStartPictureInPictureWithError error: Error) {
        let description = error.localizedDescription
        DispatchQueue.main.async {
            if !self.retriedWithExclusiveAudio, self.isStarting {
                // One more try with an audio session that does not mix with other apps.
                self.retriedWithExclusiveAudio = true
                KeepAlive.activateSession(mixWithOthers: false)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                    guard self.isStarting, !self.isActive else { return }
                    pictureInPictureController.startPictureInPicture()
                }
                return
            }
            self.isStarting = false
            self.pendingStart = false
            self.openCameraOnStart = false
            self.canvasView.stop()
            KeepAlive.shared.stop()
            self.message = "Окно не запустилось: \(description)"
        }
    }

    func pictureInPictureControllerDidStopPictureInPicture(_ pictureInPictureController: AVPictureInPictureController) {
        lock.lock()
        renderWidth = nil
        lock.unlock()
        DispatchQueue.main.async {
            self.saveDiagnostics()
            self.isStarting = false
            self.isActive = false
            self.activeSince = nil
            self.housekeeping?.invalidate()
            self.housekeeping = nil
            self.canvasView.stop()
            KeepAlive.shared.stop()
            self.session.pause()
            self.showHint(nil)
            // The kind of window may have been changed while this one was open.
            self.makeControllerIfNeeded()
        }
    }

    func pictureInPictureController(_ pictureInPictureController: AVPictureInPictureController, restoreUserInterfaceForPictureInPictureStopWithCompletionHandler completionHandler: @escaping (Bool) -> Void) {
        completionHandler(true)
    }
}

// MARK: - AVPictureInPictureSampleBufferPlaybackDelegate (player window only)

extension FloatingPrompter: AVPictureInPictureSampleBufferPlaybackDelegate {

    func pictureInPictureController(_ pictureInPictureController: AVPictureInPictureController, setPlaying playing: Bool) {
        DispatchQueue.main.async {
            if playing {
                self.session.play()
            } else {
                self.session.pause()
            }
        }
    }

    func pictureInPictureControllerTimeRangeForPlayback(_ pictureInPictureController: AVPictureInPictureController) -> CMTimeRange {
        // The system draws its timeline from the layer's clock. The range is placed so that the
        // current moment of that clock falls exactly where we are in the script.
        lock.lock()
        let total = max(1, totalDuration)
        lock.unlock()
        let progress = min(0.999, session.clock.progress(at: ScrollClock.now()))
        let layerTime = CMTimebaseGetTime(displayLayer.timebase)
        let nowSeconds = layerTime.isNumeric ? layerTime.seconds : ScrollClock.now()
        return CMTimeRange(
            start: CMTime(seconds: nowSeconds - progress * total, preferredTimescale: 600),
            duration: CMTime(seconds: total, preferredTimescale: 600)
        )
    }

    func pictureInPictureControllerIsPlaybackPaused(_ pictureInPictureController: AVPictureInPictureController) -> Bool {
        !session.clock.isRunning
    }

    func pictureInPictureController(_ pictureInPictureController: AVPictureInPictureController, didTransitionToRenderSize newRenderSize: CMVideoDimensions) {
        guard newRenderSize.width > 0 else { return }
        lock.lock()
        renderWidth = Int(newRenderSize.width)
        lock.unlock()
    }

    func pictureInPictureController(_ pictureInPictureController: AVPictureInPictureController, skipByInterval skipInterval: CMTime, completion completionHandler: @escaping () -> Void) {
        let forward = skipInterval.seconds > 0
        DispatchQueue.main.async {
            self.handleSkip(forward: forward)
            completionHandler()
        }
    }

    private func handleSkip(forward: Bool) {
        let running = session.clock.isRunning
        let useSpeed: Bool
        switch settings.skipMode {
        case .auto: useSpeed = running
        case .speed: useSpeed = true
        case .seek: useSpeed = false
        }
        if useSpeed {
            changeSpeed(by: forward ? AppSettings.Limits.floatingSpeedStep : -AppSettings.Limits.floatingSpeedStep)
        } else {
            jumpParagraph(forward: forward)
        }
    }
}
