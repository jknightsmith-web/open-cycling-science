"""Run the local server: `uv run python -m backend.api`. Binds to 127.0.0.1 only (spec 8.5)."""
from __future__ import annotations

import os

import uvicorn

from ..library import Library
from .app import create_app

HOST = "127.0.0.1"


def main() -> None:
    port = int(os.environ.get("OCS_PORT", "8765"))
    uvicorn.run(create_app(Library.open()), host=HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
