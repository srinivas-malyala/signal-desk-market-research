import AVFoundation
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let directory = root.appendingPathComponent("submission/voice-samples")
let names = ["samantha", "alex", "daniel", "karen", "moira", "rishi"]

for name in names {
    let input = directory.appendingPathComponent("\(name).aiff")
    let output = directory.appendingPathComponent("\(name).m4a")
    try? FileManager.default.removeItem(at: output)

    let asset = AVURLAsset(url: input)
    guard let exporter = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A) else {
        fatalError("Unable to create audio exporter for \(name)")
    }
    exporter.outputURL = output
    exporter.outputFileType = .m4a
    exporter.shouldOptimizeForNetworkUse = true

    let semaphore = DispatchSemaphore(value: 0)
    Task {
        do { try await exporter.export(to: output, as: .m4a) }
        catch { print("Export failed for \(name): \(error)") }
        semaphore.signal()
    }
    semaphore.wait()

    guard FileManager.default.fileExists(atPath: output.path) else {
        fatalError("No converted file produced for \(name)")
    }
    print(output.path)
}
