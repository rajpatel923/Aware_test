from datetime import datetime, timezone

from .domain import (
    DomainError,
    MessageRecord,
    INVALID_CURSOR,
    MESSAGE_ID_CONFLICT,
    SERVER_EPOCH_CHANGED,
)
from .memory_store import MemoryStore


def _utc_ms() -> str:
    dt = datetime.now(timezone.utc)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S.')}{dt.microsecond // 1000:03d}Z"


class Repository:
    def __init__(self, store: MemoryStore) -> None:
        self._s = store

    async def accept_or_replay(
        self,
        expected_epoch: str,
        client_message_id: str,
        sender: str,
        recipient: str,
        text: str,
    ) -> MessageRecord:
        s = self._s
        async with s.lock:
            if expected_epoch != s.epoch:
                raise DomainError(SERVER_EPOCH_CHANGED, "Server has restarted; fetch a new epoch")

            key = (sender, client_message_id)
            existing = s._key_map.get(key)
            if existing is not None:
                if existing.recipient == recipient and existing.text == text:
                    return existing
                raise DomainError(
                    MESSAGE_ID_CONFLICT,
                    "Message ID reused with different recipient or text",
                )

            s._sequence += 1
            seq = s._sequence
            record = MessageRecord(
                client_message_id=client_message_id,
                sender=sender,
                recipient=recipient,
                text=text,
                sequence=seq,
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
    ) -> tuple[list[MessageRecord], int, bool]:
        s = self._s
        async with s.lock:
            if expected_epoch != s.epoch:
                raise DomainError(SERVER_EPOCH_CHANGED, "Server has restarted; fetch a new epoch")
            if after > s._sequence:
                raise DomainError(INVALID_CURSOR, "Cursor exceeds the session's highest sequence")

            seqs = [seq for seq in s._mailboxes.get(recipient, []) if seq > after]
            extended = seqs[: limit + 1]
            has_more = len(extended) > limit
            page_seqs = extended[:limit]
            records = [s._by_sequence[seq] for seq in page_seqs]
            next_cursor = page_seqs[-1] if page_seqs else after

        return records, next_cursor, has_more
