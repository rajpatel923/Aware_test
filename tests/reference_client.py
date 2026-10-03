#!/usr/bin/env python3
"""
Reference headless client (Python, V01 harness self-testing only).
Implements the full JSON Lines runner protocol against the real server.
Usage: python reference_client.py --url http://127.0.0.1:PORT --data-dir DIR [--page-size N]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import httpx

_USERNAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")


class _RefClient:
    def __init__(self, base_url: str, data_dir: Path, page_size: int = 100) -> None:
        self._url = base_url.rstrip("/")
        self._data_dir = data_dir
        self._page_size = page_size
        self._offline = False
        self._fault_drop_next: str | None = None
        self._db = self._open_db()
        self._username: str | None = self._load("username")
        self._server_epoch: str | None = self._load("server_epoch")
        self._pending_epoch: str | None = self._load("pending_epoch")
        self._cursor: int = int(self._load("cursor") or "0")

    # ── persistence ──────────────────────────────────────────────────────────

    def _open_db(self) -> sqlite3.Connection:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self._data_dir / "messages.db"), check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                client_message_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                sequence INTEGER,
                error_code TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.commit()
        return db

    def _load(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _save(self, key: str, value: str | None) -> None:
        if value is None:
            self._db.execute("DELETE FROM state WHERE key=?", (key,))
        else:
            self._db.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, value))
        self._db.commit()

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _http(self) -> httpx.Client:
        return httpx.Client(base_url=self._url, timeout=10.0)

    def _epoch_header(self) -> dict[str, str]:
        if not self._server_epoch:
            raise RuntimeError("No server epoch — call sync_once first")
        return {"X-Server-Epoch": self._server_epoch}

    # ── commands ─────────────────────────────────────────────────────────────

    def identify(self, name: str) -> dict:
        canonical = name.lower()
        if not _USERNAME_RE.match(canonical):
            raise ValueError(f"Invalid username: {name!r}")
        self._username = canonical
        self._save("username", canonical)
        return {"username": canonical}

    def send(self, recipient: str, text: str) -> dict:
        mid = str(uuid.uuid4())
        self._db.execute(
            "INSERT INTO messages (client_message_id,sender,recipient,text,status) VALUES (?,?,?,?,'queued')",
            (mid, self._username, recipient, text),
        )
        self._db.commit()
        return {"client_message_id": mid, "status": "queued"}

    def offline(self, enabled: bool) -> dict:
        self._offline = enabled
        return {"offline": enabled}

    def fault(self, drop_next_response: str) -> dict:
        self._fault_drop_next = drop_next_response
        return {"armed": True}

    def sync_once(self) -> dict:
        if self._offline:
            return {
                "outcome": "paused",
                "accepted": 0,
                "received": 0,
                "pending": self._pending_count(),
            }

        if not self._server_epoch:
            try:
                with self._http() as h:
                    r = h.get("/v1/meta")
                    r.raise_for_status()
                    self._server_epoch = r.json()["server_epoch"]
                    self._save("server_epoch", self._server_epoch)
            except Exception:
                return {"outcome": "backoff", "accepted": 0, "received": 0, "pending": self._pending_count()}

        accepted = 0

        pending = self._db.execute(
            "SELECT client_message_id,sender,recipient,text FROM messages WHERE status='queued'"
            " ORDER BY rowid"
        ).fetchall()

        for mid, sender, recipient, text in pending:
            payload = {
                "client_message_id": mid,
                "sender": sender,
                "recipient": recipient,
                "text": text,
            }
            try:
                with self._http() as h:
                    resp = h.post("/v1/messages", json=payload, headers=self._epoch_header())

                if self._fault_drop_next == "submit":
                    self._fault_drop_next = None
                    raise httpx.TimeoutException("fault: dropped submit response")

                if resp.status_code == 409:
                    err = resp.json()
                    if err["code"] == "SERVER_EPOCH_CHANGED":
                        new_epoch = err["server_epoch"]
                        self._pending_epoch = new_epoch
                        self._save("pending_epoch", new_epoch)
                        return {
                            "outcome": "server_reset",
                            "accepted": accepted,
                            "received": 0,
                            "pending": self._pending_count(),
                        }
                    self._db.execute(
                        "UPDATE messages SET status='failed',error_code=? WHERE client_message_id=?",
                        (err["code"], mid),
                    )
                    self._db.commit()
                    continue

                resp.raise_for_status()
                data = resp.json()
                self._db.execute(
                    "UPDATE messages SET status='accepted',sequence=? WHERE client_message_id=?",
                    (data["sequence"], mid),
                )
                self._db.commit()
                accepted += 1

            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError):
                return {
                    "outcome": "backoff",
                    "accepted": accepted,
                    "received": 0,
                    "pending": self._pending_count(),
                }

        # fetch inbox
        received = 0
        while True:
            try:
                with self._http() as h:
                    resp = h.get(
                        f"/v1/inbox/{self._username}",
                        params={"after": self._cursor, "limit": self._page_size},
                        headers=self._epoch_header(),
                    )

                if self._fault_drop_next == "inbox":
                    self._fault_drop_next = None
                    raise httpx.TimeoutException("fault: dropped inbox response")

                if resp.status_code == 409:
                    err = resp.json()
                    if err["code"] == "SERVER_EPOCH_CHANGED":
                        new_epoch = err["server_epoch"]
                        self._pending_epoch = new_epoch
                        self._save("pending_epoch", new_epoch)
                        return {
                            "outcome": "server_reset",
                            "accepted": accepted,
                            "received": received,
                            "pending": self._pending_count(),
                        }

                resp.raise_for_status()
                data = resp.json()

                for msg in data["messages"]:
                    exists = self._db.execute(
                        "SELECT 1 FROM messages WHERE client_message_id=?",
                        (msg["client_message_id"],),
                    ).fetchone()
                    if not exists:
                        self._db.execute(
                            "INSERT OR IGNORE INTO messages "
                            "(client_message_id,sender,recipient,text,status,sequence) "
                            "VALUES (?,?,?,?,'accepted',?)",
                            (
                                msg["client_message_id"],
                                msg["sender"],
                                msg["recipient"],
                                msg["text"],
                                msg["sequence"],
                            ),
                        )
                        self._db.commit()
                        received += 1

                if data["messages"]:
                    self._cursor = data["next_cursor"]
                    self._save("cursor", str(self._cursor))

                if not data["has_more"]:
                    break

            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError):
                return {
                    "outcome": "backoff",
                    "accepted": accepted,
                    "received": received,
                    "pending": self._pending_count(),
                }

        return {
            "outcome": "ok",
            "accepted": accepted,
            "received": received,
            "pending": self._pending_count(),
        }

    def snapshot(self, peer: str | None = None) -> dict:
        if peer:
            rows = self._db.execute(
                "SELECT client_message_id,sender,recipient,text,status,sequence,error_code"
                " FROM messages WHERE sender=? OR recipient=?"
                " ORDER BY COALESCE(sequence,9999999),rowid",
                (peer, peer),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT client_message_id,sender,recipient,text,status,sequence,error_code"
                " FROM messages ORDER BY COALESCE(sequence,9999999),rowid"
            ).fetchall()

        messages = [
            {
                "client_message_id": r[0],
                "sender": r[1],
                "recipient": r[2],
                "text": r[3],
                "status": r[4],
                "sequence": r[5],
                "error_code": r[6],
            }
            for r in rows
        ]
        return {
            "username": self._username,
            "server_epoch": self._server_epoch,
            "cursor": self._cursor,
            "sync_state": "offline" if self._offline else "online",
            "pending_count": self._pending_count(),
            "messages": messages,
        }

    def reset_session(self) -> dict:
        if self._pending_epoch:
            new_epoch = self._pending_epoch
        else:
            with self._http() as h:
                r = h.get("/v1/meta")
                r.raise_for_status()
                new_epoch = r.json()["server_epoch"]
        self._server_epoch = new_epoch
        self._pending_epoch = None
        self._cursor = 0
        self._save("server_epoch", new_epoch)
        self._save("pending_epoch", None)
        self._save("cursor", "0")
        return {"server_epoch": new_epoch, "cursor": 0}

    def shutdown(self) -> dict:
        self._db.close()
        return {}

    def _pending_count(self) -> int:
        return self._db.execute(
            "SELECT COUNT(*) FROM messages WHERE status='queued'"
        ).fetchone()[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    client = _RefClient(args.url, Path(args.data_dir), args.page_size)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"id": "?", "ok": False, "error": {"code": "PARSE_ERROR", "message": str(e)}}), flush=True)
            continue

        req_id = req.get("id", "?")
        cmd = req.get("cmd", "")
        a = req.get("args") or {}

        try:
            if cmd == "identify":
                result = client.identify(a["name"])
            elif cmd == "send":
                result = client.send(a["recipient"], a["text"])
            elif cmd == "offline":
                result = client.offline(a["enabled"])
            elif cmd == "fault":
                result = client.fault(a["drop_next_response"])
            elif cmd == "sync_once":
                result = client.sync_once()
            elif cmd == "snapshot":
                result = client.snapshot(a.get("peer"))
            elif cmd == "reset_session":
                result = client.reset_session()
            elif cmd == "shutdown":
                result = client.shutdown()
                print(json.dumps({"id": req_id, "ok": True, "result": result}), flush=True)
                break
            else:
                raise ValueError(f"Unknown command: {cmd!r}")
            print(json.dumps({"id": req_id, "ok": True, "result": result}), flush=True)
        except Exception as exc:
            print(
                json.dumps({"id": req_id, "ok": False, "error": {"code": "CLIENT_ERROR", "message": str(exc)}}),
                flush=True,
            )


if __name__ == "__main__":
    main()
