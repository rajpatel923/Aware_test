"""B01 acceptance tests — in-process against the real FastAPI app."""
import asyncio
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _mid(n: int = 1) -> str:
    """Deterministic valid UUID for tests. Uses hex representation of n."""
    return f"00000000-0000-4000-8000-{n:012x}"


def _msg(
    mid: str | None = None,
    sender: str = "alice",
    recipient: str = "bob",
    text: str = "hi",
) -> dict:
    return {
        "client_message_id": _mid(1) if mid is None else mid,
        "sender": sender,
        "recipient": recipient,
        "text": text,
    }


def _h(epoch: str) -> dict:
    return {"X-Server-Epoch": epoch}


# ── 1. meta returns version and stable epoch ─────────────────────────────────

async def test_meta_version_and_stable_epoch(ctx):
    client, epoch = ctx
    r1 = await client.get("/v1/meta")
    r2 = await client.get("/v1/meta")
    assert r1.status_code == 200
    assert r1.json()["protocol_version"] == "1"
    assert r1.json()["server_epoch"] == epoch
    assert r1.json()["server_epoch"] == r2.json()["server_epoch"]


# ── 2. new message accepted and appears in inbox ──────────────────────────────

async def test_new_message_accepted_and_in_inbox(ctx):
    client, epoch = ctx
    payload = _msg(_mid(1))
    r = await client.post("/v1/messages", json=payload, headers=_h(epoch))
    assert r.status_code == 200
    body = r.json()
    assert body["client_message_id"] == payload["client_message_id"]
    assert body["sender"] == "alice"
    assert body["recipient"] == "bob"
    assert body["text"] == "hi"
    assert body["sequence"] >= 1
    assert _TS_RE.match(body["accepted_at"])
    assert body["server_epoch"] == epoch

    inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    assert inbox.status_code == 200
    msgs = inbox.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["client_message_id"] == payload["client_message_id"]
    assert inbox.headers.get("cache-control") == "no-store"


# ── 3. exact retry returns original (lost-response safety) ───────────────────

async def test_exact_retry_returns_original(ctx):
    client, epoch = ctx
    payload = _msg(_mid(1))
    r1 = await client.post("/v1/messages", json=payload, headers=_h(epoch))
    r2 = await client.post("/v1/messages", json=payload, headers=_h(epoch))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["sequence"] == r2.json()["sequence"]
    assert r1.json()["accepted_at"] == r2.json()["accepted_at"]

    inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    assert len(inbox.json()["messages"]) == 1


# ── 4. concurrent duplicates → one record; conflicting key → conflict ────────

