import AVFoundation
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let sourceURL = root.appendingPathComponent("submission/Signal_Desk_Demo_Clarity_Base.mp4")
let outputURL = root.appendingPathComponent("submission/Signal_Desk_Demo_Daniel_Clarity.mp4")
let narrationDirectory = root.appendingPathComponent("submission/narration-daniel")
let durationScale = 1.45

let baseStarts: [Double] = [
    0.45, 5.35, 10.35, 15.30, 21.30, 27.25, 37.20,
    48.25, 54.20, 60.20, 71.20, 77.20, 82.20, 87.20,
    93.20, 98.20, 103.20, 108.20, 113.20, 118.20, 126.15,
]
let starts = baseStarts.map { $0 * durationScale }

func awaitLoad<T>(_ operation: @escaping () async throws -> T) throws -> T {
    let semaphore = DispatchSemaphore(value: 0)
    var result: Result<T, Error>!
    Task {
        do { result = .success(try await operation()) }
        catch { result = .failure(error) }
        semaphore.signal()
    }
    semaphore.wait()
    return try result.get()
}

let source = AVURLAsset(url: sourceURL)
let sourceDuration = try awaitLoad { try await source.load(.duration) }
let videoTracks = try awaitLoad { try await source.loadTracks(withMediaType: .video) }
guard let sourceVideoTrack = videoTracks.first else { fatalError("Source video has no video track") }

let composition = AVMutableComposition()
guard let videoTrack = composition.addMutableTrack(
    withMediaType: .video,
    preferredTrackID: kCMPersistentTrackID_Invalid
) else { fatalError("Unable to create video track") }
try videoTrack.insertTimeRange(
    CMTimeRange(start: .zero, duration: sourceDuration),
    of: sourceVideoTrack,
    at: .zero
)
videoTrack.preferredTransform = try awaitLoad { try await sourceVideoTrack.load(.preferredTransform) }

guard let audioTrack = composition.addMutableTrack(
    withMediaType: .audio,
    preferredTrackID: kCMPersistentTrackID_Invalid
) else { fatalError("Unable to create narration track") }

for (offset, start) in starts.enumerated() {
    let number = String(format: "%02d", offset + 1)
    let clipURL = narrationDirectory.appendingPathComponent("\(number).aiff")
    let clip = AVURLAsset(url: clipURL)
    let clipDuration = try awaitLoad { try await clip.load(.duration) }
    let tracks = try awaitLoad { try await clip.loadTracks(withMediaType: .audio) }
    guard let clipTrack = tracks.first else { fatalError("Missing narration clip \(number)") }
    let insertionTime = CMTime(seconds: start, preferredTimescale: 600)
    let available = CMTimeSubtract(sourceDuration, insertionTime)
    let duration = CMTimeMinimum(clipDuration, available)
    try audioTrack.insertTimeRange(
        CMTimeRange(start: .zero, duration: duration),
        of: clipTrack,
        at: insertionTime
    )
}

try? FileManager.default.removeItem(at: outputURL)
guard let exporter = AVAssetExportSession(
    asset: composition,
    presetName: AVAssetExportPresetHighestQuality
) else { fatalError("Unable to create export session") }
exporter.outputURL = outputURL
exporter.outputFileType = .mp4
exporter.shouldOptimizeForNetworkUse = true

let exportSemaphore = DispatchSemaphore(value: 0)
Task {
    do { try await exporter.export(to: outputURL, as: .mp4) }
    catch { print("Export error: \(error)") }
    exportSemaphore.signal()
}
exportSemaphore.wait()

guard exporter.status == .completed else {
    fatalError(exporter.error?.localizedDescription ?? "Narrated export failed")
}
print(outputURL.path)
