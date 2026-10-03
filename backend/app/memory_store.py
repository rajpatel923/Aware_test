import asyncio
import secrets

from .domain import MessageRecord


class MemoryStore:
    def __init__(self, epoch: str | None = None) -> None:
        self.epoch: str = epoch if epoch is not None else secrets.token_hex(16)
        self._sequence: int = 0
        self._key_map: dict[tuple[str, str], MessageRecord] = {}
        self._by_sequence: dict[int, MessageRecord] = {}
        self._mailboxes: dict[str, list[int]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def highest_sequence(self) -> int:
        return self._sequence
