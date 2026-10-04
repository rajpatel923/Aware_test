"""B01 acceptance tests — in-process against the real FastAPI app."""
import asyncio
import re

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _eid(n: int = 1) -> str:
    """Deterministic valid UUID for tests."""
    return f"00000000-0000-4000-8000-{n:012x}"


def _msg(
    eid: str | None = None,
    sender: str = "alice",
    recipient: str = "bob",
    text: str = "hi",
    event_type: str = "message.text",
    body: dict | None = None,
) -> dict:
    return {
        "event_id": _eid(1) if eid is None else eid,
        "type": event_type,
        "sender": sender,
        "recipient": recipient,
        "body": body if body is not None else {"text": text},
    }


def _h(epoch: str) -> dict:
    return {"X-Server-Epoch": epoch}


# ── 1. meta returns version, epoch, and event types ──────────────────────────

async def test_meta_version_and_stable_epoch(ctx):
    client, epoch = ctx
    r1 = await client.get("/v1/meta")
    r2 = await client.get("/v1/meta")
    assert r1.status_code == 200
    assert r1.json()["protocol_version"] == 1          # integer, not "1"
    assert r1.json()["server_epoch"] == epoch
    assert r1.json()["server_epoch"] == r2.json()["server_epoch"]
    assert r1.headers.get("cache-control") == "no-store"


async def test_meta_event_types(ctx):
    client, _ = ctx
    r = await client.get("/v1/meta")
    types = r.json()["event_types"]
    assert isinstance(types, list)
    assert "message.text" in types


# ── 2. new event accepted and appears in mailbox ──────────────────────────────

async def test_new_event_accepted_and_in_mailbox(ctx):
    client, epoch = ctx
    payload = _msg(_eid(1))
    r = await client.post("/v1/events", json=payload, headers=_h(epoch))
    assert r.status_code == 200
    body = r.json()
    assert body["event_id"] == payload["event_id"]
    assert body["type"] == "message.text"
    assert body["sender"] == "alice"
    assert body["recipient"] == "bob"
    assert body["body"] == {"text": "hi"}
    assert body["seq"] >= 1
    assert _TS_RE.match(body["accepted_at"])
    assert body["server_epoch"] == epoch
    assert r.headers.get("cache-control") == "no-store"

    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch)
    )
    assert mailbox.status_code == 200
    events = mailbox.json()["events"]
    assert len(events) == 1
    assert events[0]["event_id"] == payload["event_id"]
    assert events[0]["body"] == {"text": "hi"}
    assert mailbox.headers.get("cache-control") == "no-store"


# ── 3. exact retry returns original (P6.1 — lost-response safety) ─────────────

async def test_exact_retry_returns_original(ctx):
    client, epoch = ctx
    payload = _msg(_eid(1))
    r1 = await client.post("/v1/events", json=payload, headers=_h(epoch))
    r2 = await client.post("/v1/events", json=payload, headers=_h(epoch))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["seq"] == r2.json()["seq"]
    assert r1.json()["accepted_at"] == r2.json()["accepted_at"]

    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch)
    )
    assert len(mailbox.json()["events"]) == 1


# ── 4. concurrent duplicates; conflicting key ────────────────────────────────

async def test_concurrent_duplicates_produce_one_record(ctx):
    client, epoch = ctx
    payload = _msg(_eid(1))
    r1, r2 = await asyncio.gather(
        client.post("/v1/events", json=payload, headers=_h(epoch)),
        client.post("/v1/events", json=payload, headers=_h(epoch)),
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["seq"] == r2.json()["seq"]
    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch)
    )
    assert len(mailbox.json()["events"]) == 1