async def test_concurrent_duplicates_produce_one_record(ctx):
    client, epoch = ctx
    payload = _msg(_mid(1))
    r1, r2 = await asyncio.gather(
        client.post("/v1/messages", json=payload, headers=_h(epoch)),
        client.post("/v1/messages", json=payload, headers=_h(epoch)),
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["sequence"] == r2.json()["sequence"]
    assert r1.json()["accepted_at"] == r2.json()["accepted_at"]
    inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    assert len(inbox.json()["messages"]) == 1


async def test_conflicting_key_rejected_and_indexes_intact(ctx):
    client, epoch = ctx
    mid = _mid(1)
    r1 = await client.post("/v1/messages", json=_msg(mid, text="original"), headers=_h(epoch))
    assert r1.status_code == 200

    conflict = await client.post("/v1/messages", json=_msg(mid, text="different"), headers=_h(epoch))
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "MESSAGE_ID_CONFLICT"

    r2 = await client.post("/v1/messages", json=_msg(_mid(2), text="next"), headers=_h(epoch))
    assert r2.status_code == 200
    assert r2.json()["sequence"] == r1.json()["sequence"] + 1


# ── 5. sender is part of key; mailboxes isolated; unregistered user; self-send

async def test_sender_is_part_of_key(ctx):
    client, epoch = ctx
    mid = _mid(1)
    r_alice = await client.post(
        "/v1/messages", json=_msg(mid, sender="alice", recipient="bob"), headers=_h(epoch)
    )
    r_carol = await client.post(
        "/v1/messages", json=_msg(mid, sender="carol", recipient="bob"), headers=_h(epoch)
    )
    assert r_alice.status_code == 200
    assert r_carol.status_code == 200
    assert r_alice.json()["sequence"] != r_carol.json()["sequence"]


async def test_mailbox_isolation(ctx):
    client, epoch = ctx
    await client.post("/v1/messages", json=_msg(_mid(1), sender="alice", recipient="bob"), headers=_h(epoch))
    await client.post("/v1/messages", json=_msg(_mid(2), sender="alice", recipient="carol"), headers=_h(epoch))
    bob_inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    carol_inbox = await client.get("/v1/inbox/carol", params={"after": 0}, headers=_h(epoch))
    assert len(bob_inbox.json()["messages"]) == 1
    assert len(carol_inbox.json()["messages"]) == 1
    assert bob_inbox.json()["messages"][0]["recipient"] == "bob"
    assert carol_inbox.json()["messages"][0]["recipient"] == "carol"


async def test_unregistered_recipient_receives_message(ctx):
    client, epoch = ctx
    await client.post("/v1/messages", json=_msg(_mid(1), recipient="nobody"), headers=_h(epoch))
    inbox = await client.get("/v1/inbox/nobody", params={"after": 0}, headers=_h(epoch))
    assert len(inbox.json()["messages"]) == 1


async def test_self_send(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/messages", json=_msg(_mid(1), sender="alice", recipient="alice"), headers=_h(epoch)
    )
    assert r.status_code == 200
    inbox = await client.get("/v1/inbox/alice", params={"after": 0}, headers=_h(epoch))
    assert len(inbox.json()["messages"]) == 1


# ── 6. paging ────────────────────────────────────────────────────────────────

async def test_paging_multiple_pages(ctx):
    client, epoch = ctx
    for i in range(1, 4):
        await client.post("/v1/messages", json=_msg(_mid(i), text=f"msg{i}"), headers=_h(epoch))

    page1 = await client.get("/v1/inbox/bob", params={"after": 0, "limit": 2}, headers=_h(epoch))
    assert page1.status_code == 200
    assert page1.json()["has_more"] is True
    assert len(page1.json()["messages"]) == 2
    cursor = page1.json()["next_cursor"]

    page2 = await client.get("/v1/inbox/bob", params={"after": cursor, "limit": 2}, headers=_h(epoch))
    assert page2.status_code == 200
    assert page2.json()["has_more"] is False
    assert len(page2.json()["messages"]) == 1
    assert page2.json()["next_cursor"] == page2.json()["messages"][0]["sequence"]


async def test_paging_empty_page(ctx):
    client, epoch = ctx
    r = await client.post("/v1/messages", json=_msg(_mid(1)), headers=_h(epoch))
    assert r.status_code == 200
    seq = r.json()["sequence"]

    empty = await client.get("/v1/inbox/bob", params={"after": seq}, headers=_h(epoch))
    assert empty.status_code == 200
    assert empty.json()["messages"] == []
    assert empty.json()["has_more"] is False
    assert empty.json()["next_cursor"] == seq


async def test_paging_exclusive_cursor(ctx):
    client, epoch = ctx
    r1 = await client.post("/v1/messages", json=_msg(_mid(1), text="first"), headers=_h(epoch))
    r2 = await client.post("/v1/messages", json=_msg(_mid(2), text="second"), headers=_h(epoch))
    assert r1.status_code == 200
    assert r2.status_code == 200
    seq1 = r1.json()["sequence"]

    inbox = await client.get("/v1/inbox/bob", params={"after": seq1}, headers=_h(epoch))
    msgs = inbox.json()["messages"]
    assert len(msgs) == 1
    assert msgs[0]["sequence"] == r2.json()["sequence"]


async def test_paging_gaps(ctx):
    client, epoch = ctx
    r1 = await client.post("/v1/messages", json=_msg(_mid(1), recipient="bob"), headers=_h(epoch))
    await client.post("/v1/messages", json=_msg(_mid(2), recipient="carol"), headers=_h(epoch))
    r3 = await client.post("/v1/messages", json=_msg(_mid(3), recipient="bob"), headers=_h(epoch))
    assert r1.status_code == 200
    assert r3.status_code == 200

    inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    seqs = [m["sequence"] for m in inbox.json()["messages"]]
    assert seqs == [r1.json()["sequence"], r3.json()["sequence"]]
    assert seqs[1] - seqs[0] == 2


async def test_paging_repeated_read_stable(ctx):
    client, epoch = ctx
    await client.post("/v1/messages", json=_msg(_mid(1)), headers=_h(epoch))
    p1 = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    p2 = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    assert p1.json()["messages"] == p2.json()["messages"]
    assert p1.json()["next_cursor"] == p2.json()["next_cursor"]


# ── 7. validation errors ──────────────────────────────────────────────────────

async def test_invalid_username_rejected(ctx):
    client, epoch = ctx
    for i, bad in enumerate(["Alice", "al ice", "a" * 33, "é"], start=1):
        r = await client.post("/v1/messages", json=_msg(_mid(i), sender=bad), headers=_h(epoch))
        assert r.status_code == 422, f"expected 422 for sender={bad!r}, got {r.status_code}"
        assert r.json()["code"] == "INVALID_REQUEST"


async def test_invalid_uuid_rejected(ctx):
    client, epoch = ctx
    for bad in ["not-a-uuid", "00000000-0000-0000-0000-00000000000z", ""]:
        r = await client.post(
            "/v1/messages",
            json={**_msg(), "client_message_id": bad},
            headers=_h(epoch),
        )
        assert r.status_code == 422, f"expected 422 for mid={bad!r}"
        assert r.json()["code"] == "INVALID_REQUEST"


async def test_text_too_long_rejected(ctx):
    client, epoch = ctx
    r = await client.post("/v1/messages", json=_msg(text="a" * 4097), headers=_h(epoch))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_text_multibyte_limit(ctx):
    client, epoch = ctx
    valid = "\U0001f44b" * 1024     # 1024 × 4 bytes = 4096 bytes
    invalid = "\U0001f44b" * 1025   # 4100 bytes
    r_ok = await client.post("/v1/messages", json=_msg(text=valid), headers=_h(epoch))
    assert r_ok.status_code == 200
    r_bad = await client.post("/v1/messages", json=_msg(_mid(2), text=invalid), headers=_h(epoch))
    assert r_bad.status_code == 422


async def test_unknown_field_in_body_rejected(ctx):
    client, epoch = ctx
    payload = {**_msg(_mid(1)), "extra": "field"}
    r = await client.post("/v1/messages", json=payload, headers=_h(epoch))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_missing_epoch_header_rejected(ctx):
    client, _ = ctx
    r = await client.post("/v1/messages", json=_msg(_mid(1)))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_invalid_limit_rejected(ctx):
    client, epoch = ctx
    r0 = await client.get("/v1/inbox/bob", params={"after": 0, "limit": 0}, headers=_h(epoch))
    assert r0.status_code == 422
    r101 = await client.get("/v1/inbox/bob", params={"after": 0, "limit": 101}, headers=_h(epoch))
    assert r101.status_code == 422


async def test_negative_after_rejected(ctx):
    client, epoch = ctx
    r = await client.get("/v1/inbox/bob", params={"after": -1}, headers=_h(epoch))
    assert r.status_code == 422


# ── 8. error envelope shape ───────────────────────────────────────────────────

async def test_error_envelope_shape(ctx):
    client, epoch = ctx
    r = await client.post("/v1/messages", json=_msg(text=""), headers=_h(epoch))
    assert r.status_code == 422
    body = r.json()
    assert {"code", "message", "server_epoch"} <= set(body.keys())
    assert body["code"] == "INVALID_REQUEST"
    assert isinstance(body["message"], str)


async def test_malformed_json_uses_envelope(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/messages",
        content=b"{not valid json",
        headers={**_h(epoch), "Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


# ── 9. stale epoch rejected; no state change ─────────────────────────────────

async def test_stale_epoch_rejected_and_no_state_change(ctx):
    client, epoch = ctx
    stale = "a" * 32
    assert stale != epoch

    r = await client.post("/v1/messages", json=_msg(_mid(1)), headers=_h(stale))
    assert r.status_code == 409
    assert r.json()["code"] == "SERVER_EPOCH_CHANGED"
    assert r.json()["server_epoch"] == epoch

    inbox = await client.get("/v1/inbox/bob", params={"after": 0}, headers=_h(epoch))
    assert inbox.json()["messages"] == []


# ── 10. cursor beyond highest sequence ───────────────────────────────────────

async def test_cursor_beyond_highest_sequence_rejected(ctx):
    client, epoch = ctx
    r = await client.get("/v1/inbox/bob", params={"after": 9999}, headers=_h(epoch))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_CURSOR"


# ── 11. separate app instances share no state ─────────────────────────────────

async def test_separate_instances_no_shared_state():
    app1 = create_app()
    app2 = create_app()
    async with (
        AsyncClient(transport=ASGITransport(app=app1), base_url="http://test") as c1,
        AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c2,
    ):
        e1 = (await c1.get("/v1/meta")).json()["server_epoch"]
        e2 = (await c2.get("/v1/meta")).json()["server_epoch"]
        assert e1 != e2

        await c1.post("/v1/messages", json=_msg(_mid(1)), headers=_h(e1))
        inbox2 = await c2.get("/v1/inbox/bob", params={"after": 0}, headers=_h(e2))
        assert inbox2.json()["messages"] == []
