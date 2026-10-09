import AppKit
import AVFoundation
import CoreVideo
import Foundation

struct Slide {
    let imagePath: String?
    let eyebrow: String
    let title: String
    let caption: String
    let duration: Double
    let crop: CGRect
    let redactions: [CGRect]

    init(
        imagePath: String?,
        eyebrow: String,
        title: String,
        caption: String,
        duration: Double,
        crop: CGRect = CGRect(x: 0, y: 0, width: 1, height: 1),
        redactions: [CGRect] = []
    ) {
        self.imagePath = imagePath
        self.eyebrow = eyebrow
        self.title = title
        self.caption = caption
        self.duration = duration
        self.crop = crop
        self.redactions = redactions
    }
}

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let clarityMode = CommandLine.arguments.contains("--clarity")
let outputName = clarityMode ? "Signal_Desk_Demo_Clarity_Base.mp4" : "Signal_Desk_Demo_Enhanced.mp4"
let output = root.appendingPathComponent("submission/\(outputName)")
let width = 1920
let height = 1080
let fps: Int32 = 30
let transitionDuration = 0.65
let durationScale = clarityMode ? 1.45 : 1.0

let slides = [
    Slide(
        imagePath: nil,
        eyebrow: "MASSIVE × DATABRICKS × LAKEBASE × RENDER",
        title: "Signal Desk",
        caption: "From live market research to governed evidence, confirmed actions, and measurable operations.",
        duration: 5
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.06.40 PM.png",
        eyebrow: "LIVE DEPLOYMENT",
        title: "Two production services, one research experience",
        caption: "Render hosts the web application and FastMCP service as independently deployable, healthy services.",
        duration: 5,
        crop: CGRect(x: 0.13, y: 0.13, width: 0.74, height: 0.76)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.07.31 PM.png",
        eyebrow: "RESEARCH WORKSPACE",
        title: "A focused interface for market questions",
        caption: "Performance, peer comparison, evidence search, watchlists, saved research, and analytics live in one workflow.",
        duration: 5,
        crop: CGRect(x: 0.15, y: 0.21, width: 0.70, height: 0.72)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.07.47 PM.png",
        eyebrow: "BOUNDED MARKET DATA",
        title: "AAPL performance with an explicit as-of date",
        caption: "The result separates facts from interpretation and states source coverage and limitations alongside the metrics.",
        duration: 6,
        crop: CGRect(x: 0.15, y: 0.26, width: 0.70, height: 0.70)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.08.08 PM.png",
        eyebrow: "COMPARISON",
        title: "Comparable windows make peer analysis honest",
        caption: "AAPL and MSFT are evaluated over the same 90-day period, with returns, ranges, volatility, and limitations visible.",
        duration: 6,
        crop: CGRect(x: 0.15, y: 0.28, width: 0.70, height: 0.68)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.10.43 PM.png",
        eyebrow: "EVIDENCE RETRIEVAL",
        title: "Search the thesis, not just the ticker",
        caption: "The user can constrain a natural-language question by company and source type before retrieval.",
        duration: 4,
        crop: CGRect(x: 0.15, y: 0.30, width: 0.70, height: 0.62)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.11.22 PM.png",
        eyebrow: "ATTRIBUTABLE RESULTS",
        title: "Every claim stays connected to its source",
        caption: "Ranked news evidence includes ticker, timestamp, relevance score, excerpt, and a direct source link.",
        duration: 6
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.12.27 PM.png",
        eyebrow: "USER-OWNED STATE",
        title: "A watchlist change begins as an intent",
        caption: "The user enters GOOGL, but the system does not silently mutate persistent state.",
        duration: 3
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.12.42 PM.png",
        eyebrow: "CONFIRMATION GATE",
        title: "Write actions require explicit approval",
        caption: "The proposed change is shown clearly before anything is persisted.",
        duration: 4
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.13.01 PM.png",
        eyebrow: "VERIFIABLE RESULT",
        title: "The watchlist reflects the confirmed update",
        caption: "The new company appears with the latest synchronized price, daily change, and source timestamp.",
        duration: 4
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.14.36 PM.png",
        eyebrow: "OBSERVABILITY",
        title: "Usage, reliability, and latency are measurable",
        caption: "Privacy-safe Gold tables expose active researchers, error rate, watchlist changes, saves, and per-tool latency.",
        duration: 6
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.15.53 PM.png",
        eyebrow: "SUPERVISOR AGENT",
        title: "The same tools compose into a grounded answer",
        caption: "Agent Bricks calls governed tools and returns an AAPL summary with metrics, as-of date, source, and limitations.",
        duration: 6,
        crop: CGRect(x: 0.34, y: 0.09, width: 0.64, height: 0.82)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.16.16 PM.png",
        eyebrow: "TOOL TRANSPARENCY",
        title: "Retrieval parameters remain inspectable",
        caption: "The trace shows the semantic query, ticker filter, source constraint, and grounded output used by the Supervisor.",
        duration: 5,
        crop: CGRect(x: 0.34, y: 0.09, width: 0.64, height: 0.82)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.16.30 PM.png",
        eyebrow: "EVIDENCE-GROUNDED SYNTHESIS",
        title: "Filing evidence supports—and challenges—the thesis",
        caption: "The answer cites reported growth while surfacing App Store, regulatory, and compliance risks as counter-evidence.",
        duration: 6,
        crop: CGRect(x: 0.34, y: 0.09, width: 0.64, height: 0.82)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.16.59 PM.png",
        eyebrow: "SAFE ACTION",
        title: "The Supervisor confirms, writes, then verifies",
        caption: "After user approval, the agent updates the Primary watchlist and reads it back to confirm the durable result.",
        duration: 6,
        crop: CGRect(x: 0.34, y: 0.09, width: 0.64, height: 0.82)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.18.34 PM.png",
        eyebrow: "RESEARCH MEMORY",
        title: "Drafting is separate from saving",
        caption: "A TSLA margin-pressure note is only persisted after a second explicit confirmation, then returned with its record ID.",
        duration: 5,
        crop: CGRect(x: 0.34, y: 0.09, width: 0.64, height: 0.82)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.20.53 PM.png",
        eyebrow: "MULTI-COMPANY REPORTS",
        title: "Comprehensive analysis becomes reusable memory",
        caption: "The confirmed MSFT–AMZN report is saved once with an idempotency key and durable research metadata.",
        duration: 5,
        crop: CGRect(x: 0.34, y: 0.08, width: 0.64, height: 0.84)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.22.15 PM.png",
        eyebrow: "GOVERNED MCP",
        title: "Nine tools publish through Unity Catalog",
        caption: "Discovery, read, write, and retrieval operations share one governed service with usage tracking, limits, and policies.",
        duration: 6,
        crop: CGRect(x: 0.11, y: 0.04, width: 0.71, height: 0.58)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.22.28 PM.png",
        eyebrow: "SERVICE HEALTH",
        title: "The MCP plane is observable in production",
        caption: "Native metrics show 64 calls, zero errors, request volume, and end-to-end latency across all tools.",
        duration: 5,
        crop: CGRect(x: 0.11, y: 0.10, width: 0.87, height: 0.69)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.23.16 PM.png",
        eyebrow: "POLICY ENFORCEMENT",
        title: "Guardrails wrap both request and response",
        caption: "Sensitive-data detection runs before the tool call and again before the model response leaves the service.",
        duration: 5,
        crop: CGRect(x: 0.25, y: 0.16, width: 0.50, height: 0.66)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.26.18 PM.png",
        eyebrow: "LAKEFLOW OPERATIONS",
        title: "Scheduled refreshes and ingestion runs stay visible",
        caption: "Market, filing, research-search, and analytics workloads are independently deployable and operationally auditable.",
        duration: 5,
        crop: CGRect(x: 0.10, y: 0.18, width: 0.88, height: 0.66),
        redactions: [CGRect(x: 0.50, y: 0.37, width: 0.085, height: 0.48)]
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.27.04 PM.png",
        eyebrow: "AI SEARCH",
        title: "The research index is online and synchronized",
        caption: "A Delta Sync index serves 528 filing and article chunks through a governed retrieval endpoint.",
        duration: 5,
        crop: CGRect(x: 0.11, y: 0.07, width: 0.71, height: 0.34)
    ),
    Slide(
        imagePath: "submission/demo-assets/Screenshot 2026-10-08 at 4.37.09 PM.png",
        eyebrow: "LAKEBASE → LAKEHOUSE",
        title: "Operational changes flow into governed analytics",
        caption: "Lakebase Change Data Feed is enabled from Postgres state into Unity Catalog for downstream transformation.",
        duration: 5,
        crop: CGRect(x: 0.10, y: 0.05, width: 0.84, height: 0.74)
    ),
    Slide(
        imagePath: "proposal/signal-desk-capstone-architecture.png",
        eyebrow: "END-TO-END ARCHITECTURE",
        title: "One governed research data plane",
        caption: "Lakeflow, Lakebase, AI Search, Unity Catalog MCP, Agent Bricks, and Render connect facts, actions, memory, and analytics.",
        duration: 8
    ),
    Slide(
        imagePath: nil,
        eyebrow: "SIGNAL DESK",
        title: "Research the claim. Inspect the evidence.",
        caption: "Confirmed actions. Attributable sources. Governed operations. Research support only—not personalized investment advice.",
        duration: 5
    ),
]

