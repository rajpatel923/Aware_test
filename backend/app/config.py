import os

HOST: str = os.environ.get("MESSAGING_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("MESSAGING_PORT", "8000"))
