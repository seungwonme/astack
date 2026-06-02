#!/usr/bin/env swift

import AppKit
import ApplicationServices
import Foundation

struct Config {
    var bundleID = "com.apple.VoiceMemos"
    var timeout: TimeInterval = 180
    var unavailableText = "오디오를 전사할 수 없음"
}

let riskyRecordingLabels: Set<String> = ["완료", "일시 정지", "일시중지"]

struct RowInfo {
    let description: String
    let duration: String
    let element: AXUIElement

    var isTranscribed: Bool {
        description.contains("전사문을 사용할 수 있음")
    }

    var normalizedDescription: String {
        description.replacingOccurrences(of: ", 전사문을 사용할 수 있음", with: "")
    }

    var key: String {
        normalizedDescription + "|" + duration
    }

    var title: String {
        normalizedDescription.split(separator: ",").first.map(String.init) ?? normalizedDescription
    }
}

enum TranscriptionResult: String {
    case transcribed
    case unavailable
    case timedOut = "timeout"
    case missingRow = "missing-row"
    case missingButton = "missing-button"
    case unsafeState = "unsafe-state"
}

func parseArgs() -> Config {
    var config = Config()
    let args = Array(CommandLine.arguments.dropFirst())
    var index = 0

    while index < args.count {
        switch args[index] {
        case "--bundle-id":
            index += 1
            if index < args.count { config.bundleID = args[index] }
        case "--timeout":
            index += 1
            if index < args.count, let value = Double(args[index]) { config.timeout = value }
        default:
            break
        }
        index += 1
    }

    return config
}

func axValue(_ element: AXUIElement, _ attribute: String) -> AnyObject? {
    var value: CFTypeRef?
    let result = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
    return result == .success ? (value as AnyObject?) : nil
}

func axString(_ element: AXUIElement, _ attribute: String) -> String {
    (axValue(element, attribute) as? String) ?? ""
}

func axChildren(_ element: AXUIElement) -> [AXUIElement] {
    for attribute in [kAXChildrenAttribute as String, kAXContentsAttribute as String] {
        if let children = axValue(element, attribute) as? [AXUIElement], !children.isEmpty {
            return children
        }
    }
    return []
}

func matchesAnyLabel(_ element: AXUIElement, labels: Set<String>) -> Bool {
    let candidates = [
        axString(element, kAXTitleAttribute as String),
        axString(element, kAXDescriptionAttribute as String),
        axString(element, kAXValueAttribute as String),
    ]

    return candidates.contains { labels.contains($0) }
}

func findFirst(where predicate: (AXUIElement) -> Bool, in root: AXUIElement) -> AXUIElement? {
    if predicate(root) { return root }

    for child in axChildren(root) {
        if let match = findFirst(where: predicate, in: child) {
            return match
        }
    }

    return nil
}

func collectButtons(in root: AXUIElement, into array: inout [AXUIElement]) {
    if axString(root, kAXRoleAttribute as String) == kAXButtonRole as String {
        array.append(root)
    }

    for child in axChildren(root) {
        collectButtons(in: child, into: &array)
    }
}

func appElement(bundleID: String) -> AXUIElement? {
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first else {
        return nil
    }
    return AXUIElementCreateApplication(app.processIdentifier)
}

func refreshWindow(_ appElement: AXUIElement) -> AXUIElement? {
    (axValue(appElement, kAXWindowsAttribute as String) as? [AXUIElement])?.first
}

func recordingsList(in window: AXUIElement) -> AXUIElement? {
    findFirst(where: { axString($0, kAXIdentifierAttribute as String) == "RecordingsList" }, in: window)
}

func visibleRows(in window: AXUIElement) -> [RowInfo] {
    guard let list = recordingsList(in: window) else { return [] }

    var buttons: [AXUIElement] = []
    collectButtons(in: list, into: &buttons)

    return buttons.compactMap { button in
        let description = axString(button, kAXDescriptionAttribute as String)
        guard description.contains(",") else { return nil }

        return RowInfo(
            description: description,
            duration: axString(button, kAXValueAttribute as String),
            element: button
        )
    }
}

func currentDetailTitle(in window: AXUIElement) -> String {
    if let field = findFirst(where: {
        axString($0, kAXRoleAttribute as String) == "AXTextField"
            && !axString($0, kAXValueAttribute as String).isEmpty
    }, in: window) {
        return axString(field, kAXValueAttribute as String)
    }

    return ""
}