func color(_ hex: UInt32) -> NSColor {
    NSColor(
        calibratedRed: CGFloat((hex >> 16) & 0xff) / 255,
        green: CGFloat((hex >> 8) & 0xff) / 255,
        blue: CGFloat(hex & 0xff) / 255,
        alpha: 1
    )
}

let background = color(0xF5F2E9)
let ink = color(0x102B31)
let green = color(0x008B6A)
let muted = color(0x5E7178)

func drawText(_ text: String, rect: NSRect, size: CGFloat, weight: NSFont.Weight, color: NSColor) {
    let paragraph = NSMutableParagraphStyle()
    paragraph.lineBreakMode = .byWordWrapping
    paragraph.alignment = .left
    let attributes: [NSAttributedString.Key: Any] = [
        .font: NSFont.systemFont(ofSize: size, weight: weight),
        .foregroundColor: color,
        .paragraphStyle: paragraph,
    ]
    text.draw(in: rect, withAttributes: attributes)
}

func sourceImage(_ slide: Slide) -> NSImage? {
    guard let path = slide.imagePath else { return nil }
    return NSImage(contentsOf: root.appendingPathComponent(path))
}

func sourceRect(for slide: Slide, imageSize: NSSize) -> NSRect {
    let crop = slide.crop
    return NSRect(
        x: crop.minX * imageSize.width,
        y: (1 - crop.minY - crop.height) * imageSize.height,
        width: crop.width * imageSize.width,
        height: crop.height * imageSize.height
    )
}

