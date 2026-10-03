from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain import DomainError

_STATUS = {
    "INVALID_REQUEST": 422,
    "INVALID_CURSOR": 422,
    "MESSAGE_ID_CONFLICT": 409,
    "SERVER_EPOCH_CHANGED": 409,
}


def _current_epoch(request: Request) -> str | None:
    try:
        return request.app.state.store.epoch
    except Exception:
        return None


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=_STATUS.get(exc.code, 422),
        content={
            "code": exc.code,
            "message": exc.message,
            "server_epoch": _current_epoch(request),
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    msg = errors[0]["msg"] if errors else "Invalid request"
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_REQUEST",
            "message": msg,
            "server_epoch": _current_epoch(request),
        },
    )
