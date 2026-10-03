import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue


class ClientProcess:
    def __init__(
        self,
        executable: list[str],
        base_url: str,
        data_dir: Path,
        page_size: int | None = None,
    ) -> None:
        self._executable = executable
        self._base_url = base_url
        self._data_dir = data_dir
        self._page_size = page_size
        self._proc: subprocess.Popen | None = None
        self._counter = 0
        self._queue: Queue[str] = Queue()
        self._reader: threading.Thread | None = None

    def _build_args(self) -> list[str]:
        args = list(self._executable) + ["--url", self._base_url, "--data-dir", str(self._data_dir)]
        if self._page_size is not None:
            args += ["--page-size", str(self._page_size)]
        return args

    def start(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._proc = subprocess.Popen(
            self._build_args(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc is not None
        for line in self._proc.stdout:  # type: ignore[union-attr]
            self._queue.put(line.rstrip())

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self.command("shutdown")
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def restart(self) -> None:
        self.stop()
        self._counter = 0
        self._queue = Queue()
        self._reader = None
        self.start()

    def command(self, cmd: str, args: dict | None = None, timeout: float = 15.0) -> dict:
        self._counter += 1
        req_id = str(self._counter)
        req: dict = {"id": req_id, "cmd": cmd}
        if args:
            req["args"] = args
        assert self._proc is not None, "Client not started"
        self._proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
        self._proc.stdin.flush()  # type: ignore[union-attr]

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                line = self._queue.get(timeout=max(0.01, remaining))
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == req_id:
                    return resp
            except Empty:
                continue
        raise TimeoutError(f"No response to '{cmd}' (id={req_id}) within {timeout}s")
