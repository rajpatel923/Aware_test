// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Messaging",
    platforms: [.macOS(.v13), .iOS(.v17)],
    products: [
        .executable(name: "messaging-cli", targets: ["MessagingCLI"]),
        .library(name: "MessagingCore", targets: ["MessagingCore"]),
        .library(name: "MessagingHTTP", targets: ["MessagingHTTP"]),
        .library(name: "MessagingSQLite", targets: ["MessagingSQLite"]),
    ],
    dependencies: [
        .package(url: "https://github.com/groue/GRDB.swift", .upToNextMajor(from: "6.0.0")),
    ],
    targets: [
        .target(
            name: "MessagingCore"
        ),
        .target(
            name: "MessagingHTTP",
            dependencies: ["MessagingCore"]
        ),
        .target(
            name: "MessagingSQLite",
            dependencies: [
                "MessagingCore",
                .product(name: "GRDB", package: "GRDB.swift"),
            ]
        ),
        .executableTarget(
            name: "MessagingCLI",
            dependencies: ["MessagingCore", "MessagingHTTP", "MessagingSQLite"]
        ),
        // XCTest requires Xcode; disabled until N01 (Xcode install) is unblocked.
        // .testTarget(name: "MessagingTests", dependencies: ["MessagingCore", "MessagingSQLite",
        //     .product(name: "GRDB", package: "GRDB.swift")], path: "Tests/MessagingTests"),
    ]
)
