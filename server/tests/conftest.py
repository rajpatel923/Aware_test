import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def ctx():
    """Yields (client, epoch) for a fresh server instance."""
    application = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        resp = await client.get("/v1/meta")
        assert resp.status_code == 200
        epoch = resp.json()["server_epoch"]
        yield client, epoch
