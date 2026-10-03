from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .api.errors import domain_error_handler, validation_error_handler
from .api.routes import router
from .domain import DomainError
from .memory_store import MemoryStore
from .repository import Repository
from .service import MessagingService


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

    return application


app = create_app()
