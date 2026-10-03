"""Shared fixtures for V01 harness tests."""
import sys
from pathlib import Path

import pytest

# Make the tests/ directory importable as a package root regardless of CWD.
_tests_dir = str(Path(__file__).parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from harness import ClientProcess, ServerProcess

TESTS_DIR = Path(__file__).parent
REF_CLIENT = [sys.executable, str(TESTS_DIR / "reference_client.py")]


@pytest.fixture
def server(tmp_path):
    """Start a fresh server process; yield it; stop it."""
    s = ServerProcess()
    s.start()
    yield s
    s.stop()


@pytest.fixture
def make_client(server, tmp_path):
    """Factory: make_client("alice") → ClientProcess in its own data dir."""
    created: list[ClientProcess] = []

    def _make(name: str, page_size: int | None = None) -> ClientProcess:
        c = ClientProcess(
            executable=REF_CLIENT,
            base_url=server.base_url,
            data_dir=tmp_path / name,
            page_size=page_size,
        )
        c.start()
        created.append(c)
        return c

    yield _make

    for c in created:
        c.stop()
