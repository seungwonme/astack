#!/usr/bin/env swift

import AppKit
import ApplicationServices
import Foundation

struct Config {
    var bundleID = "com.apple.VoiceMemos"
    var buttonDescription = "전사문"
    var buttonIdentifier = "PlaybackView/TranscriptionButton"
    var timeout: TimeInterval = 10
    var pollInterval: TimeInterval = 0.25
}

let riskyRecordingLabels: Set<String> = ["완료", "일시 정지", "일시중지"]

func parseArgs() -> Config {
    var config = Config()
    let args = Array(CommandLine.arguments.dropFirst())
    var index = 0

    while index < args.count {
        switch args[index] {
        case "--bundle-id":
            index += 1
            if index < args.count { config.bundleID = args[index] }
        case "--description":
            index += 1
            if index < args.count { config.buttonDescription = args[index] }
        case "--identifier":
            index += 1
            if index < args.count { config.buttonIdentifier = args[index] }
        case "--timeout":
            index += 1
            if index < args.count, let value = Double(args[index]) { config.timeout = value }
        case "--poll-interval":
            index += 1
            if index < args.count, let value = Double(args[index]) { config.pollInterval = value }
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
    guard result == .success else { return nil }
    return value as AnyObject?
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

func findFirst(where predicate: (AXUIElement) -> Bool, in root: AXUIElement) -> AXUIElement? {
    if predicate(root) {
        return root
    }

    for child in axChildren(root) {
        if let match = findFirst(where: predicate, in: child) {
            return match
        }
    }

    return nil
}

func matchesAnyLabel(_ element: AXUIElement, labels: Set<String>) -> Bool {
    let candidates = [
        axString(element, kAXTitleAttribute as String),
        axString(element, kAXDescriptionAttribute as String),
        axString(element, kAXValueAttribute as String),
    ]

    return candidates.contains { labels.contains($0) }
}

func recordingUIReason(in root: AXUIElement) -> String? {
    if findFirst(where: {
        axString($0, kAXIdentifierAttribute as String) == "RecordingView/TranscriptionButton"
    }, in: root) != nil {
        return "recording transcription control is visible"
    }

    if findFirst(where: {
        axString($0, kAXRoleAttribute as String) == kAXButtonRole as String
            && matchesAnyLabel($0, labels: riskyRecordingLabels)
    }, in: root) != nil {
        return "recording controls are visible"
    }

    return nil
}

func matchesButton(_ element: AXUIElement, config: Config) -> Bool {
    let role = axString(element, kAXRoleAttribute as String)
    guard role == kAXButtonRole as String else { return false }

    let identifier = axString(element, kAXIdentifierAttribute as String)

    if !config.buttonIdentifier.isEmpty {
        return identifier == config.buttonIdentifier
    }

    let title = axString(element, kAXTitleAttribute as String)
    let description = axString(element, kAXDescriptionAttribute as String)
    let help = axString(element, kAXHelpAttribute as String)

    return title == config.buttonDescription
        || description == config.buttonDescription
        || help == config.buttonDescription
}

func findButton(in element: AXUIElement, config: Config) -> AXUIElement? {
    if matchesButton(element, config: config) {
        return element
    }

    for child in axChildren(element) {
        if let match = findButton(in: child, config: config) {
            return match
        }
    }

    return nil
}

func voiceMemosApp(bundleID: String) -> NSRunningApplication? {
    NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first
}

func activate(_ app: NSRunningApplication) {
    app.activate(options: [.activateIgnoringOtherApps])
}

func press(_ element: AXUIElement) -> Bool {
    AXUIElementPerformAction(element, kAXPressAction as CFString) == .success
}

let config = parseArgs()

guard let app = voiceMemosApp(bundleID: config.bundleID) else {
    fputs("Voice Memos is not running.\n", stderr)
    exit(1)
}

activate(app)

let deadline = Date().addingTimeInterval(config.timeout)
let appElement = AXUIElementCreateApplication(app.processIdentifier)

while Date() < deadline {
    if let windows = axValue(appElement, kAXWindowsAttribute as String) as? [AXUIElement] {
        for window in windows {
            if let reason = recordingUIReason(in: window) {
                fputs("Recording UI detected (\(reason)); refusing to automate.\n", stderr)
                exit(4)
            }

            if let button = findButton(in: window, config: config) {
                if press(button) {
                    print("clicked transcription button")
                    exit(0)
                }
                fputs("Found transcription button but failed to press it.\n", stderr)
                exit(2)
            }
        }
    }

    Thread.sleep(forTimeInterval: config.pollInterval)
}

fputs("Timed out waiting for the transcription button.\n", stderr)
exit(3)