func currentTranscriptValue(in window: AXUIElement) -> String {
    if let textElement = findFirst(where: {
        axString($0, kAXDescriptionAttribute as String) == "전사문 보기"
    }, in: window) {
        return axString(textElement, kAXValueAttribute as String)
    }

    return ""
}

func recordingUIReason(in window: AXUIElement) -> String? {
    if findFirst(where: {
        axString($0, kAXIdentifierAttribute as String) == "RecordingView/TranscriptionButton"
    }, in: window) != nil {
        return "recording transcription control is visible"
    }

    if findFirst(where: {
        axString($0, kAXRoleAttribute as String) == kAXButtonRole as String
            && matchesAnyLabel($0, labels: riskyRecordingLabels)
    }, in: window) != nil {
        return "recording controls are visible"
    }

    return nil
}

func isUnavailableState(in window: AXUIElement, text: String) -> Bool {
    findFirst(where: {
        axString($0, kAXValueAttribute as String) == text
            || axString($0, kAXDescriptionAttribute as String) == text
            || axString($0, kAXTitleAttribute as String) == text
    }, in: window) != nil
}

func transcriptionButton(in window: AXUIElement) -> AXUIElement? {
    findFirst(where: {
        axString($0, kAXIdentifierAttribute as String) == "PlaybackView/TranscriptionButton"
    }, in: window)
}

func selectRow(_ row: RowInfo) -> Bool {
    AXUIElementPerformAction(row.element, kAXPressAction as CFString) == .success
}

func transcribe(_ item: RowInfo, appElement: AXUIElement, config: Config) -> TranscriptionResult {
    guard
        let initialWindow = refreshWindow(appElement),
        let row = visibleRows(in: initialWindow).first(where: { $0.key == item.key })
    else {
        return .missingRow
    }

    guard selectRow(row) else {
        return .missingRow
    }
    Thread.sleep(forTimeInterval: 0.8)

    guard let selectedWindow = refreshWindow(appElement) else {
        return .missingRow
    }

    if recordingUIReason(in: selectedWindow) != nil {
        return .unsafeState
    }

    let detailTitle = currentDetailTitle(in: selectedWindow)
    let baselineTranscript = currentTranscriptValue(in: selectedWindow)

    if detailTitle == item.title && isUnavailableState(in: selectedWindow, text: config.unavailableText) {
        return .unavailable
    }

    guard let button = transcriptionButton(in: selectedWindow) else {
        return .missingButton
    }

    guard AXUIElementPerformAction(button, kAXPressAction as CFString) == .success else {
        return .missingButton
    }

    let deadline = Date().addingTimeInterval(config.timeout)
    while Date() < deadline {
        Thread.sleep(forTimeInterval: 1.0)

        guard let window = refreshWindow(appElement) else {
            continue
        }

        if recordingUIReason(in: window) != nil {
            return .unsafeState
        }

        if let currentRow = visibleRows(in: window).first(where: { $0.key == item.key }), currentRow.isTranscribed {
            return .transcribed
        }

        let latestTitle = currentDetailTitle(in: window)
        if latestTitle == item.title {
            if isUnavailableState(in: window, text: config.unavailableText) {
                return .unavailable
            }

            let transcript = currentTranscriptValue(in: window)
            if !transcript.isEmpty && transcript != baselineTranscript {
                return .transcribed
            }
        }
    }

    return .timedOut
}

let config = parseArgs()

guard let app = appElement(bundleID: config.bundleID), let window = refreshWindow(app) else {
    fputs("Voice Memos is not running or has no window.\n", stderr)
    exit(1)
}

if let reason = recordingUIReason(in: window) {
    fputs("Recording UI detected (\(reason)); refusing to automate.\n", stderr)
    exit(2)
}

let targets = visibleRows(in: window).filter { !$0.isTranscribed }
print("targets\t\(targets.count)")

var counts: [TranscriptionResult: Int] = [:]

for item in targets {
    print("start\t\(item.key)")
    let result = transcribe(item, appElement: app, config: config)
    counts[result, default: 0] += 1
    print("result\t\(item.key)\t\(result.rawValue)")
}

print(
    "summary\ttranscribed=\(counts[.transcribed, default: 0])"
        + "\tunavailable=\(counts[.unavailable, default: 0])"
        + "\ttimeout=\(counts[.timedOut, default: 0])"
        + "\tmissing-row=\(counts[.missingRow, default: 0])"
        + "\tmissing-button=\(counts[.missingButton, default: 0])"
        + "\tunsafe-state=\(counts[.unsafeState, default: 0])"
)
