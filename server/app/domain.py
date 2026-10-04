import re
from dataclasses import dataclass, field

USERNAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# A4 error codes
INVALID_REQUEST = "INVALID_REQUEST"
EVENT_ID_CONFLICT = "EVENT_ID_CONFLICT"
SERVER_EPOCH_CHANGED = "SERVER_EPOCH_CHANGED"
INVALID_CURSOR = "INVALID_CURSOR"
UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
INTERNAL_ERROR = "INTERNAL_ERROR"

# P3.1 — registered event types for v1
SUPPORTED_TYPES: frozenset[str] = frozenset({"message.text"})


class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_username(name: str) -> None:
    if not isinstance(name, str) or not USERNAME_RE.match(name):
        raise DomainError(INVALID_REQUEST, f"Invalid username: {name!r}")


def validate_event_id(eid: str) -> None:
    if not isinstance(eid, str) or not UUID_RE.match(eid):
        raise DomainError(INVALID_REQUEST, f"Invalid event_id: {eid!r}")


def validate_text(text: str) -> None:
    # D4.1: 1–4096 UTF-8 bytes; lone surrogates are invalid
    if not isinstance(text, str):
        raise DomainError(INVALID_REQUEST, "text must be a string")
    try:
        b = text.encode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        raise DomainError(INVALID_REQUEST, "text contains invalid Unicode")
    if not (1 <= len(b) <= 4096):
        raise DomainError(INVALID_REQUEST, f"text must be 1–4096 UTF-8 bytes, got {len(b)}")


def validate_message_text_body(body: dict) -> None:
    # A1.6: reject unknown fields in bodies of known types
    if not isinstance(body, dict):
        raise DomainError(INVALID_REQUEST, "body must be a JSON object")
    unknown = set(body.keys()) - {"text"}
    if unknown:
        raise DomainError(INVALID_REQUEST, f"Unknown fields in body: {sorted(unknown)}")
    if "text" not in body:
        raise DomainError(INVALID_REQUEST, "body.text is required for message.text")
    validate_text(body["text"])


@dataclass
class EventRecord:
    event_id: str
    type: str
    sender: str
    recipient: str
    body: dict = field(compare=False)  # compared field-by-field in conflict check
    seq: int = 0
    accepted_at: str = ""
    server_epoch: str = ""

    def envelope_matches(self, other: "EventRecord") -> bool:
        # P6.1: exact retry — same key, same immutable payload
        return (
            self.type == other.type
            and self.recipient == other.recipient
            and self.body == other.body
        )
