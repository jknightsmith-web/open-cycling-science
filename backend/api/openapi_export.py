"""Write the API's OpenAPI schema to a file, for generating the frontend's TypeScript types."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from ..library import Library
from .app import create_app


def main(out: str) -> None:
    with tempfile.TemporaryDirectory() as root:
        schema = create_app(Library(Path(root))).openapi()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
