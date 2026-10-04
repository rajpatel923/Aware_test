import re
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

_USERNAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # A1.6: reject unknown envelope fields

    event_id: str
    type: str
    sender: str
    recipient: str
    body: dict[str, Any]

    @field_validator("event_id")
    @classmethod
    def _valid_event_id(cls, v: str) -> str:
        if not _UUID_RE.match(v):
            raise ValueError("event_id must be a lowercase UUID string")
        return v

    @field_validator("type")
    @classmethod
    def _valid_type_format(cls, v: str) -> str:
        if not _TYPE_RE.match(v):
            raise ValueError("type must match [a-z][a-z0-9_]*.[a-z][a-z0-9_]*")
        return v

    @field_validator("sender", "recipient")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("username must match [a-z0-9_]{1,32}")
        return v


class EventOut(BaseModel):
    event_id: str
    type: str
    sender: str
    recipient: str
    body: dict[str, Any]
    seq: int
    accepted_at: str
    server_epoch: str


class MailboxPageOut(BaseModel):
    server_epoch: str
    events: list[EventOut]
    next_cursor: int
    has_more: bool


class MetaOut(BaseModel):
    protocol_version: int = 1
    server_epoch: str
    event_types: list[str]
