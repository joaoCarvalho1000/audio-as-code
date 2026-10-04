"""Cooperative render checkpoints and staged file publication."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderProgress:
    """Stage-local work counts, not a wall-clock percentage or time estimate."""

    phase: str
    completed: int
    total: int
    track: str | None = None


class RenderCancelled(ValueError):
    """The caller requested cancellation at a cooperative checkpoint."""


ProgressCallback = Callable[[RenderProgress], None]
CancelCallback = Callable[[], bool]


@dataclass
class _RenderControl:
    progress: ProgressCallback | None = None
    cancel: CancelCallback | None = None

    def check(self) -> None:
        if self.cancel is not None and self.cancel():
            raise RenderCancelled("render cancelled")

    def notify(self, phase: str, completed: int, total: int, track: str | None = None) -> None:
        self.check()
        if self.progress is not None:
            self.progress(RenderProgress(phase, completed, total, track))
        self.check()


@contextmanager
def _staged_outputs(paths: Sequence[Path]) -> Iterator[list[Path]]:
    """Prepare all files before replacement; each replace is atomic, not the set.

    Cancellation/callback/synthesis/encoding failures leave destinations intact.
    A filesystem failure during the final replacement loop may publish a subset.
    """
    staged: list[Path] = []
    try:
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix=".aac-", suffix=".wav", dir=path.parent, delete=False
            ) as stream:
                staged.append(Path(stream.name))
        yield staged
        for temporary, destination in zip(staged, paths, strict=True):
            os.replace(temporary, destination)
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
