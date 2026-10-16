import AppKit
import SwiftUI
import Translation

struct Request: Decodable {
    let text: String
    let source: String
    let target: String
}

@MainActor
func finish(_ result: [String: Any], code: Int32 = 0) -> Never {
    if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
    exit(code)
}

@MainActor
func translate(_ session: TranslationSession, request: Request) async {
    do {
        let response = try await session.translate(request.text)
        finish(["ok": true, "result": response.targetText])
    } catch {
        finish(["ok": false, "error": "系统翻译未完成。请确认语言资源已下载，或切换轻量云端。", "detail": error.localizedDescription], code: 1)
    }
}

struct TranslationHost: View {
    let request: Request
    let needsDownload: Bool
    @State private var configuration: TranslationSession.Configuration?

    var body: some View {
        VStack(spacing: 10) {
            Text("Prism · 系统翻译").font(.headline)
            Text("首次使用需下载语言资源，请确认系统提示。")
                .font(.subheadline).foregroundStyle(.secondary)
            ProgressView().controlSize(.small)
        }
        .padding(24)
        .frame(width: 340, height: 130)
        .opacity(needsDownload ? 1 : 0)
        .task {
            configuration = TranslationSession.Configuration(
                source: Locale.Language(identifier: request.source),
                target: Locale.Language(identifier: request.target))
        }
        .translationTask(configuration) { session in
            await translate(session, request: request)
        }
    }
}

@main
@MainActor
struct TranslationService {
    static var panel: NSWindow?

    static func main() {
        guard let request = try? JSONDecoder().decode(Request.self, from: FileHandle.standardInput.readDataToEndOfFile()),
              !request.text.isEmpty, request.text.count <= 12000 else {
            finish(["ok": false, "error": "翻译输入无效"], code: 1)
        }
        let application = NSApplication.shared
        application.setActivationPolicy(.accessory)
        Task { @MainActor in
            let source = Locale.Language(identifier: request.source)
            let target = Locale.Language(identifier: request.target)
            let availability = await LanguageAvailability().status(from: source, to: target)
            if CommandLine.arguments.contains("--check") {
                let status = availability == .installed ? "installed" : (availability == .supported ? "supported" : "unsupported")
                finish(["ok": true, "status": status])
            }
            guard availability != .unsupported else {
                finish(["ok": false, "error": "苹果系统暂不支持此语言组合，请切换轻量云端或 AI 模型。"], code: 1)
            }
            if #available(macOS 26.0, *), availability == .installed,
               !CommandLine.arguments.contains("--swiftui-session") {
                let session: TranslationSession
                if #available(macOS 26.4, *) {
                    session = TranslationSession(installedSource: source, target: target, preferredStrategy: .lowLatency)
                } else {
                    session = TranslationSession(installedSource: source, target: target)
                }
                await translate(session, request: request)
            } else {
                // macOS 15 sessions are supplied by SwiftUI. Keep a live view in a
                // non-activating transparent window; show it only for resource consent.
                let needsDownload = availability != .installed
                let window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 340, height: 130),
                                     styleMask: needsDownload ? [.titled, .nonactivatingPanel] : [.borderless, .nonactivatingPanel],
                                     backing: .buffered, defer: false)
                window.title = "Prism · 系统翻译"
                window.isReleasedWhenClosed = false
                window.level = .floating
                window.isOpaque = false
                window.backgroundColor = needsDownload ? .windowBackgroundColor : .clear
                window.hasShadow = needsDownload
                window.ignoresMouseEvents = !needsDownload
                window.contentView = NSHostingView(rootView: TranslationHost(request: request, needsDownload: needsDownload))
                window.center()
                panel = window
                window.orderFrontRegardless()
            }
        }
        application.run()
    }
}
