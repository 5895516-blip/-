import UIKit

/// The text of the camera-friendly floating window.
///
/// This is an ordinary view that redraws itself, with no video pipeline behind it. That matters:
/// when the Camera starts recording, iOS takes the video resources away from background apps,
/// which turns a video-based window black. A plain view keeps drawing.
final class FloatingCanvasView: UIView {

    /// Supplies what to draw for a given moment. Called on the main thread.
    var frameProvider: ((CFTimeInterval) -> (content: FloatingContent, version: Int, state: FloatingFrameState)?)?

    /// Frames drawn since `start()` and how many of them while the app was in the background.
    private(set) var framesDrawn = 0
    private(set) var framesDrawnInBackground = 0

    private struct Signature: Equatable {
        var state: FloatingFrameState
        var version: Int
        var size: CGSize
    }

    private let renderer = FloatingFrameRenderer()
    private let linkProxy = CanvasLinkProxy()
    private var displayLink: CADisplayLink?
    private var fallbackTimer: Timer?
    private var lastLinkTick: CFTimeInterval = 0
    private var lastSignature: Signature?
    private var lastDrawTime: CFTimeInterval = 0
    private var drawTime: CFTimeInterval = 0

    override init(frame: CGRect) {
        super.init(frame: frame)
        commonInit()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        commonInit()
    }

    private func commonInit() {
        isOpaque = true
        contentMode = .redraw
        isUserInteractionEnabled = false
        backgroundColor = UIColor(cgColor: PrompterPalette.floatingBackground)
        linkProxy.view = self
    }

    deinit {
        displayLink?.invalidate()
        fallbackTimer?.invalidate()
    }

    // MARK: Ticking

    /// Starts redrawing. The display link gives perfectly even motion; the timer takes over
    /// whenever the system stops calling the link (which it may do for a background app).
    func start() {
        framesDrawn = 0
        framesDrawnInBackground = 0
        lastSignature = nil
        if displayLink == nil {
            let link = CADisplayLink(target: linkProxy, selector: #selector(CanvasLinkProxy.tick(_:)))
            link.preferredFrameRateRange = CAFrameRateRange(minimum: 30, maximum: 60, preferred: 60)
            link.add(to: .main, forMode: .common)
            displayLink = link
        }
        if fallbackTimer == nil {
            let timer = Timer(timeInterval: 1.0 / 60.0, repeats: true) { [weak self] _ in
                guard let self else { return }
                let now = ScrollClock.now()
                if now - self.lastLinkTick > 0.1 {
                    self.tick(at: now)
                }
            }
            RunLoop.main.add(timer, forMode: .common)
            fallbackTimer = timer
        }
        tick(at: ScrollClock.now())
    }

    func stop() {
        displayLink?.invalidate()
        displayLink = nil
        fallbackTimer?.invalidate()
        fallbackTimer = nil
    }

    fileprivate func linkFired(_ link: CADisplayLink) {
        lastLinkTick = ScrollClock.now()
        tick(at: link.targetTimestamp)
    }

    private func tick(at time: CFTimeInterval) {
        guard bounds.width > 1, bounds.height > 1, let frame = frameProvider?(time) else { return }
        let signature = Signature(state: frame.state, version: frame.version, size: bounds.size)
        // Redraw when something changed, plus twice a second to recover from any lost frame.
        guard signature != lastSignature || time - lastDrawTime > 0.5 else { return }
        lastSignature = signature
        lastDrawTime = time
        drawTime = time
        setNeedsDisplay()
    }

    // MARK: Drawing

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        guard let frame = frameProvider?(drawTime > 0 ? drawTime : ScrollClock.now()) else {
            context.setFillColor(PrompterPalette.floatingBackground)
            context.fill(bounds)
            return
        }
        renderer.draw(
            content: frame.content,
            state: frame.state,
            in: context,
            size: bounds.size,
            pixelsPerUnit: max(1, contentScaleFactor)
        )
        framesDrawn += 1
        if UIApplication.shared.applicationState != .active {
            framesDrawnInBackground += 1
        }
    }
}

/// Breaks the retain cycle between `CADisplayLink` and the view.
private final class CanvasLinkProxy: NSObject {
    weak var view: FloatingCanvasView?

    @objc func tick(_ link: CADisplayLink) {
        view?.linkFired(link)
    }
}