async def test_conflicting_key_rejected_and_indexes_intact(ctx):
    client, epoch = ctx
    eid = _eid(1)
    r1 = await client.post("/v1/events", json=_msg(eid, text="original"), headers=_h(epoch))
    assert r1.status_code == 200

    conflict = await client.post(
        "/v1/events", json=_msg(eid, text="different"), headers=_h(epoch)
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "EVENT_ID_CONFLICT"

    r2 = await client.post("/v1/events", json=_msg(_eid(2), text="next"), headers=_h(epoch))
    assert r2.status_code == 200
    assert r2.json()["seq"] == r1.json()["seq"] + 1


# ── 5. sender in key; mailboxes isolated; unregistered user; self-send ────────

async def test_sender_is_part_of_key(ctx):
    client, epoch = ctx
    eid = _eid(1)
    r_alice = await client.post(
        "/v1/events", json=_msg(eid, sender="alice", recipient="bob"), headers=_h(epoch)
    )
    r_carol = await client.post(
        "/v1/events", json=_msg(eid, sender="carol", recipient="bob"), headers=_h(epoch)
    )
    assert r_alice.status_code == 200
    assert r_carol.status_code == 200
    assert r_alice.json()["seq"] != r_carol.json()["seq"]


async def test_mailbox_isolation(ctx):
    client, epoch = ctx
    await client.post(
        "/v1/events", json=_msg(_eid(1), sender="alice", recipient="bob"), headers=_h(epoch)
    )
    await client.post(
        "/v1/events", json=_msg(_eid(2), sender="alice", recipient="carol"), headers=_h(epoch)
    )
    bob = await client.get("/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch))
    carol = await client.get(
        "/v1/mailboxes/carol/events", params={"after": 0}, headers=_h(epoch)
    )
    assert len(bob.json()["events"]) == 1
    assert len(carol.json()["events"]) == 1
    assert bob.json()["events"][0]["recipient"] == "bob"
    assert carol.json()["events"][0]["recipient"] == "carol"


async def test_unregistered_recipient_receives_event(ctx):
    client, epoch = ctx
    await client.post("/v1/events", json=_msg(_eid(1), recipient="nobody"), headers=_h(epoch))
    mailbox = await client.get(
        "/v1/mailboxes/nobody/events", params={"after": 0}, headers=_h(epoch)
    )
    assert len(mailbox.json()["events"]) == 1


async def test_self_send(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/events", json=_msg(_eid(1), sender="alice", recipient="alice"), headers=_h(epoch)
    )
    assert r.status_code == 200
    mailbox = await client.get(
        "/v1/mailboxes/alice/events", params={"after": 0}, headers=_h(epoch)
    )
    assert len(mailbox.json()["events"]) == 1


# ── 6. paging ────────────────────────────────────────────────────────────────

async def test_paging_multiple_pages(ctx):
    client, epoch = ctx
    for i in range(1, 4):
        await client.post("/v1/events", json=_msg(_eid(i), text=f"msg{i}"), headers=_h(epoch))

    page1 = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0, "limit": 2}, headers=_h(epoch)
    )
    assert page1.status_code == 200
    assert page1.json()["has_more"] is True
    assert len(page1.json()["events"]) == 2
    cursor = page1.json()["next_cursor"]

    page2 = await client.get(
        "/v1/mailboxes/bob/events", params={"after": cursor, "limit": 2}, headers=_h(epoch)
    )
    assert page2.status_code == 200
    assert page2.json()["has_more"] is False
    assert len(page2.json()["events"]) == 1
    assert page2.json()["next_cursor"] == page2.json()["events"][0]["seq"]


async def test_paging_empty_page(ctx):
    client, epoch = ctx
    r = await client.post("/v1/events", json=_msg(_eid(1)), headers=_h(epoch))
    assert r.status_code == 200
    seq = r.json()["seq"]

    empty = await client.get(
        "/v1/mailboxes/bob/events", params={"after": seq}, headers=_h(epoch)
    )
    assert empty.status_code == 200
    assert empty.json()["events"] == []
    assert empty.json()["has_more"] is False
    assert empty.json()["next_cursor"] == seq


async def test_paging_exclusive_cursor(ctx):
    client, epoch = ctx
    r1 = await client.post("/v1/events", json=_msg(_eid(1), text="first"), headers=_h(epoch))
    r2 = await client.post("/v1/events", json=_msg(_eid(2), text="second"), headers=_h(epoch))
    assert r1.status_code == 200
    assert r2.status_code == 200
    seq1 = r1.json()["seq"]

    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": seq1}, headers=_h(epoch)
    )
    events = mailbox.json()["events"]
    assert len(events) == 1
    assert events[0]["seq"] == r2.json()["seq"]


async def test_paging_gaps_from_other_mailboxes(ctx):
    client, epoch = ctx
    r1 = await client.post(
        "/v1/events", json=_msg(_eid(1), recipient="bob"), headers=_h(epoch)
    )
    await client.post("/v1/events", json=_msg(_eid(2), recipient="carol"), headers=_h(epoch))
    r3 = await client.post(
        "/v1/events", json=_msg(_eid(3), recipient="bob"), headers=_h(epoch)
    )
    assert r1.status_code == 200
    assert r3.status_code == 200

    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch)
    )
    seqs = [e["seq"] for e in mailbox.json()["events"]]
    assert seqs == [r1.json()["seq"], r3.json()["seq"]]
    assert seqs[1] - seqs[0] == 2


