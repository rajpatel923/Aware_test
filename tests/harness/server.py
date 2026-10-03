import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).parent.parent.parent / "backend"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerProcess:
    def __init__(self, port: int | None = None) -> None:
        self._port = port or _free_port()
        self._proc: subprocess.Popen | None = None
        self._epoch: str | None = None

    def start(self) -> None:
        venv_python = BACKEND_DIR / ".venv" / "bin" / "python"
        python = str(venv_python) if venv_python.exists() else sys.executable
        self._proc = subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app",
             "--port", str(self._port), "--log-level", "error"],
            cwd=BACKEND_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(f"{self.base_url}/v1/meta", timeout=1.0)
                self._epoch = resp.json()["server_epoch"]
                return
            except Exception:
                time.sleep(0.05)
        raise RuntimeError(f"Server on port {self._port} did not start within 15 s")

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            self._epoch = None

    def restart(self) -> None:
        self.stop()
        self.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def epoch(self) -> str:
        if self._epoch is None:
            raise RuntimeError("Server not started")
        return self._epoch
