import AVFoundation

/// Keeps the app running while its window floats over another app.
///
/// iOS suspends a background app within seconds unless it is playing audio, and a suspended app
/// cannot scroll its text. So while the floating window is open the app plays a silent loop.
/// The audio session mixes with others: music keeps playing and the Camera records normally.
final class KeepAlive: NSObject {

    static let shared = KeepAlive()

    /// How many times the system interrupted the session since `start()` (for diagnostics).
    private(set) var interruptions = 0
    /// How many times playback had to be restarted since `start()` (for diagnostics).
    private(set) var restarts = 0

    private var player: AVAudioPlayer?
    private var wanted = false

    var isPlaying: Bool { player?.isPlaying ?? false }

    private override init() {
        super.init()
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(handleInterruption(_:)), name: AVAudioSession.interruptionNotification, object: nil)
        center.addObserver(self, selector: #selector(handleMediaReset), name: AVAudioSession.mediaServicesWereResetNotification, object: nil)
    }

    /// Configures the shared audio session. Picture in Picture needs the playback category.
    /// - Parameter mixWithOthers: `false` is a fallback for systems that refuse to start the
    ///   window with a mixing session.
    static func activateSession(mixWithOthers: Bool = true) {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playback, mode: .moviePlayback, options: mixWithOthers ? [.mixWithOthers] : [])
            try session.setActive(true)
        } catch {
            try? session.setCategory(.playback)
            try? session.setActive(true)
        }
    }

    func start() {
        if !wanted {
            interruptions = 0
            restarts = 0
        }
        wanted = true
        if player == nil {
            let newPlayer = try? AVAudioPlayer(data: KeepAlive.silentWAV(seconds: 2))
            newPlayer?.numberOfLoops = -1
            newPlayer?.volume = 0.01
            newPlayer?.prepareToPlay()
            player = newPlayer
        }
        if player?.isPlaying != true {
            player?.play()
        }
    }

    func stop() {
        wanted = false
        player?.stop()
        player = nil
    }

    /// Resumes the silent loop if something stopped it. Called after interruptions and
    /// periodically while the window is open.
    func restartIfNeeded() {
        guard wanted, player?.isPlaying != true else { return }
        KeepAlive.activateSession()
        restarts += 1
        if player == nil {
            start()
        } else {
            player?.play()
        }
    }

    @objc private func handleInterruption(_ notification: Notification) {
        guard let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
        DispatchQueue.main.async {
            guard self.wanted else { return }
            if type == .began {
                self.interruptions += 1
            }
            // Another app (for example the Camera when a recording starts) took the audio.
            // Our loop mixes with anything, so simply start it again a moment later.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                self.restartIfNeeded()
            }
        }
    }

    @objc private func handleMediaReset() {
        DispatchQueue.main.async {
            self.player = nil
            if self.wanted {
                KeepAlive.activateSession()
                self.start()
            }
        }
    }

    /// A 16-bit mono PCM WAV file that contains only silence.
    static func silentWAV(seconds: Double, sampleRate: Int = 22_050) -> Data {
        let sampleCount = Int(Double(sampleRate) * seconds)
        let dataSize = sampleCount * 2
        var data = Data()

        func append32(_ value: UInt32) {
            withUnsafeBytes(of: value.littleEndian) { data.append(contentsOf: $0) }
        }
        func append16(_ value: UInt16) {
            withUnsafeBytes(of: value.littleEndian) { data.append(contentsOf: $0) }
        }

        data.append(contentsOf: Array("RIFF".utf8))
        append32(UInt32(36 + dataSize))
        data.append(contentsOf: Array("WAVE".utf8))
        data.append(contentsOf: Array("fmt ".utf8))
        append32(16)                        // size of the format chunk
        append16(1)                         // PCM
        append16(1)                         // mono
        append32(UInt32(sampleRate))
        append32(UInt32(sampleRate * 2))    // bytes per second
        append16(2)                         // bytes per sample frame
        append16(16)                        // bits per sample
        data.append(contentsOf: Array("data".utf8))
        append32(UInt32(dataSize))
        data.append(Data(count: dataSize))
        return data
    }
}
