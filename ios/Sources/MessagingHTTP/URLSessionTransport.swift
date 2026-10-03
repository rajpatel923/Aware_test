import Foundation
import MessagingCore

/// Wire DTOs — JSON-encodable shapes matching the OpenAPI contract.
private struct MetaDTO: Decodable { let protocol_version: String; let server_epoch: String }

private struct SubmitBodyDTO: Encodable {
    let client_message_id: String
    let sender: String
    let recipient: String
    let text: String
}

private struct MessageDTO: Decodable {
    let client_message_id: String
    let sender: String
    let recipient: String
    let text: String
    let sequence: Int
    let accepted_at: String
    let server_epoch: String
}

private struct InboxPageDTO: Decodable {
    let messages: [MessageDTO]
    let next_cursor: Int
    let has_more: Bool
    let server_epoch: String
}

private struct ErrorDTO: Decodable {
    let code: String
    let message: String
    let server_epoch: String?
}

public final class URLSessionTransport: MessagingTransport {
    private let baseURL: URL
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private let timeout: TimeInterval

    public init(baseURL: URL, timeout: TimeInterval = 10) {
        self.baseURL = baseURL
        self.timeout = timeout
        let config = URLSessionConfiguration.ephemeral
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        self.session = URLSession(configuration: config)
    }

    private func url(_ path: String) -> URL { baseURL.appendingPathComponent(path) }

    private func request(
        _ method: String, url: URL, body: Data? = nil, epoch: String? = nil
    ) -> URLRequest {
        var req = URLRequest(url: url, timeoutInterval: timeout)
        req.httpMethod = method
        req.cachePolicy = .reloadIgnoringLocalCacheData
        if let body { req.httpBody = body; req.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let epoch { req.setValue(epoch, forHTTPHeaderField: "X-Server-Epoch") }
        return req
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data, status: Int) throws -> T {
        if status == 409 || status == 422 {
            if let err = try? decoder.decode(ErrorDTO.self, from: data) {
                if err.code == "SERVER_EPOCH_CHANGED" {
                    throw MessagingError.epochChanged(newEpoch: err.server_epoch ?? "")
                }
                if err.code == "MESSAGE_ID_CONFLICT" {
                    throw MessagingError.conflict(err.code)
                }
                throw MessagingError.invalidRequest(err.message)
            }
        }
        guard (200..<300).contains(status) else {
            throw MessagingError.networkError("HTTP \(status)")
        }
        return try decoder.decode(type, from: data)
    }

    public func fetchMeta() async throws -> MetaResponse {
        let req = request("GET", url: url("/v1/meta"))
        let (data, resp) = try await session.data(for: req)
        let dto = try decode(MetaDTO.self, from: data, status: (resp as! HTTPURLResponse).statusCode)
        return MetaResponse(serverEpoch: dto.server_epoch)
    }

    public func submit(_ request: SubmitRequest) async throws -> MessageResponse {
        let body = try encoder.encode(SubmitBodyDTO(
            client_message_id: request.clientMessageID,
            sender: request.sender,
            recipient: request.recipient,
            text: request.text
        ))
        var req = self.request("POST", url: url("/v1/messages"), body: body, epoch: request.expectedEpoch)
        let (data, resp) = try await session.data(for: req)
        let dto = try decode(MessageDTO.self, from: data, status: (resp as! HTTPURLResponse).statusCode)
        return MessageResponse(
            clientMessageID: dto.client_message_id,
            sequence: dto.sequence,
            acceptedAt: dto.accepted_at,
            serverEpoch: dto.server_epoch
        )
    }

    public func fetchInbox(username: String, after: Int, limit: Int, epoch: String) async throws -> InboxResponse {
        let encoded = username.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? username
        var comps = URLComponents(url: url("/v1/inbox/\(encoded)"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "after", value: "\(after)"),
            URLQueryItem(name: "limit", value: "\(limit)"),
        ]
        var req = self.request("GET", url: comps.url!, epoch: epoch)
        let (data, resp) = try await session.data(for: req)
        let dto = try decode(InboxPageDTO.self, from: data, status: (resp as! HTTPURLResponse).statusCode)
        let msgs = dto.messages.map { m in
            IncomingMessage(
                clientMessageID: m.client_message_id,
                sender: m.sender,
                recipient: m.recipient,
                text: m.text,
                sequence: m.sequence
            )
        }
        return InboxResponse(messages: msgs, nextCursor: dto.next_cursor, hasMore: dto.has_more)
    }
}
