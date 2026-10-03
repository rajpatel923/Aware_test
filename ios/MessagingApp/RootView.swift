import SwiftUI
import MessagingCore

struct RootView: View {
    @EnvironmentObject var vm: ViewModel

    var body: some View {
        Group {
            if vm.username == nil {
                IdentifyView()
            } else {
                ConversationView()
            }
        }
        .alert("Error", isPresented: Binding(
            get: { vm.error != nil },
            set: { if !$0 { vm.clearError() } }
        )) {
            Button("OK") { vm.clearError() }
        } message: {
            Text(vm.error ?? "")
        }
    }
}

// MARK: - Identify

struct IdentifyView: View {
    @EnvironmentObject var vm: ViewModel
    @State private var name = ""

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Text("Messaging")
                .font(.largeTitle).bold()
            TextField("Your name", text: $name)
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal, 40)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
            Button("Continue") { vm.identify(name: name.trimmingCharacters(in: .whitespaces)) }
                .buttonStyle(.borderedProminent)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            Spacer()
        }
    }
}

// MARK: - Conversation

struct ConversationView: View {
    @EnvironmentObject var vm: ViewModel
    @State private var recipient = ""
    @State private var messageText = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                messageList
                composerBar
            }
            .navigationTitle(vm.username ?? "")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Sync") { vm.syncOnce() }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    Text("pending:\(vm.pendingCount) \(vm.syncState)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 4) {
                    ForEach(vm.messages, id: \.clientMessageID) { msg in
                        MessageRow(msg: msg, me: vm.username ?? "")
                            .id(msg.clientMessageID)
                    }
                }
                .padding(.horizontal, 8)
                .padding(.top, 8)
            }
            .onChange(of: vm.messages.count) {
                if let last = vm.messages.last {
                    withAnimation { proxy.scrollTo(last.clientMessageID, anchor: .bottom) }
                }
            }
        }
    }

    private var composerBar: some View {
        VStack(spacing: 4) {
            TextField("To", text: $recipient)
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
            HStack {
                TextField("Message", text: $messageText)
                    .textFieldStyle(.roundedBorder)
                Button("Send") {
                    vm.send(recipient: recipient.trimmingCharacters(in: .whitespaces),
                            text: messageText.trimmingCharacters(in: .whitespaces))
                    messageText = ""
                }
                .buttonStyle(.borderedProminent)
                .disabled(recipient.trimmingCharacters(in: .whitespaces).isEmpty ||
                          messageText.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(8)
        .background(.regularMaterial)
    }
}

// MARK: - MessageRow

struct MessageRow: View {
    let msg: MessageSnapshot
    let me: String

    private var isMine: Bool { msg.sender == me }

    var body: some View {
        HStack {
            if isMine { Spacer(minLength: 60) }
            VStack(alignment: isMine ? .trailing : .leading, spacing: 2) {
                if !isMine {
                    Text(msg.sender).font(.caption).foregroundStyle(.secondary)
                }
                Text(msg.text)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(isMine ? Color.blue.opacity(0.2) : Color.gray.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                Text(msg.status + (msg.errorCode.map { " (\($0))" } ?? ""))
                    .font(.caption2).foregroundStyle(.secondary)
            }
            if !isMine { Spacer(minLength: 60) }
        }
    }
}
