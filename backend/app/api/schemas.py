import re

from pydantic import BaseModel, ConfigDict, field_validator

_USERNAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_message_id: str
    sender: str
    recipient: str
    text: str

    @field_validator("client_message_id")
    @classmethod
    def _valid_mid(cls, v: str) -> str:
        if not _UUID_RE.match(v):
            raise ValueError("Invalid client_message_id")
        return v

    @field_validator("sender", "recipient")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("Invalid username")
        return v

    @field_validator("text")
    @classmethod
    def _valid_text(cls, v: str) -> str:
        try:
            b = v.encode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            raise ValueError("Text contains invalid Unicode")
        if not (1 <= len(b) <= 4096):
            raise ValueError(f"Text must be 1–4096 UTF-8 bytes, got {len(b)}")
        return v


class AcceptedMessageOut(BaseModel):
    client_message_id: str
    sender: str
    recipient: str
    text: str
    sequence: int
    accepted_at: str
    server_epoch: str


class InboxPageOut(BaseModel):
    server_epoch: str
    messages: list[AcceptedMessageOut]
    next_cursor: int
    has_more: bool


class MetaOut(BaseModel):
    protocol_version: str = "1"
    server_epoch: str


class ErrorOut(BaseModel):
    code: str
    message: str
    server_epoch: str | None = None
