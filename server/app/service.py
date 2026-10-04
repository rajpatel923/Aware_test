from .domain import (
    SUPPORTED_TYPES,
    UNSUPPORTED_TYPE,
    DomainError,
    EventRecord,
    validate_event_id,
    validate_message_text_body,
    validate_username,
)
from .repository import Repository


class MessagingService:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    async def submit(
        self,
        expected_epoch: str,
        event_id: str,
        event_type: str,
        sender: str,
        recipient: str,
        body: dict,
    ) -> EventRecord:
        # A3.3 validation order (steps 2–6; step 1 is done in the route handler):
        # Step 2: field formats
        validate_event_id(event_id)
        validate_username(sender)
        validate_username(recipient)
        # Step 3: epoch match (checked atomically in repository, but fast-fail here too)
        if expected_epoch != self._repo.current_epoch:
            from .domain import SERVER_EPOCH_CHANGED
            raise DomainError(SERVER_EPOCH_CHANGED, "Server has restarted; fetch a new epoch")
        # Step 4: type must be supported
        if event_type not in SUPPORTED_TYPES:
            raise DomainError(UNSUPPORTED_TYPE, f"Unsupported event type: {event_type!r}")
        # Step 5: body valid for its type
        if event_type == "message.text":
            validate_message_text_body(body)
        # Step 6: idempotency/conflict check inside the lock
        return await self._repo.accept_or_replay(
            expected_epoch, event_id, event_type, sender, recipient, body
        )

    async def inbox(
        self,
        expected_epoch: str,
        recipient: str,
        after: int,
        limit: int,
    ) -> tuple:
        validate_username(recipient)
        return await self._repo.read_inbox(expected_epoch, recipient, after, limit)