func redactionRect(_ redaction: CGRect, crop: CGRect, drawn: NSRect) -> NSRect? {
    let intersection = redaction.intersection(crop)
    guard !intersection.isNull, intersection.width > 0, intersection.height > 0 else { return nil }
    return NSRect(
        x: drawn.minX + ((intersection.minX - crop.minX) / crop.width) * drawn.width,
        y: drawn.maxY - ((intersection.maxY - crop.minY) / crop.height) * drawn.height,
        width: (intersection.width / crop.width) * drawn.width,
        height: (intersection.height / crop.height) * drawn.height
    )
}

func render(_ slide: Slide) -> CGImage {
    let canvas = NSImage(size: NSSize(width: width, height: height))
    canvas.lockFocus()
    background.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()

    if let image = sourceImage(slide) {
        let stage = NSRect(x: 56, y: 215, width: 1808, height: 805)
        let source = sourceRect(for: slide, imageSize: image.size)
        let scale = min(stage.width / source.width, stage.height / source.height)
        let drawn = NSRect(
            x: stage.midX - source.width * scale / 2,
            y: stage.midY - source.height * scale / 2,
            width: source.width * scale,
            height: source.height * scale
        )
        let shadow = NSShadow()
        shadow.shadowColor = NSColor.black.withAlphaComponent(0.18)
        shadow.shadowBlurRadius = 24
        shadow.shadowOffset = NSSize(width: 0, height: -8)
        NSGraphicsContext.current?.saveGraphicsState()
        shadow.set()
        NSColor.white.setFill()
        NSBezierPath(roundedRect: drawn, xRadius: 16, yRadius: 16).fill()
        NSGraphicsContext.current?.restoreGraphicsState()
        NSGraphicsContext.current?.saveGraphicsState()
        NSBezierPath(roundedRect: drawn, xRadius: 16, yRadius: 16).addClip()
        image.draw(in: drawn, from: source, operation: .sourceOver, fraction: 1)
        for redaction in slide.redactions {
            guard let mask = redactionRect(redaction, crop: slide.crop, drawn: drawn) else { continue }
            NSColor(calibratedWhite: 0.08, alpha: 0.96).setFill()
            NSBezierPath(roundedRect: mask.insetBy(dx: -4, dy: -3), xRadius: 8, yRadius: 8).fill()
        }
        NSGraphicsContext.current?.restoreGraphicsState()

        drawText(slide.eyebrow, rect: NSRect(x: 74, y: 164, width: 1700, height: 34), size: 23, weight: .bold, color: green)
        drawText(slide.title, rect: NSRect(x: 74, y: 94, width: 1700, height: 64), size: 48, weight: .bold, color: ink)
        drawText(slide.caption, rect: NSRect(x: 76, y: 26, width: 1720, height: 62), size: 28, weight: .regular, color: muted)
    } else {
        NSColor(calibratedWhite: 1, alpha: 0.55).setFill()
        NSBezierPath(roundedRect: NSRect(x: 120, y: 165, width: 1680, height: 750), xRadius: 36, yRadius: 36).fill()
        drawText(slide.eyebrow, rect: NSRect(x: 190, y: 735, width: 1500, height: 48), size: 26, weight: .bold, color: green)
        drawText(slide.title, rect: NSRect(x: 180, y: 500, width: 1560, height: 220), size: 104, weight: .bold, color: ink)
        drawText(slide.caption, rect: NSRect(x: 190, y: 335, width: 1500, height: 150), size: 42, weight: .regular, color: muted)
        green.setFill()
        NSRect(x: 190, y: 295, width: 260, height: 8).fill()
    }

    canvas.unlockFocus()
    var proposed = NSRect(x: 0, y: 0, width: width, height: height)
    guard let cg = canvas.cgImage(forProposedRect: &proposed, context: nil, hints: nil) else {
        fatalError("Unable to render slide")
    }
    return cg
}

