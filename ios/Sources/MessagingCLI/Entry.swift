import Foundation
import MessagingCore
import MessagingHTTP
import MessagingSQLite

// MARK: - JSON protocol types

private struct CLIRequest: Decodable {
    let id: String
    let cmd: String
    let args: ArgsPayload?
}

private struct ArgsPayload: Decodable {
    let name: String?
    let recipient: String?
    let text: String?
    let enabled: Bool?
    let drop_next_response: String?
    let peer: String?
}

// Per-command result types

private struct IdentifyResult: Encodable { let username: String }
private struct SendResult: Encodable { let client_message_id: String; let status: String }
private struct OfflineResult: Encodable { let offline: Bool }
private struct FaultResult: Encodable { let armed: Bool }
private struct SyncOnceResult: Encodable { let outcome: String; let accepted: Int; let received: Int; let pending: Int }
private struct SnapshotMessageResult: Encodable {
    let client_message_id: String; let sender: String; let recipient: String; let text: String
    let status: String; let sequence: Int?; let error_code: String?
}
private struct SnapshotResult: Encodable {
    let username: String?; let server_epoch: String?; let cursor: Int
    let sync_state: String; let pending_count: Int; let messages: [SnapshotMessageResult]
}
private struct ResetSessionResult: Encodable { let server_epoch: String; let cursor: Int }
private struct ShutdownResult: Encodable {}

// MARK: - I/O helpers

private let stdoutHandle = FileHandle.standardOutput

private func writeLine(_ s: String) {
    guard let data = (s + "\n").data(using: .utf8) else { return }
    stdoutHandle.write(data)
}

private func emit(id: String, result: some Encodable) {
    do {
        let resultData = try JSONEncoder().encode(result)
        let resultObj = try JSONSerialization.jsonObject(with: resultData)
        let envelope: [String: Any] = ["id": id, "ok": true, "result": resultObj]
        let data = try JSONSerialization.data(withJSONObject: envelope)
        writeLine(String(data: data, encoding: .utf8)!)
    } catch {
        emitError(id: id, code: "ENCODE_ERROR", message: "\(error)")
    }
}

private func emitError(id: String, code: String, message: String) {
    let envelope: [String: Any] = ["id": id, "ok": false, "error": ["code": code, "message": message]]
    if let data = try? JSONSerialization.data(withJSONObject: envelope),
       let line = String(data: data, encoding: .utf8) {
        writeLine(line)
    }
}

// MARK: - Command dispatch

private func dispatch(id: String, cmd: String, args: ArgsPayload?, client: MessagingClient) async {
    do {
        switch cmd {
        case "identify":
            guard let name = args?.name else { throw MessagingError.invalidRequest("Missing arg: name") }
            let username = try await client.identify(name: name)
            emit(id: id, result: IdentifyResult(username: username))

        case "send":
            guard let recipient = args?.recipient else { throw MessagingError.invalidRequest("Missing arg: recipient") }
            guard let text = args?.text else { throw MessagingError.invalidRequest("Missing arg: text") }
            let mid = try await client.enqueue(recipient: recipient, text: text)
            emit(id: id, result: SendResult(client_message_id: mid, status: "queued"))

        case "offline":
            guard let enabled = args?.enabled else { throw MessagingError.invalidRequest("Missing arg: enabled") }
            await client.setOffline(enabled)
            emit(id: id, result: OfflineResult(offline: enabled))

        case "fault":
            guard let drop = args?.drop_next_response else { throw MessagingError.invalidRequest("Missing arg: drop_next_response") }
            await client.fault(drop: drop)
            emit(id: id, result: FaultResult(armed: true))

        case "sync_once":
            let (outcome, accepted, received, pending) = try await client.syncOnce()
            emit(id: id, result: SyncOnceResult(outcome: outcome, accepted: accepted, received: received, pending: pending))

        case "snapshot":
            let snap = try await client.snapshot(peer: args?.peer)
            let msgs = snap.messages.map { m in
                SnapshotMessageResult(
                    client_message_id: m.clientMessageID,
                    sender: m.sender,
                    recipient: m.recipient,
                    text: m.text,
                    status: m.status,
                    sequence: m.sequence,
                    error_code: m.errorCode
                )
            }
            emit(id: id, result: SnapshotResult(
                username: snap.username,
                server_epoch: snap.serverEpoch,
                cursor: snap.cursor,
                sync_state: snap.syncState,
                pending_count: snap.pendingCount,
                messages: msgs
            ))

        case "reset_session":
            let (epoch, cursor) = try await client.resetSession()
            emit(id: id, result: ResetSessionResult(server_epoch: epoch, cursor: cursor))

        case "shutdown":
            emit(id: id, result: ShutdownResult())
            exit(0)

        default:
            emitError(id: id, code: "UNKNOWN_COMMAND", message: "Unknown command: \(cmd)")
        }
    } catch let e as MessagingError {
        emitError(id: id, code: "CLIENT_ERROR", message: "\(e)")
    } catch {
        emitError(id: id, code: "CLIENT_ERROR", message: "\(error)")
    }
}

// MARK: - Entry point

@main
struct CLI {
    static func main() async throws {
        let args = CommandLine.arguments

        var urlString: String?
        var dataDir: String?
        var pageSize: Int = 100

        var i = 1
        while i < args.count {
            switch args[i] {
            case "--url":      i += 1; urlString = args[i]
            case "--data-dir": i += 1; dataDir = args[i]
            case "--page-size": i += 1; pageSize = Int(args[i]) ?? 100
            default: break
            }
            i += 1
        }

        guard let rawURL = urlString, let url = URL(string: rawURL) else {
            fputs("usage: messaging-cli --url <url> --data-dir <dir> [--page-size N]\n", stderr)
            exit(1)
        }
        guard let dir = dataDir else {
            fputs("usage: messaging-cli --url <url> --data-dir <dir> [--page-size N]\n", stderr)
            exit(1)
        }

        let dirURL = URL(fileURLWithPath: dir)
        try FileManager.default.createDirectory(at: dirURL, withIntermediateDirectories: true)
        let dbPath = dirURL.appendingPathComponent("messages.db").path

        let store = try GRDBStore(path: dbPath)
        let transport = URLSessionTransport(baseURL: url)
        let client = MessagingClient(store: store, transport: transport, pageSize: pageSize)
        try await client.load()

        let decoder = JSONDecoder()

        // Read stdin on a background thread, feed lines to an AsyncStream
        let lines = AsyncStream<String> { continuation in
            Thread.detachNewThread {
                while let line = readLine(strippingNewline: true) {
                    if !line.isEmpty { continuation.yield(line) }
                }
                continuation.finish()
            }
        }

        for await line in lines {
            guard let data = line.data(using: .utf8),
                  let req = try? decoder.decode(CLIRequest.self, from: data) else {
                emitError(id: "?", code: "PARSE_ERROR", message: "Could not parse: \(line)")
                continue
            }
            await dispatch(id: req.id, cmd: req.cmd, args: req.args, client: client)
        }
    }
}
