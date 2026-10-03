from fastapi import APIRouter, Header, Query, Request, Response

from ..domain import DomainError, INVALID_REQUEST
from ..service import MessagingService
from .schemas import AcceptedMessageOut, InboxPageOut, MetaOut, SubmitRequest

router = APIRouter()


def _svc(request: Request) -> MessagingService:
    return request.app.state.service


def _epoch_header(x_server_epoch: str | None) -> str:
    if not x_server_epoch:
        raise DomainError(INVALID_REQUEST, "X-Server-Epoch header is required and must not be empty")
    return x_server_epoch


@router.get("/v1/meta", response_model=MetaOut)
async def get_meta(request: Request) -> MetaOut:
    return MetaOut(server_epoch=request.app.state.store.epoch)


@router.post("/v1/messages", response_model=AcceptedMessageOut)
async def submit_message(
    body: SubmitRequest,
    request: Request,
    x_server_epoch: str | None = Header(default=None),
) -> AcceptedMessageOut:
    epoch = _epoch_header(x_server_epoch)
    record = await _svc(request).submit(
        expected_epoch=epoch,
        client_message_id=body.client_message_id,
        sender=body.sender,
        recipient=body.recipient,
        text=body.text,
    )
    return AcceptedMessageOut(**vars(record))


@router.get("/v1/inbox/{username}", response_model=InboxPageOut)
async def get_inbox(
    username: str,
    request: Request,
    response: Response,
    x_server_epoch: str | None = Header(default=None),
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> InboxPageOut:
    epoch = _epoch_header(x_server_epoch)
    records, next_cursor, has_more = await _svc(request).inbox(
        expected_epoch=epoch,
        recipient=username,
        after=after,
        limit=limit,
    )
    response.headers["Cache-Control"] = "no-store"
    return InboxPageOut(
        server_epoch=request.app.state.store.epoch,
        messages=[AcceptedMessageOut(**vars(r)) for r in records],
        next_cursor=next_cursor,
        has_more=has_more,
    )