func makePixelBuffer(pool: CVPixelBufferPool, first: CGImage, second: CGImage?, mix: CGFloat) -> CVPixelBuffer {
    var optional: CVPixelBuffer?
    let status = CVPixelBufferPoolCreatePixelBuffer(nil, pool, &optional)
    guard status == kCVReturnSuccess, let buffer = optional else {
        fatalError("Unable to allocate pixel buffer: \(status)")
    }
    CVPixelBufferLockBaseAddress(buffer, [])
    defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
    guard let base = CVPixelBufferGetBaseAddress(buffer) else { fatalError("Missing pixel buffer base") }
    let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let info = CGBitmapInfo.byteOrder32Little.rawValue | CGImageAlphaInfo.premultipliedFirst.rawValue
    guard let context = CGContext(
        data: base,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: rowBytes,
        space: colorSpace,
        bitmapInfo: info
    ) else { fatalError("Unable to create frame context") }
    context.setFillColor(background.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.setAlpha(1)
    context.draw(first, in: CGRect(x: 0, y: 0, width: width, height: height))
    if let second, mix > 0 {
        context.setAlpha(mix)
        context.draw(second, in: CGRect(x: 0, y: 0, width: width, height: height))
    }
    return buffer
}

try? FileManager.default.removeItem(at: output)
let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
let settings: [String: Any] = [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: width,
    AVVideoHeightKey: height,
]
let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String: width,
        kCVPixelBufferHeightKey as String: height,
    ]
)
guard writer.canAdd(input) else { fatalError("Cannot add video input") }
writer.add(input)
guard writer.startWriting() else { fatalError(writer.error?.localizedDescription ?? "Unable to start writer") }
writer.startSession(atSourceTime: .zero)
guard let pool = adaptor.pixelBufferPool else { fatalError("Missing pixel buffer pool") }

let rendered = slides.map(render)
var frameNumber: Int64 = 0
for (index, slide) in slides.enumerated() {
    let frames = Int(slide.duration * durationScale * Double(fps))
    let transitionFrames = index < slides.count - 1 ? Int(transitionDuration * Double(fps)) : 0
    for localFrame in 0..<frames {
        while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.002) }
        let inTransition = transitionFrames > 0 && localFrame >= frames - transitionFrames
        let mix: CGFloat
        let next: CGImage?
        if inTransition {
            mix = CGFloat(localFrame - (frames - transitionFrames) + 1) / CGFloat(transitionFrames)
            next = rendered[index + 1]
        } else {
            mix = 0
            next = nil
        }
        let buffer = makePixelBuffer(pool: pool, first: rendered[index], second: next, mix: mix)
        let time = CMTime(value: frameNumber, timescale: fps)
        guard adaptor.append(buffer, withPresentationTime: time) else {
            fatalError(writer.error?.localizedDescription ?? "Unable to append frame")
        }
        frameNumber += 1
    }
}

input.markAsFinished()
let semaphore = DispatchSemaphore(value: 0)
writer.finishWriting { semaphore.signal() }
semaphore.wait()
guard writer.status == .completed else {
    fatalError(writer.error?.localizedDescription ?? "Video export failed")
}
print(output.path)
