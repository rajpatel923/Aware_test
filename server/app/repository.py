from datetime import datetime, timezone

from .domain import (
    EVENT_ID_CONFLICT,
    INVALID_CURSOR,
    SERVER_EPOCH_CHANGED,
    DomainError,
    EventRecord,
)
from .memory_store import MemoryStore


def _utc_ms() -> str:
    dt = datetime.now(timezone.utc)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S.')}{dt.microsecond // 1000:03d}Z"


class Repository:
    def __init__(self, store: MemoryStore) -> None:
        self._s = store

    @property
    def current_epoch(self) -> str:
        return self._s.epoch

    async def accept_or_replay(
        self,
        expected_epoch: str,
        event_id: str,
        event_type: str,
        sender: str,
        recipient: str,
        body: dict,
    ) -> EventRecord:
        s = self._s
        async with s.lock:
            # Step 3 (authoritative, under lock): A3.3
            if expected_epoch != s.epoch:
                raise DomainError(SERVER_EPOCH_CHANGED, "Server has restarted; fetch a new epoch")

            key = (sender, event_id)
            existing = s._key_map.get(key)

            if existing is not None:
                # P6.1: exact replay returns original record
                candidate = EventRecord(
                    event_id=event_id,
                    type=event_type,
                    sender=sender,
                    recipient=recipient,
                    body=body,
                )
                if existing.envelope_matches(candidate):
                    return existing
                raise DomainError(
                    EVENT_ID_CONFLICT,
                    "Event ID reused with different recipient, type, or body",
                )

            s._sequence += 1
            seq = s._sequence
            record = EventRecord(
                event_id=event_id,
                type=event_type,
                sender=sender,
                recipient=recipient,
                body=body,
                seq=seq,
                accepted_at=_utc_ms(),
                server_epoch=s.epoch,
            )
            s._key_map[key] = record
            s._by_sequence[seq] = record
            s._mailboxes.setdefault(recipient, []).append(seq)

        return record

    async def read_inbox(
        self,
        expected_epoch: str,
        recipient: str,
        after: int,
        limit: int,
    ) -> tuple[list[EventRecord], int, bool]:
        s = self._s
        async with s.lock:
            if expected_epoch != s.epoch:
                raise DomainError(SERVER_EPOCH_CHANGED, "Server has restarted; fetch a new epoch")

            # A3.6: after must not exceed the session's highest seq
            if after > s._sequence:
                raise DomainError(INVALID_CURSOR, "Cursor exceeds the session's highest sequence")

            seqs = [sq for sq in s._mailboxes.get(recipient, []) if sq > after]
            # Fetch one extra to determine has_more (A3.5)
            extended = seqs[: limit + 1]
            has_more = len(extended) > limit
            page_seqs = extended[:limit]
            records = [s._by_sequence[sq] for sq in page_seqs]
            next_cursor = page_seqs[-1] if page_seqs else after

        return records, next_cursor, has_more
