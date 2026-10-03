import SwiftUI
import MessagingCore
import MessagingHTTP
import MessagingSQLite

@main
struct MessagingIOSApp: App {
    @StateObject private var vm: ViewModel = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dbURL = docs.appendingPathComponent("messages.db")
        let store = try! GRDBStore(path: dbURL.path)
        let transport = URLSessionTransport(baseURL: URL(string: "http://127.0.0.1:8000")!)
        let client = MessagingClient(store: store, transport: transport)
        return ViewModel(client: client)
    }()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(vm)
        }
    }
}
