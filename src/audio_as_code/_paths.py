"""Shared, read-only path checks before CLI and Python exports write artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def check_paths(
    paths: Sequence[str | Path],
    directories: Sequence[str | Path] = (),
    *,
    conflict_message: str = "score input, output, report, and stem paths must be distinct",
) -> None:
    """Reject known conflicts without creating files or output directories.

    These checks do not reserve paths or guarantee later filesystem writes succeed.
    """
    resolved = [Path(path).resolve() for path in paths]
    for index, path in enumerate(resolved):
        if path.is_dir():
            raise ValueError(f"expected a file path, got a directory: {path}")
        for other in resolved[:index]:
            if path == other or (path.exists() and other.exists() and path.samefile(other)):
                raise ValueError(conflict_message)
            if path in other.parents or other in path.parents:
                raise ValueError("a file path cannot also be an output directory")
    for directory in [
        *(path.parent for path in resolved),
        *(Path(path).resolve() for path in directories),
    ]:
        if directory in resolved:
            raise ValueError("a file path cannot also be an output directory")
        for parent in [directory, *directory.parents]:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"output directory is blocked by an existing file: {parent}")
