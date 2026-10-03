"""A02 acceptance tests — Kotlin CLI against the real server.

Each test maps to one of the seven A02 guarantees in .agent/task.md.
The Kotlin CLI is expected at android/messaging-cli/build/libs/messaging-cli.jar.
"""
import json
import sys
from pathlib import Path

import pytest

from harness import AssertionFailure, ClientProcess, ScenarioRunner, ServerProcess

REPO = Path(__file__).parent.parent
KOTLIN_JAR = REPO / "android" / "messaging-cli" / "build" / "libs" / "messaging-cli.jar"
SPEC = REPO / "spec"

KOTLIN_CMD = ["java", "-jar", str(KOTLIN_JAR)]


def _require_kotlin():
    if not KOTLIN_JAR.exists():
        pytest.skip(f"Kotlin CLI not built: {KOTLIN_JAR}")


@pytest.fixture
def kotlin_server(tmp_path):
    s = ServerProcess()
    s.start()
    yield s
    s.stop()


@pytest.fixture
def make_kotlin(kotlin_server, tmp_path):
    created: list[ClientProcess] = []

    def _make(name: str, page_size: int | None = None) -> ClientProcess:
        c = ClientProcess(
            executable=KOTLIN_CMD,
            base_url=kotlin_server.base_url,
            data_dir=tmp_path / name,
            page_size=page_size,
        )
        c.start()
        created.append(c)
        return c

    yield _make

    for c in created:
        c.stop()


# ── A02-1: basic send and receive ─────────────────────────────────────────────

def test_kotlin_basic_exchange(make_kotlin):
    _require_kotlin()
    alice = make_kotlin("alice")
    bob = make_kotlin("bob")

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})

    send = alice.command("send", {"recipient": "bob", "text": "hello from kotlin"})
    assert send["ok"] is True
    mid = send["result"]["client_message_id"]

    sa = alice.command("sync_once")
    assert sa["result"]["outcome"] == "ok"
    assert sa["result"]["pending"] == 0

    sb = bob.command("sync_once")
    assert sb["result"]["received"] == 1

    snap = bob.command("snapshot")
    msgs = snap["result"]["messages"]
    assert any(m["client_message_id"] == mid and m["status"] == "accepted" for m in msgs)


# ── A02-2: offline queue, reconnect, flush ─────────────────────────────────────

def test_kotlin_offline_queue_flush(make_kotlin):
    _require_kotlin()
    alice = make_kotlin("alice")
    bob = make_kotlin("bob")

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once")   # prime epoch
    bob.command("sync_once")

    alice.command("offline", {"enabled": True})
    send = alice.command("send", {"recipient": "bob", "text": "queued offline"})
    mid = send["result"]["client_message_id"]

    snap = alice.command("snapshot")
    assert snap["result"]["pending_count"] == 1
    assert any(m["client_message_id"] == mid and m["status"] == "queued" for m in snap["result"]["messages"])

    alice.command("offline", {"enabled": False})
    sa = alice.command("sync_once")
    assert sa["result"]["outcome"] == "ok"
    assert sa["result"]["pending"] == 0

    bob.command("sync_once")
    snap_b = bob.command("snapshot")
    assert any(m["client_message_id"] == mid and m["status"] == "accepted" for m in snap_b["result"]["messages"])


# ── A02-3: lost submit response — idempotent resubmit ──────────────────────────

def test_kotlin_lost_ack_scenario(kotlin_server, make_kotlin):
    _require_kotlin()
    alice = make_kotlin("alice")
    bob = make_kotlin("bob")
    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once")
    bob.command("sync_once")
    scenario = json.loads((SPEC / "lost_ack.json").read_text())
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=kotlin_server).run()


# ── A02-4: lost inbox response — no duplicate on refetch ──────────────────────

def test_kotlin_repeat_inbox_scenario(kotlin_server, make_kotlin):
    _require_kotlin()
    alice = make_kotlin("alice")
    bob = make_kotlin("bob")
    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once")
    bob.command("sync_once")
    scenario = json.loads((SPEC / "repeat_inbox.json").read_text())
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=kotlin_server).run()


# ── A02-5: client restart — queue survives ─────────────────────────────────────

def test_kotlin_client_restart_scenario(kotlin_server, tmp_path):
    _require_kotlin()
    alice_dir = tmp_path / "alice"
    bob_dir = tmp_path / "bob"

    alice = ClientProcess(executable=KOTLIN_CMD, base_url=kotlin_server.base_url, data_dir=alice_dir)
    alice.start()
    bob = ClientProcess(executable=KOTLIN_CMD, base_url=kotlin_server.base_url, data_dir=bob_dir)
    bob.start()

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once")
    bob.command("sync_once")

    scenario = json.loads((SPEC / "client_restart.json").read_text())
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=kotlin_server).run()

    alice.stop()
    bob.stop()


# ── A02-6: server restart → epoch change → reset_session → resume ─────────────

def test_kotlin_server_restart_scenario(kotlin_server, tmp_path):
    _require_kotlin()
    alice = ClientProcess(executable=KOTLIN_CMD, base_url=kotlin_server.base_url, data_dir=tmp_path / "alice")
    bob = ClientProcess(executable=KOTLIN_CMD, base_url=kotlin_server.base_url, data_dir=tmp_path / "bob")
    alice.start(); bob.start()

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once"); bob.command("sync_once")

    scenario = json.loads((SPEC / "server_restart.json").read_text())
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=kotlin_server).run()

    alice.stop(); bob.stop()


# ── A02-7: two instances share no state ──────────────────────────────────────

def test_kotlin_separate_instances(tmp_path):
    _require_kotlin()
    s1 = ServerProcess(); s1.start()
    s2 = ServerProcess(); s2.start()

    try:
        c1 = ClientProcess(executable=KOTLIN_CMD, base_url=s1.base_url, data_dir=tmp_path / "c1")
        c2 = ClientProcess(executable=KOTLIN_CMD, base_url=s2.base_url, data_dir=tmp_path / "c2")
        c1.start(); c2.start()

        c1.command("identify", {"name": "alice"})
        c2.command("identify", {"name": "alice"})
        c1.command("sync_once"); c2.command("sync_once")

        c1.command("send", {"recipient": "bob", "text": "only in s1"})
        c1.command("sync_once")

        snap = c2.command("snapshot")
        assert snap["result"]["messages"] == []  # c2 has no messages

        c1.stop(); c2.stop()
    finally:
        s1.stop(); s2.stop()
