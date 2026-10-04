"""Optional live progress files, separate from the CLI's JSON result streams."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from ._render_control import RenderProgress


@contextmanager
def progress_file(path: str | None) -> Iterator[Callable[[RenderProgress], None] | None]:
    if path is None:
        yield None
        return
    stream: TextIO | None = None

    def record(event: RenderProgress) -> None:
        nonlocal stream
        if stream is None:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            stream = destination.open("w", encoding="utf-8", newline="\n")
        print(json.dumps({"event": "render_progress", **asdict(event)}), file=stream, flush=True)

    try:
        yield record
    finally:
        if stream is not None:
            stream.close()
