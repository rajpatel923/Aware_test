from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api.errors import domain_error_handler, validation_error_handler
from .api.routes import router
from .domain import DomainError
from .memory_store import MemoryStore
from .repository import Repository
from .service import MessagingService

_MAX_BODY = 16_384  # A1.5: 16 KiB


def create_app(epoch: str | None = None) -> FastAPI:
    store = MemoryStore(epoch=epoch)
    repo = Repository(store)
    service = MessagingService(repo)

    application = FastAPI(title="Local Messaging", version="1", docs_url=None, redoc_url=None)
    application.state.store = store
    application.state.service = service

    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.include_router(router)

    @application.middleware("http")
    async def limit_body_size(request: Request, call_next):
        # A1.5: reject bodies over 16 KiB before parsing
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > _MAX_BODY:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "code": "INVALID_REQUEST",
                            "message": "Request body exceeds 16 KiB limit",
                            "server_epoch": store.epoch,
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)

    return application


app = create_app()
