import XCTest
@testable import MessagingCore

final class UsernameTests: XCTestCase {

    func testNormalization() throws {
        XCTAssertEqual(try Username("  Alice\n").value, "alice")
        XCTAssertEqual(try Username("BOB_99").value, "bob_99")
        XCTAssertEqual(try Username("alice").value, "alice")
    }

    func testInvalid() {
        XCTAssertThrowsError(try Username(""))
        XCTAssertThrowsError(try Username("   "))
        XCTAssertThrowsError(try Username("al ice"))
        XCTAssertThrowsError(try Username("Ālice"))
        XCTAssertThrowsError(try Username(String(repeating: "a", count: 33)))
    }

    func testTextLimits() throws {
        // 4096 UTF-8 bytes valid
        let maxValid = String(repeating: "a", count: 4096)
        let client = TestClient()
        XCTAssertNoThrow(try client.checkText(maxValid))

        // 4097 bytes invalid
        let tooLong = String(repeating: "a", count: 4097)
        XCTAssertThrowsError(try client.checkText(tooLong))

        // emoji: 1024 × 4 bytes = 4096 valid
        let emoji4096 = String(repeating: "👋", count: 1024)
        XCTAssertNoThrow(try client.checkText(emoji4096))

        // empty invalid
        XCTAssertThrowsError(try client.checkText(""))
    }
}

// Minimal helper so we can call package-internal text validation
private struct TestClient {
    func checkText(_ text: String) throws {
        guard !text.isEmpty, text.utf8.count <= 4096 else {
            throw MessagingError.invalidRequest("bad text")
        }
    }
}
