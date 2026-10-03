from .domain import MessageRecord, validate_message_id, validate_text, validate_username
from .repository import Repository


class MessagingService:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    async def submit(
        self,
        expected_epoch: str,
        client_message_id: str,
        sender: str,
        recipient: str,
        text: str,
    ) -> MessageRecord:
        validate_message_id(client_message_id)
        validate_username(sender)
        validate_username(recipient)
        validate_text(text)
        return await self._repo.accept_or_replay(
            expected_epoch, client_message_id, sender, recipient, text
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
