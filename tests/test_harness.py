"""V01 — harness self-tests.
Verifies the test infrastructure independently of the Swift/Kotlin clients.
Every test uses the Python reference client against the real server.
"""
import json
from pathlib import Path

import pytest

from harness import AssertionFailure, ClientProcess, ScenarioRunner, ServerProcess

SPEC = Path(__file__).parent.parent / "spec"


# ── 1. server lifecycle ───────────────────────────────────────────────────────

def test_server_starts_and_responds(server):
    import httpx
    resp = httpx.get(f"{server.base_url}/v1/meta", timeout=3)
    assert resp.status_code == 200
    assert resp.json()["server_epoch"] == server.epoch


# ── 2. client process + JSON Lines protocol ───────────────────────────────────

def test_client_identify(make_client):
    c = make_client("alice")
    resp = c.command("identify", {"name": "Alice"})
    assert resp["ok"] is True
    assert resp["result"]["username"] == "alice"


def test_client_shutdown(make_client):
    c = make_client("alice")
    resp = c.command("shutdown")
    assert resp["ok"] is True


# ── 3. bind and variable substitution ────────────────────────────────────────

def test_bind_tracks_message_id(make_client, server):
    c = make_client("alice")
    c.command("identify", {"name": "alice"})
    c.command("sync_once")  # prime the epoch

    send_resp = c.command("send", {"recipient": "bob", "text": "hello"})
    assert send_resp["ok"] is True
    mid = send_resp["result"]["client_message_id"]

    runner = ScenarioRunner(scenario={"steps": []}, clients={"alice": c}, server=server)
    runner._bind_result("m1", send_resp["result"])
    assert runner._bindings["m1"] == mid
    assert runner._substitute("$m1") == mid


# ── 4. basic send + receive (two reference clients, real server) ───────────────

def test_basic_message_exchange(make_client):
    alice = make_client("alice")
    bob = make_client("bob")

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})

    send_r = alice.command("send", {"recipient": "bob", "text": "hey bob"})
    assert send_r["ok"] is True
    mid = send_r["result"]["client_message_id"]

    sync_a = alice.command("sync_once")
    assert sync_a["result"]["outcome"] == "ok"
    assert sync_a["result"]["pending"] == 0

    sync_b = bob.command("sync_once")
    assert sync_b["result"]["outcome"] == "ok"
    assert sync_b["result"]["received"] == 1

    snap_b = bob.command("snapshot")
    msgs = snap_b["result"]["messages"]
    assert any(m["client_message_id"] == mid and m["status"] == "accepted" for m in msgs)


# ── 5. runner assertions pass on correct scenario ─────────────────────────────

def test_runner_passes_correct_assertions(make_client, server):
    alice = make_client("alice")
    bob = make_client("bob")

    scenario = {
        "steps": [
            {"client": "alice", "cmd": "identify", "args": {"name": "alice"}},
            {"client": "bob", "cmd": "identify", "args": {"name": "bob"}},
            {
                "client": "alice", "cmd": "send",
                "args": {"recipient": "bob", "text": "runner test"},
                "bind": "m1",
                "expect": {"result": {"status": "queued"}},
            },
            {
                "client": "alice", "cmd": "sync_once",
                "expect": {"result": {"outcome": "ok", "pending": 0}},
            },
            {
                "client": "bob", "cmd": "sync_once",
                "expect": {"result": {"outcome": "ok", "received": 1}},
            },
            {
                "client": "bob", "cmd": "snapshot",
                "expect": {
                    "contains": [{"client_message_id": "$m1", "status": "accepted"}],
                },
            },
        ]
    }
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=server).run()


# ── 6. deliberately wrong assertion must fail ─────────────────────────────────

def test_wrong_assertion_raises_failure(make_client, server):
    alice = make_client("alice")
    alice.command("identify", {"name": "alice"})

    # Expect "accepted" before any sync — the message is still "queued".
    scenario = {
        "steps": [
            {
                "client": "alice", "cmd": "send",
                "args": {"recipient": "bob", "text": "will fail"},
                "bind": "m1",
            },
            {
                "client": "alice", "cmd": "snapshot",
                "expect": {
                    "contains": [{"client_message_id": "$m1", "status": "accepted"}],
                },
            },
        ]
    }
    with pytest.raises(AssertionFailure):
        ScenarioRunner(scenario, clients={"alice": alice, "bob": alice}, server=server).run()


# ── 7. lost_ack scenario (spec/lost_ack.json, both roles use reference client) ─

def _run_scenario(scenario_file: Path, server, make_client):
    scenario = json.loads(scenario_file.read_text())
    alice = make_client("alice")
    bob = make_client("bob")
    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    # prime server epoch for both
    alice.command("sync_once")
    bob.command("sync_once")
    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=server).run()


def test_lost_ack_scenario(server, make_client):
    _run_scenario(SPEC / "lost_ack.json", server, make_client)


def test_client_restart_scenario(server, make_client, tmp_path):
    scenario = json.loads((SPEC / "client_restart.json").read_text())

    import sys
    from harness import ClientProcess
    TESTS_DIR = Path(__file__).parent
    REF = [sys.executable, str(TESTS_DIR / "reference_client.py")]

    # Use a fixed data dir so restart reuses the same DB
    alice_dir = tmp_path / "alice"
    bob_dir = tmp_path / "bob"

    alice = ClientProcess(executable=REF, base_url=server.base_url, data_dir=alice_dir)
    alice.start()
    bob = ClientProcess(executable=REF, base_url=server.base_url, data_dir=bob_dir)
    bob.start()

    alice.command("identify", {"name": "alice"})
    bob.command("identify", {"name": "bob"})
    alice.command("sync_once")
    bob.command("sync_once")

    ScenarioRunner(scenario, clients={"alice": alice, "bob": bob}, server=server).run()

    alice.stop()
    bob.stop()
