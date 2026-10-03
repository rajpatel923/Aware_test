import re
from dataclasses import dataclass

USERNAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

INVALID_REQUEST = "INVALID_REQUEST"
MESSAGE_ID_CONFLICT = "MESSAGE_ID_CONFLICT"
SERVER_EPOCH_CHANGED = "SERVER_EPOCH_CHANGED"
INVALID_CURSOR = "INVALID_CURSOR"


class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_username(name: str) -> None:
    if not isinstance(name, str) or not USERNAME_RE.match(name):
        raise DomainError(INVALID_REQUEST, f"Invalid username: {name!r}")


def validate_text(text: str) -> None:
    if not isinstance(text, str):
        raise DomainError(INVALID_REQUEST, "text must be a string")
    try:
        b = text.encode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        raise DomainError(INVALID_REQUEST, "text contains invalid Unicode")
    if not (1 <= len(b) <= 4096):
        raise DomainError(
            INVALID_REQUEST,
            f"text must be 1–4096 UTF-8 bytes, got {len(b)}",
        )


def validate_message_id(mid: str) -> None:
    if not isinstance(mid, str) or not UUID_RE.match(mid):
        raise DomainError(INVALID_REQUEST, f"Invalid client_message_id: {mid!r}")


@dataclass(frozen=True)
class MessageRecord:
    client_message_id: str
    sender: str
    recipient: str
    text: str
    sequence: int
    accepted_at: str
    server_epoch: str