async def test_paging_repeated_read_stable(ctx):
    client, epoch = ctx
    await client.post("/v1/events", json=_msg(_eid(1)), headers=_h(epoch))
    p1 = await client.get("/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch))
    p2 = await client.get("/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch))
    assert p1.json()["events"] == p2.json()["events"]
    assert p1.json()["next_cursor"] == p2.json()["next_cursor"]


# ── 7. validation errors ──────────────────────────────────────────────────────

async def test_invalid_username_rejected(ctx):
    client, epoch = ctx
    for i, bad in enumerate(["Alice", "al ice", "a" * 33, "é"], start=1):
        r = await client.post(
            "/v1/events", json=_msg(_eid(i), sender=bad), headers=_h(epoch)
        )
        assert r.status_code == 422, f"expected 422 for sender={bad!r}"
        assert r.json()["code"] == "INVALID_REQUEST"


async def test_invalid_event_id_rejected(ctx):
    client, epoch = ctx
    for bad in ["not-a-uuid", "00000000-0000-0000-0000-00000000000z", ""]:
        payload = {**_msg(), "event_id": bad}
        r = await client.post("/v1/events", json=payload, headers=_h(epoch))
        assert r.status_code == 422, f"expected 422 for event_id={bad!r}"
        assert r.json()["code"] == "INVALID_REQUEST"


async def test_invalid_type_format_rejected(ctx):
    client, epoch = ctx
    for bad in ["MessageText", "message", ".text", "message.", "message text"]:
        r = await client.post(
            "/v1/events", json=_msg(event_type=bad), headers=_h(epoch)
        )
        assert r.status_code == 422, f"expected 422 for type={bad!r}"
        assert r.json()["code"] == "INVALID_REQUEST"


async def test_unsupported_type_rejected(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/events", json=_msg(event_type="reaction.add", body={"emoji": "👍"}),
        headers=_h(epoch),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "UNSUPPORTED_TYPE"


async def test_text_too_long_rejected(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/events", json=_msg(body={"text": "a" * 4097}), headers=_h(epoch)
    )
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_text_multibyte_limit(ctx):
    client, epoch = ctx
    valid = "\U0001f44b" * 1024    # 4096 bytes exactly
    invalid = "\U0001f44b" * 1025  # 4100 bytes
    r_ok = await client.post(
        "/v1/events", json=_msg(_eid(1), body={"text": valid}), headers=_h(epoch)
    )
    assert r_ok.status_code == 200
    r_bad = await client.post(
        "/v1/events", json=_msg(_eid(2), body={"text": invalid}), headers=_h(epoch)
    )
    assert r_bad.status_code == 422


async def test_empty_text_rejected(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/events", json=_msg(body={"text": ""}), headers=_h(epoch)
    )
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_unknown_field_in_envelope_rejected(ctx):
    client, epoch = ctx
    payload = {**_msg(_eid(1)), "extra": "field"}
    r = await client.post("/v1/events", json=payload, headers=_h(epoch))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_unknown_field_in_body_rejected(ctx):
    # A1.6: body of a known type must not have extra fields
    client, epoch = ctx
    r = await client.post(
        "/v1/events",
        json=_msg(_eid(1), body={"text": "hi", "extra": "field"}),
        headers=_h(epoch),
    )
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_missing_epoch_header_rejected(ctx):
    client, _ = ctx
    r = await client.post("/v1/events", json=_msg(_eid(1)))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"


async def test_invalid_limit_rejected(ctx):
    client, epoch = ctx
    r0 = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0, "limit": 0}, headers=_h(epoch)
    )
    assert r0.status_code == 422
    r101 = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0, "limit": 101}, headers=_h(epoch)
    )
    assert r101.status_code == 422


async def test_negative_after_rejected(ctx):
    client, epoch = ctx
    r = await client.get(
        "/v1/mailboxes/bob/events", params={"after": -1}, headers=_h(epoch)
    )
    assert r.status_code == 422


# ── 8. error envelope shape ───────────────────────────────────────────────────

async def test_error_envelope_shape(ctx):
    client, epoch = ctx
    r = await client.post("/v1/events", json=_msg(body={"text": ""}), headers=_h(epoch))
    assert r.status_code == 422
    body = r.json()
    assert {"code", "message", "server_epoch"} <= set(body.keys())
    assert body["code"] == "INVALID_REQUEST"
    assert isinstance(body["message"], str)


async def test_malformed_json_uses_envelope(ctx):
    client, epoch = ctx
    r = await client.post(
        "/v1/events",
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

    r = await client.post("/v1/events", json=_msg(_eid(1)), headers=_h(stale))
    assert r.status_code == 409
    assert r.json()["code"] == "SERVER_EPOCH_CHANGED"
    assert r.json()["server_epoch"] == epoch

    mailbox = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(epoch)
    )
    assert mailbox.json()["events"] == []


# ── 10. cursor beyond highest sequence ───────────────────────────────────────

async def test_cursor_beyond_highest_sequence_rejected(ctx):
    client, epoch = ctx
    r = await client.get(
        "/v1/mailboxes/bob/events", params={"after": 9999}, headers=_h(epoch)
    )
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

        await c1.post("/v1/events", json=_msg(_eid(1)), headers=_h(e1))
        mailbox2 = await c2.get(
            "/v1/mailboxes/bob/events", params={"after": 0}, headers=_h(e2)
        )
        assert mailbox2.json()["events"] == []
