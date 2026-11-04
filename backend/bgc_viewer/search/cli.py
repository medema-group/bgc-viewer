"""Query protocluster search indexes with ``python -m bgc_viewer.search.cli``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .index import (
    RecordHit,
    RegionHit,
    Results,
    SearchError,
    SearchHit,
    open_index,
    search_protoclusters,
    search_record,
    search_region,
)

_CLI_LEVELS = ("protocluster", "region", "record")


HitFormatter = Callable[[int, Any], str]

_CLI_EXAMPLES = """\
examples (run these from the backend/ directory):

  # Build the backend indexes first
  uv run python preprocess_cli.py /path/to/data --output /tmp/bgv/attributes.db

  # Exact, multi-valued, and analyzed (full-text) field queries
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index product:terpene
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index \\
      'pfam:PF00550 AND pfam:PF00668'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'pfam_name:"thioesterase"'

  # Path fields match by directory, stem, or extension
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:NC_003888'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:json'

  # Path prefix: drop the extension and prefix the stem
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:"NC_003888.3"*'

  # Boolean negation, numeric ranges, and pagination
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index \\
      'organism:Amycolatopsis NOT product:terpene'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'product:terpene' \\
      --offset 2 --limit 2

  # Result granularity: protocluster (default), region, or record
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'product:terpene' \\
      --level protocluster
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'product:terpene' \\
      --level region
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'pfam:PF00550' \\
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


def _print_results(
    result: Results[Any], format_hit: HitFormatter, query: str, offset: int
) -> None:
    print(f"query: {query}")
    shown = len(result.hits)
    if shown == 0:
        print("no hits")
        return
    first = offset + 1
    last = offset + shown
    more = " (more available)" if result.has_more else ""
    print(f"showing {first}-{last}{more}")
    for position, hit in enumerate(result.hits, start=first):
        print(format_hit(position, hit))


def _search_command(args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    result: Results[Any]
    format_hit: HitFormatter
    try:
        target = open_index(Path(args.index_directory))
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

    _print_results(result, format_hit, query, args.offset)
    return 0


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bgc_viewer.search.cli",
        description=("Query a Tantivy protocluster search index from Python."),
        epilog=_CLI_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    if args.command == "search":
        return _search_command(args)
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for querying backend search indexes."""
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
