"""X01 acceptance tests — cross-language interoperability.

Run the required Alice/Bob scenario (spec/alice_bob.json) twice:
  run 1: alice=Swift, bob=Kotlin
  run 2: alice=Kotlin, bob=Swift

Requires:
  ios/.build/debug/messaging-cli  (built via `swift build`)
  android/messaging-cli/build/libs/messaging-cli.jar  (built via `./gradlew :messaging-cli:jar`)
"""
import json
from pathlib import Path

import pytest

from harness import ClientProcess, ScenarioRunner, ServerProcess

REPO = Path(__file__).parent.parent
SWIFT_BIN = REPO / "ios" / ".build" / "debug" / "messaging-cli"
KOTLIN_JAR = REPO / "android" / "messaging-cli" / "build" / "libs" / "messaging-cli.jar"
SPEC = REPO / "spec"

SWIFT_CMD = [str(SWIFT_BIN)]
KOTLIN_CMD = ["java", "-jar", str(KOTLIN_JAR)]


def _require_clients():
    if not SWIFT_BIN.exists():
        pytest.skip(f"Swift CLI not built: {SWIFT_BIN}")
    if not KOTLIN_JAR.exists():
        pytest.skip(f"Kotlin CLI not built: {KOTLIN_JAR}")


def _run_alice_bob(alice_cmd, bob_cmd, tmp_path):
    """Run the alice_bob.json scenario with the given client commands."""
    server = ServerProcess()
    server.start()

    alice = ClientProcess(executable=alice_cmd, base_url=server.base_url, data_dir=tmp_path / "alice")
    bob = ClientProcess(executable=bob_cmd, base_url=server.base_url, data_dir=tmp_path / "bob")
    alice.start()
    bob.start()

    try:
        scenario = json.loads((SPEC / "alice_bob.json").read_text())
        ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=server).run()
    finally:
        alice.stop()
        bob.stop()
        server.stop()


# ── X01-1: alice=Swift, bob=Kotlin ─────────────────────────────────────────────

def test_alice_swift_bob_kotlin(tmp_path):
    _require_clients()
    _run_alice_bob(SWIFT_CMD, KOTLIN_CMD, tmp_path)


# ── X01-2: alice=Kotlin, bob=Swift ─────────────────────────────────────────────

def test_alice_kotlin_bob_swift(tmp_path):
    _require_clients()
    _run_alice_bob(KOTLIN_CMD, SWIFT_CMD, tmp_path)
