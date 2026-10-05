from fastapi import APIRouter, Header, Query, Request, Response

from ..domain import INVALID_REQUEST, SUPPORTED_TYPES, DomainError
from ..service import MessagingService
from .schemas import EventOut, MailboxPageOut, MetaOut, SubmitRequest

router = APIRouter()


def _svc(request: Request) -> MessagingService:
    return request.app.state.service


def _epoch_header(x_server_epoch: str | None) -> str:
    # A3.1: epoch header required on every non-meta request
    if not x_server_epoch:
        raise DomainError(INVALID_REQUEST, "X-Server-Epoch header is required")
    return x_server_epoch


@router.get("/v1/meta", response_model=MetaOut)
async def get_meta(request: Request, response: Response) -> MetaOut:
    response.headers["Cache-Control"] = "no-store"  # A1.4
    return MetaOut(
        server_epoch=request.app.state.store.epoch,
        event_types=sorted(SUPPORTED_TYPES),
    )


@router.post("/v1/events", response_model=EventOut)
async def submit_event(
    body: SubmitRequest,
    request: Request,
    response: Response,
    x_server_epoch: str | None = Header(default=None),
) -> EventOut:
    epoch = _epoch_header(x_server_epoch)
    response.headers["Cache-Control"] = "no-store"  # A1.4
    record = await _svc(request).submit(
        expected_epoch=epoch,
        event_id=body.event_id,
        event_type=body.type,
        sender=body.sender,
        recipient=body.recipient,
        body=body.body,
    )
    return EventOut(
        event_id=record.event_id,
        type=record.type,
        sender=record.sender,
        recipient=record.recipient,
        body=record.body,
        seq=record.seq,
        accepted_at=record.accepted_at,
        server_epoch=record.server_epoch,
    )


@router.get("/v1/mailboxes/{username}/events", response_model=MailboxPageOut)
async def get_mailbox_events(
    username: str,
    request: Request,
    response: Response,
    x_server_epoch: str | None = Header(default=None),
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> MailboxPageOut:
    epoch = _epoch_header(x_server_epoch)
    response.headers["Cache-Control"] = "no-store"  # A1.4
    records, next_cursor, has_more = await _svc(request).inbox(
        expected_epoch=epoch,
        recipient=username,
        after=after,
        limit=limit,
    )
    return MailboxPageOut(
        server_epoch=request.app.state.store.epoch,
        events=[
            EventOut(
                event_id=r.event_id,
                type=r.type,
                sender=r.sender,
                recipient=r.recipient,
                body=r.body,
                seq=r.seq,
                accepted_at=r.accepted_at,
                server_epoch=r.server_epoch,
            )
            for r in records
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )
