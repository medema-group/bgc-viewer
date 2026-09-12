"""Development CLI for building and querying protocluster search indexes.

This module is the Stage 1 manual experimentation surface over the Python API in
:mod:`bgc_viewer.search.index`. Run it with ``python -m bgc_viewer.search.cli``.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from .document import ProtoclusterSearchDocument
from .extraction import ExtractionError, extract_documents
from .index import (
    RecordHit,
    RegionHit,
    SearchError,
    SearchHit,
    build_index,
    open_index,
    search_protoclusters,
    search_record,
    search_region,
)

_CLI_LEVELS = ("protocluster", "region", "record")


class _PrintableResults(Protocol):
    """Structural view shared by the protocluster, region, and record results."""

    @property
    def query(self) -> str: ...

    @property
    def hits(self) -> tuple[Any, ...]: ...

    @property
    def total(self) -> int: ...

    @property
    def offset(self) -> int: ...

    @property
    def limit(self) -> int: ...


HitFormatter = Callable[[int, Any], str]

_CLI_EXAMPLES = """\
examples (run these from the backend/ directory):

  # Index the bundled demo antiSMASH outputs into a scratch directory
  uv run python -m bgc_viewer.search.cli build-index ../demos/data \\
      -o /tmp/bgv --file NC_003888.3.json --file Y16952.json

  # Exact, multi-valued, and analyzed (full-text) field queries
  uv run python -m bgc_viewer.search.cli search /tmp/bgv product:terpene
  uv run python -m bgc_viewer.search.cli search /tmp/bgv \\
      'pfam:PF00550 AND pfam:PF00668'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv 'pfam_name:"thioesterase"'

  # Boolean negation, numeric ranges, and pagination
  uv run python -m bgc_viewer.search.cli search /tmp/bgv \\
      'organism:Amycolatopsis NOT product:terpene'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv 'product:terpene' \\
      --offset 2 --limit 2

  # Result granularity: protocluster (default), region, or record
  uv run python -m bgc_viewer.search.cli search /tmp/bgv 'product:terpene' \\
      --level protocluster
  uv run python -m bgc_viewer.search.cli search /tmp/bgv 'product:terpene' \\
      --level region
  uv run python -m bgc_viewer.search.cli search /tmp/bgv 'pfam:PF00550' \\
      --level record
"""


def _source_label(output_file: str, input_file: str | None) -> str:
    if input_file:
        return f"{output_file}  <-  {input_file}"
    return output_file


def _format_protocluster_hit(position: int, hit: SearchHit) -> str:
    fields = hit.fields
    source = _source_label(fields.get("output_file", ""), fields.get("input_file"))
    location = f"[{fields.get('start', '')}:{fields.get('end', '')}]"
    return "\n".join(
        (
            f"[{position}] score={hit.score:.4f}  {source}",
            (
                f"      record={fields.get('record', '')}  "
                f"region={fields.get('region', '')}  "
                f"protocluster={fields.get('protocluster', '')}  {location}"
            ),
            (
                f"      product={fields.get('product', '')}  "
                f"category={fields.get('category', '')}"
            ),
            f"      organism={fields.get('organism', '')}",
        )
    )


def _format_region_hit(position: int, hit: RegionHit) -> str:
    source = _source_label(hit.output_file, hit.input_file)
    return "\n".join(
        (
            f"[{position}] score={hit.score:.4f}  {source}",
            f"      record={hit.record}  region={hit.region}",
        )
    )


def _format_record_hit(position: int, hit: RecordHit) -> str:
    source = _source_label(hit.output_file, hit.input_file)
    return "\n".join(
        (
            f"[{position}] score={hit.score:.4f}  {source}",
            f"      record={hit.record}",
        )
    )


def _print_results(result: _PrintableResults, format_hit: HitFormatter) -> None:
    print(f"query: {result.query}")
    if result.total == 0:
        print("0 total")
        return
    shown = len(result.hits)
    if shown == 0:
        print(f"{result.total} total; no hits at offset {result.offset}")
        return
    first = result.offset + 1
    last = result.offset + shown
    print(f"{result.total} total; showing {first}-{last}")
    for position, hit in enumerate(result.hits, start=first):
        print(format_hit(position, hit))


def _build_command(args: argparse.Namespace) -> int:
    source_root = Path(args.source_directory)
    if not source_root.is_dir():
        print(f"error: source directory not found: {source_root}", file=sys.stderr)
        return 1

    files = [Path(relative) for relative in args.files]
    index_dir = Path(args.index_directory)

    warnings.simplefilter("default")
    indexed = 0

    def streaming() -> Iterable[ProtoclusterSearchDocument]:
        nonlocal indexed
        for document in extract_documents(
            files, source_root, warning_threshold=args.warning_threshold
        ):
            indexed += 1
            yield document

    try:
        build_index(streaming(), index_dir)
    except ExtractionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"error: cannot write index to {index_dir}: {error}", file=sys.stderr)
        return 1

    print(f"Indexed {indexed} protocluster document(s) into {index_dir}")
    return 0


def _search_command(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    result: _PrintableResults
    format_hit: HitFormatter
    try:
        target = open_index(args.index_directory)
        if args.level == "region":
            result = search_region(target, query, offset=args.offset, limit=args.limit)
            format_hit = _format_region_hit
        elif args.level == "record":
            result = search_record(target, query, offset=args.offset, limit=args.limit)
            format_hit = _format_record_hit
        else:
            result = search_protoclusters(
                target, query, offset=args.offset, limit=args.limit
            )
            format_hit = _format_protocluster_hit
    except SearchError as error:
        print(f"error: [{error.code}] {error}", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    _print_results(result, format_hit)
    return 0


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bgc_viewer.search.cli",
        description=(
            "Build and query a Tantivy protocluster search index directly "
            "from Python (Stage 1 development CLI)."
        ),
        epilog=_CLI_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build-index", help="Build a search index from antiSMASH JSON files."
    )
    build.add_argument(
        "source_directory",
        metavar="SOURCE_DIRECTORY",
        help="Source root that selected JSON paths are resolved against.",
    )
    build.add_argument(
        "-o",
        "--index-directory",
        dest="index_directory",
        required=True,
        metavar="INDEX_DIRECTORY",
        help="Directory the Tantivy index is written to.",
    )
    build.add_argument(
        "--file",
        dest="files",
        action="append",
        required=True,
        metavar="RELATIVE_JSON",
        help=(
            "antiSMASH JSON path relative to SOURCE_DIRECTORY; repeat for "
            "multiple files. Paths outside the source root are rejected."
        ),
    )
    build.add_argument(
        "--warning-threshold",
        type=int,
        default=100,
        help=(
            "Fail the build after this many occurrences of one warning code "
            "in a single file (default: 100)."
        ),
    )

    query_parser = subparsers.add_parser(
        "search", help="Query an existing search index."
    )
    query_parser.add_argument(
        "index_directory",
        metavar="INDEX_DIRECTORY",
        help="Directory of a previously built Tantivy index.",
    )
    query_parser.add_argument(
        "query",
        nargs="+",
        metavar="QUERY",
        help=(
            "Tantivy query string. Pass it as one quoted argument or as "
            "separate tokens, which are joined with spaces."
        ),
    )
    query_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of ranked hits to skip (default: 0).",
    )
    query_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of hits to print (default: 10).",
    )
    query_parser.add_argument(
        "--level",
        choices=_CLI_LEVELS,
        default="protocluster",
        help=(
            "Result granularity: protocluster (default) reports each matching "
            "protocluster, region collapses matches to unique regions, and "
            "record collapses them to unique records."
        ),
    )
    return parser


def _run_cli(args: argparse.Namespace) -> int:
    if args.command == "build-index":
        return _build_command(args)
    if args.command == "search":
        return _search_command(args)
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the Stage 1 search development CLI."""
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
