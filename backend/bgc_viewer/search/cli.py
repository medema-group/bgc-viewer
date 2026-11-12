"""Query region search indexes with ``python -m bgc_viewer.search.cli``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .index import (
    RecordHit,
    Results,
    SearchError,
    SearchHit,
    Sort,
    facet_counts,
    field_values,
    open_index,
    prepare_query,
    search_record,
    search_regions,
)
from .query import build_filter_query, parse_filter_group

_CLI_LEVELS = ("region", "record")


HitFormatter = Callable[[int, Any], str]

_CLI_EXAMPLES = """\
examples (run these from the backend/ directory):

  # Build the backend indexes first
  uv run python preprocess_cli.py /path/to/data --output /tmp/bgv/attributes.db

  # Exact, multi-valued, and full-text (any text of the region) queries
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index product:terpene
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index \\
      'pfam:PF00550 AND pfam:PF00668'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'text:thioesterase'

  # antiSMASH module results and numeric ranges
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index \\
      'substrates:Leu AND knowncluster_top_similarity:[50 TO 100]'

  # Path fields match by directory, stem, or extension
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:NC_003888'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:json'

  # Path prefix: drop the extension and prefix the stem
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'output_file:"NC_003888.3"*'

  # Boolean negation, numeric ranges, and pagination
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index \\
      'Amycolatopsis NOT product:terpene'
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'product:terpene' \\
      --offset 2 --limit 2

  # Result granularity: region (default) or record
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'pfam:PF00550' \\
      --level record

  # Structured filter (the query builder's JSON), sorted, with facet counts
  uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index --filter \\
      '{"conditions": [{"field": "product_category", "operator": "in", "value": ["NRPS"]},
                       {"field": "length", "operator": "gt", "value": 40000}]}' \\
      --sort length:desc --facet product --facet organism

  # Suggested values of a field, with region counts
  uv run python -m bgc_viewer.search.cli values /tmp/bgv/tantivy.index pfam PF005
"""


def _source_label(output_file: str, input_file: str | None) -> str:
    if input_file:
        return f"{output_file}  <-  {input_file}"
    return output_file


def _score_label(score: float | None) -> str:
    return "sorted" if score is None else f"score={score:.4f}"


def _format_region_hit(position: int, hit: SearchHit) -> str:
    fields = hit.fields
    source = _source_label(fields.get("output_file", ""), fields.get("input_file"))
    location = f"[{fields.get('start', '')}:{fields.get('end', '')}]"
    return "\n".join(
        (
            f"[{position}] {_score_label(hit.score)}  {source}",
            (
                f"      record={fields.get('record', '')}  "
                f"region={fields.get('region', '')}  {location}"
            ),
            (
                f"      product={', '.join(fields.get('product', []))}  "
                f"category={', '.join(fields.get('product_category', []))}"
            ),
            f"      organism={fields.get('organism', '')}",
        )
    )


def _format_record_hit(position: int, hit: RecordHit) -> str:
    source = _source_label(hit.output_file, hit.input_file)
    return "\n".join(
        (
            f"[{position}] {_score_label(hit.score)}  {source}",
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
    print(f"showing {first}-{last}{more} of {result.total_regions} matching regions")
    for position, hit in enumerate(result.hits, start=first):
        print(format_hit(position, hit))


def _parse_sort(value: str | None) -> Sort | None:
    if not value:
        return None
    name, _, order = value.partition(":")
    return Sort(field=name, descending=order == "desc")


def _search_command(args: argparse.Namespace) -> int:
    if args.filter and args.query:
        print("error: pass either QUERY or --filter, not both", file=sys.stderr)
        return 2
    label = args.filter or " ".join(args.query)
    result: Results[Any]
    format_hit: HitFormatter
    try:
        target = open_index(Path(args.index_directory))
        if args.filter:
            query = build_filter_query(
                target, parse_filter_group(json.loads(args.filter))
            )
        else:
            query = prepare_query(target, label)
        search = search_record if args.level == "record" else search_regions
        format_hit = (
            _format_record_hit if args.level == "record" else _format_region_hit
        )
        result = search(
            target,
            query,
            offset=args.offset,
            limit=args.limit,
            sort=_parse_sort(args.sort),
        )
        facets = facet_counts(target, query, args.facet or ())
    except SearchError as error:
        print(f"error: [{error.code}] {error}", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    _print_results(result, format_hit, label, args.offset)
    for name, buckets in facets.items():
        counts = ", ".join(f"{bucket.value} ({bucket.count})" for bucket in buckets)
        print(f"facet {name}: {counts or 'no values'}")
    return 0


def _values_command(args: argparse.Namespace) -> int:
    try:
        target = open_index(Path(args.index_directory))
        values = field_values(target, args.field, args.contains, args.size)
    except SearchError as error:
        print(f"error: [{error.code}] {error}", file=sys.stderr)
        return 2
    for bucket in values:
        print(f"{bucket.count:>8}  {bucket.value}")
    if not values:
        print("no values")
    return 0


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bgc_viewer.search.cli",
        description=("Query a Tantivy region search index from Python."),
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
        nargs="*",
        metavar="QUERY",
        help=(
            "Tantivy query string. Pass it as one quoted argument or as "
            "separate tokens, which are joined with spaces."
        ),
    )
    query_parser.add_argument(
        "--filter",
        metavar="JSON",
        help="Structured filter (a FilterGroup as JSON) instead of a QUERY.",
    )
    query_parser.add_argument(
        "--sort",
        metavar="FIELD[:desc]",
        help="Order hits by a single-valued field instead of by relevance.",
    )
    query_parser.add_argument(
        "--facet",
        action="append",
        metavar="FIELD",
        help="Count the values of FIELD over all matches (repeatable).",
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
        default="region",
        help=(
            "Result granularity: region (default) reports each matching "
            "region, and record collapses matches to unique records."
        ),
    )

    values_parser = subparsers.add_parser(
        "values", help="Suggest values of a field, with region counts."
    )
    values_parser.add_argument("index_directory", metavar="INDEX_DIRECTORY")
    values_parser.add_argument("field", metavar="FIELD")
    values_parser.add_argument(
        "contains",
        nargs="?",
        default="",
        metavar="TEXT",
        help="Text the values must contain, ignoring case.",
    )
    values_parser.add_argument(
        "--size", type=int, default=20, help="Number of values (default: 20)."
    )
    return parser


def _run_cli(args: argparse.Namespace) -> int:
    if args.command == "search":
        return _search_command(args)
    if args.command == "values":
        return _values_command(args)
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for querying backend search indexes."""
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
