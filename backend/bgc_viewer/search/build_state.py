"""Build-state signaling for the delete-in-place preprocessing rebuild.

A preprocessing run deletes the previous database and ``tantivy.index/`` before
building the new pair, so every request landing inside that window reaches a
half-written or absent index. The ``.building`` sentinel written into the
preprocessing output directory makes that window visible to readers instead of
letting it surface as a misleading ``missing_index``. A build wraps itself in
:func:`building`, which writes the marker on entry and removes it only when
the block completes cleanly.

Two distinct states matter and must not collapse into one:

* A build that is live in this process is retryable: the caller should wait.
* A sentinel with no build running in this process means the previous run was
  interrupted by a kill, a crash, or a power loss. Nothing is coming to clear
  it, so it is reported as a distinct non-retryable error and is never removed
  automatically: clearing it would make an inconsistent pair look valid.

Liveness is decided by the caller's in-process flag, never by the sentinel
itself. The sentinel carries a timestamp for human diagnostics only; a
multi-process deployment would need a live process identity or heartbeat in
here, which is out of scope.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Callable, Iterator

from .index import SearchError

#: Name of the sentinel file marking an output directory as mid-build.
SENTINEL_NAME = ".building"


class IndexRebuildingError(SearchError):
    """A search arrived while this process is rebuilding the index.

    Retryable: the build is running and the index will be usable when it ends.
    """

    code = "index_rebuilding"

    def __init__(self) -> None:
        super().__init__(
            "The search index is being rebuilt. Retry after preprocessing finishes."
        )


class IndexInterruptedError(SearchError):
    """The build sentinel survived with no build running in this process.

    Not retryable: the previous run died mid-build, so the database and index
    on disk are not a trustworthy pair. Rerunning preprocessing is the
    recovery procedure.
    """

    code = "index_interrupted"

    def __init__(self, output_dir: str | PathLike[str] | None = None) -> None:
        message = (
            "The previous preprocessing run was interrupted. "
            "Rerun preprocessing to rebuild the search index."
        )
        if output_dir is not None:
            message = f"{message} Stale sentinel: {sentinel_path(output_dir)}"
        super().__init__(message)


def sentinel_path(output_dir: str | PathLike[str]) -> Path:
    """Return the sentinel file path for a preprocessing output directory."""
    return Path(output_dir) / SENTINEL_NAME


def mark_building(output_dir: str | PathLike[str]) -> Path:
    """Mark an output directory as having a preprocessing run in progress."""
    path = sentinel_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return path


def clear_building(output_dir: str | PathLike[str]) -> None:
    """Remove the sentinel after a build completes; a no-op when absent."""
    try:
        sentinel_path(output_dir).unlink()
    except FileNotFoundError:
        pass


def is_building(output_dir: str | PathLike[str]) -> bool:
    """Whether a sentinel is present, regardless of any build being live."""
    return sentinel_path(output_dir).exists()


@contextmanager
def building(output_dir: str | PathLike[str]) -> Iterator[Path]:
    """Mark ``output_dir`` as building for the duration of the block.

    Yields the sentinel path. The sentinel is removed only when the block
    returns normally: there is deliberately no ``finally`` cleanup, because a
    run that raises, and a run killed outright, must both leave the marker
    behind so readers report the half-built pair as interrupted rather than
    serving or hiding it.

    The block is the whole build. Nesting is not supported: an inner block
    finishing would clear the marker the outer build still depends on.
    """
    path = mark_building(output_dir)
    yield path
    clear_building(output_dir)


def guard_build_state(
    output_dir: str | PathLike[str], *, build_is_live: Callable[[], bool]
) -> None:
    """Raise the error matching the current build state, or return ``None``.

    The in-process flag is consulted first so a request arriving after a run
    was accepted but before its worker thread created the sentinel is still
    reported as rebuilding. Only when no build is live does a present sentinel
    mean the previous run was interrupted.
    """
    if build_is_live():
        raise IndexRebuildingError()
    if is_building(output_dir):
        raise IndexInterruptedError(output_dir)
