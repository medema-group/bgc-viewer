# Search Index

Protocluster search runs on an embedded [Tantivy](https://github.com/quickwit-oss/tantivy) index built from antiSMASH JSON output and queried through Tantivy's native query language.

SQLite stays authoritative for files, records, byte offsets, and metadata. The search index is a derived artifact: local, disposable, and rebuilt from the source JSON whenever the database is rebuilt. There is no external search service.

One Tantivy document is one protocluster. Every clause of a query such as:

```text
pfam:PF00512 AND pfam:PF00513
```

must match inside the same protocluster document.

## Where things live

| Concern | Path |
| --- | --- |
| Field registry, schema version, canonical document | `backend/bgc_viewer/search/document.py` |
| Index build, open, search | `backend/bgc_viewer/search/index.py` |
| antiSMASH adapters and extraction | `backend/bgc_viewer/search/extraction.py` |
| Build sentinel and rebuild signaling | `backend/bgc_viewer/search/build_state.py` |
| HTTP request/response contract | `backend/bgc_viewer/search/api.py` |
| Development CLI | `backend/bgc_viewer/search/cli.py` |
| Preprocessing integration | `backend/bgc_viewer/preprocessing.py` |
| Search tests | `backend/bgc_viewer/tests/search/` |
| antiSMASH fixtures | `backend/bgc_viewer/tests/search/fixtures/` |

The field registry in
[`backend/bgc_viewer/search/document.py`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/document.py)
is the single source of truth for which public fields exist, how each one is
analyzed, and how each one is boosted. This page deliberately does not
reproduce that list. To see the fields and their descriptions:

- read
  [`SEARCH_FIELD_REGISTRY`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/document.py), or
- ask a running backend for
  [`GET /api/search/schema`](/api/search), which serves each field's public
  name, kind, description, and whether an unqualified term searches it.

## Query language

Tantivy's native `QueryParser` language is the public query contract. The
`tantivy` Python package is pinned to an exact version, and the project queries
are regression-tested when it is upgraded.

### Boolean operators and precedence

`AND`, `OR`, and `NOT` work with normal Boolean precedence, and parentheses
group as expected:

```text
(pfam:PF00512 OR pfam:PF00513) AND organism:Amycolatopsis
organism:Amycolatopsis NOT pfam:PF00513
pfam:PF00512 AND pfam:PF00513 AND NOT category:PKS
```

Whitespace between terms means an implicit `OR`, which is Tantivy's default.
A query made only of excluded terms is rejected, as Tantivy rejects it:

```text
NOT pfam:PF00512      -> 400 invalid_query: Only excluding terms given
```

### Exact fields versus full-text fields

Exact fields use Tantivy's `raw` analyzer: the whole value is one token and no
case folding happens, so matching is case-sensitive and whole-value. Full-text
fields use Tantivy's `default` analyzer: Unicode word segmentation with
lowercase normalization and indexed positions, so matching is case-insensitive
and phrase queries work.

| Behavior | Exact field | Full-text field |
| --- | --- | --- |
| Case sensitivity | Case-sensitive | Case-insensitive |
| Matching unit | Whole value | Individual words |
| Phrase query | Treated as one exact term | Ordered, adjacent words |
| Phrase slop `"a b"~N` | Not supported | Supported |
| Phrase prefix `"a b"*` | Not supported | Supported |
| Single-word prefix | Not supported | Not supported |

```text
product:T1PKS         matches  product:t1pks  does not
organism:AMYCOLATOPSIS matches  organism:amycolatopsis matches
```

A field's public kind (`exact`, `full_text`, or `numeric`) is reported by
`GET /api/search/schema`.

### No single-word prefix or typo tolerance

A single word matches whole indexed words and nothing else. There is no prefix
matching and no typo tolerance on a bare term, on any field:

```text
organism:Strepto        matches nothing
organism:Strepto*       matches nothing
organism:Streptomycez   matches nothing
pfam:PF0051*          matches nothing
```

This is a deliberate limit rather than a gap. Tantivy offers prefix and
Levenshtein matching only as a per-field parser option that applies to
**every** term built against that field, so turning it on would widen a plain
search without the searcher asking for it. The registry therefore carries no
tolerance knob for any field.

A trailing `*` on a bare term is not a wildcard. Tantivy's grammar folds it
into the term text and the tokenizer then drops it, so `Strepto*` is searched
as the exact word `strepto`. There is no wildcard query type to catch it, and
regex queries are disabled.

Looser matching is available, but only inside a multi-word quoted phrase, where
the searcher asks for it explicitly.

### Phrases, slop, and prefix

Double quotes create an ordered, adjacent phrase search on full-text fields,
which index positions:

```text
pfam_name:"His Kinase"      matches  pfam_name:"Kinase His"  does not
organism:"Streptomyces coelicolor"
```

A `~N` after a quoted phrase is Tantivy's native slop: how far the query words
may shift from sitting next to each other.

```text
organism:"His Amycolatopsis"~1    matches His Kinase Amycolatopsis
organism:"Kinase His"~2           matches His Kinase Amycolatopsis
```

Slop counts total positional deviation rather than skipped words, so swapping
two adjacent words costs 2, not 1.

A `*` after a quoted phrase makes its **last word** a prefix:

```text
organism:"streptomyces coeli"*    matches Streptomyces coelicolor
pfam_name:"his ki"*               matches His Kinase
```

The prefixed word still has to sit next to the words before it, so
`organism:"coelicolor strepto"*` matches nothing.

Both operators need the phrase to tokenize to at least two words, and a
one-word prefix is refused outright:

```text
organism:"coeli"*   -> 400 invalid_query: does not produce at least two terms
```

Slop and prefix are mutually exclusive on one phrase, and neither reaches a
bare term: typed after an unquoted term the tilde stays part of the term text
and matches nothing.

On an exact field a quoted value is simply an exact term. Inside quotes, escape
a double quote as `\"` and a backslash as `\\`.

### Unqualified search

A term with no field prefix is searched across every registry field marked as
participating in unqualified search. Numeric navigation and coordinate fields
(`region`, `protocluster`, `start`, `end`) are excluded, so a bare number does
not turn into a coordinate search. `GET /api/search/schema` reports the
`unqualified` flag per field.

### Numeric ranges

The numeric fields support Tantivy range syntax, including exclusive bounds and
open ends:

```text
start:[1000 TO 5000]
start:{1000 TO 5000}
end:[5000 TO *]
```

### Boosts

Each registry field carries one static query-time boost, applied uniformly to
fielded and unqualified clauses. Exact fields boost higher than full-text
fields, so an exact identifier hit outranks a word match. A query may add its
own boost with `^`:

```text
pfam:PF00512^3
```

Results are ordered by Tantivy relevance score. Equal scores resolve in
Tantivy document-insertion order, which is deterministic because documents are
always indexed in selected-file, record, and protocluster order.

### Regex queries

Regex queries are disabled. A regex literal produces a structured error rather
than a result set:

```text
pfam:/PF005.*/   -> 400 invalid_query: Regex queries are not allowed.
```

### PFAM version normalization

Every `db_xref` value on an overlapping `PFAM_domain` is indexed with a
trailing PFAM version removed when the value has the standard accession form,
so `PF00512.28` is indexed as `PF00512`. Search the versionless accession:

```text
pfam:PF00512      matches
pfam:PF00512.28   does not match
```

All `db_xref` values are indexed rather than filtered to a PFAM-only regular
expression. Accession and description are treated as one annotation: when the
accession is absent or unusable, both the accession and the `pfam_name` for
that feature are omitted and a warning is emitted.

### Query errors

Query failures are structured, never a silent empty result set and never a
literal query. The envelope is:

```json
{
  "error": {
    "code": "unknown_field",
    "message": "Unknown field: pfma",
    "details": { "available_fields": ["category", "gene", "..."] }
  }
}
```

| Condition | `code` | HTTP |
| --- | --- | --- |
| Malformed request body | `invalid_request` | 400 |
| Empty query | `empty_query` | 400 |
| Unknown field | `unknown_field`, with `details.available_fields` | 400 |
| Invalid syntax | `invalid_query` | 400 |
| No database selected | `no_database` | 400 |
| Database file gone | `missing_database` | 404 |
| Index absent | `missing_index` | 404 |
| Index corrupt | `corrupt_index` | 500 |
| Rebuild in progress | `index_rebuilding` | 409 |
| Interrupted build | `index_interrupted` | 409 |
| Schema version mismatch | `incompatible_schema` | 409 |

The character position of a parse error is not tracked and is not reported.

### Availability

Advanced search applies to preprocessed backend datasets only: the index is
built from antiSMASH JSON on the server during preprocessing. JSON and
GenBank files loaded directly into the browser keep their existing basic search
behavior and are not in the Tantivy index.

The frontend surfaces for this — the level selector, the help popup driven by
`GET /api/search/schema`, and record-to-protocluster navigation from a search
hit — are planned and **not yet shipped**. Until Stage 3 lands, the shipped
surfaces are the HTTP endpoints and the development CLI.

## Development CLI

The CLI is the primary manual experimentation surface. Run it from the
`backend/` directory:

```bash
# Build an index from selected files under a source root
uv run python -m bgc_viewer.search.cli build-index ../demos/data \
    -o /tmp/bgv --file NC_003888.3.json --file Y16952.json

# Query it
uv run python -m bgc_viewer.search.cli search /tmp/bgv 'pfam:PF00550 AND pfam:PF00668'
uv run python -m bgc_viewer.search.cli search /tmp/bgv 'organism:Strepto*'
uv run python -m bgc_viewer.search.cli search /tmp/bgv 'product:terpene' --offset 2 --limit 2

# Result granularity: protocluster (default), region, or record
uv run python -m bgc_viewer.search.cli search /tmp/bgv 'pfam:PF00550' --level region
```

Selected input paths are explicit and resolved against the source root; paths
outside the root are rejected and no additional JSON files are discovered
implicitly.

## Rebuild requirements

The index is rebuilt by preprocessing, which deletes and recreates the SQLite
database and its sibling `tantivy.index/` in place. **Rerunning preprocessing
is the recovery procedure after a failed build**: a run that raises leaves
neither artifact behind.

Bump `SEARCH_SCHEMA_VERSION` in `document.py` whenever a registry change
alters the stored Tantivy schema or the values that get stored, which means
changing a field's:

- `name`
- `value_type`
- `analyzer`
- `cardinality`, when the change alters what is extracted for the field
- the extraction semantics of an existing field

Do **not** bump it for query-time or display-only changes: `boost`,
`default_search`, `returned`, and `description` are applied
when a query is parsed or a response is assembled and leave the stored index
untouched.

`open_index` rebuilds the expected schema from the current registry, rejects
an index whose stored schema differs, and then checks the persisted schema
version, so a stale index fails loudly with `incompatible_schema` rather than
serving wrong results.

A `.building` sentinel in the preprocessing output directory marks a run in
progress. It is deliberately not cleared on failure: a present sentinel with
no build running means the previous run was interrupted, and search reports
`index_interrupted` rather than serving a half-built pair. It is never
cleared automatically.

## Contributor recipes

### Adding a search field

1. Add one typed `SearchFieldDefinition` to `SEARCH_FIELD_REGISTRY` in
   `backend/bgc_viewer/search/document.py`: the public `name`, a
   user-facing `description` in plain prose, the `attribute` it reads from the
   canonical document, `value_type`, `cardinality`, `analyzer`, whether it is
   `returned` in ordinary hits, whether unqualified queries search it
   (`default_search`), its static query-time `boost`, whether it is `required`
   in a canonical document, and whether it is `required`. Every
   registered field is stored in Tantivy; `returned` is the
   only storage-related decision and selects what comes back in an ordinary
   hit.
2. Add the attribute to `SearchFields` or `SourceFile` in `document.py`, and
   add extraction for it to each adapter in
   `backend/bgc_viewer/search/extraction.py` that can provide it. Missing
   optional data produces an empty value, not a failed file.
3. Bump `SEARCH_SCHEMA_VERSION` if the change alters the stored schema, per
   the rules above.
4. Add a minimal fixture containing two protoclusters that differ only in the
   new field under `backend/bgc_viewer/tests/search/fixtures/antismash8/`.
5. Add exact or full-text, Boolean, unqualified-search, and missing-value
   tests as appropriate in `backend/bgc_viewer/tests/search/test_index.py`.
6. Run the suite and rebuild any test indexes:

   ```bash
   cd backend && uv run pytest bgc_viewer/tests/search/
   ```

No change to query parsing, the Flask routes, or the Vue frontend is needed.
The registry drives the Tantivy schema, the default search fields, the boosts,
the boosts, and the field metadata served by
`GET /api/search/schema`, so a new field reaches searchers through the
existing paths.

`backend/bgc_viewer/tests/search/test_field_registry_docs.py` is the guard
that keeps the registry honest: it fails if a field name is duplicated, a
value type, cardinality, or analyzer combination is invalid, a numeric field
is included in unqualified search, a description is empty or carries markup,
or the `tantivy` schema builder rejects a field.

### Supporting a changed antiSMASH major version

1. Add a small representative JSON fixture produced by that antiSMASH version
   under `backend/bgc_viewer/tests/search/fixtures/antismashN/`.
2. Run the adapter contract suite against the v8 compatibility path:

   ```bash
   cd backend && uv run pytest bgc_viewer/tests/search/test_adapters.py
   ```

3. If it passes, register the version as verified against the existing
   `Antismash8Adapter` in the `_ADAPTERS` map in
   `backend/bgc_viewer/search/extraction.py` without duplicating adapter
   code. If it fails, implement an `AntismashNAdapter` in the same file that
   translates the new layout into the unchanged canonical document contract,
   reusing the shared location, normalization, and overlap helpers, and
   register it in `_ADAPTERS`.
4. Run the shared adapter contract tests, which assert identical canonical
   documents for semantically equivalent fixtures across versions.
5. Document the real source-layout differences and update the compatibility
   matrix below.

Never spread `if version == N` branches through the indexer or the field
extractors. Version differences live in adapters only.

Adapter validation errors include the source file, the declared antiSMASH
version, the adapter attempted, and the missing or incompatible JSON path.

## Compatibility matrix

| Declared antiSMASH version | Adapter selected | How it was selected | Verified by |
| --- | --- | --- | --- |
| 8.0.2 (extraction baseline) | `Antismash8Adapter` | Exact registration for major version 8 | `fixtures/antismash8/equivalent.json`, `fixtures/antismash8/multi.json` |
| 7.0.1 | `Antismash8Adapter` | v8 compatibility fallback | `fixtures/antismash7/equivalent.json` |
| 9.0.0 | `Antismash8Adapter` | v8 compatibility fallback | `fixtures/antismash9/equivalent.json` |
| Unknown or unparsable version | `Antismash8Adapter` | Fallback when the declared major version is unrecognized | `_select_adapter` in `extraction.py` |
| Any version with an incompatible required structure | none | `ExtractionError` naming the file, declared version, adapter, and failing JSON path | `test_adapters.py` |

antiSMASH 8.0.2 is the baseline established by the demo files. Any valid 8.x
file produces the same search-document structure. Other major versions run the
same v8-compatible extraction path optimistically and are accepted whenever
the required record, feature, location, and protocluster qualifier structures
can be read and the generated documents validate. The declared version number
alone is never a rejection criterion.

## Testing

| File | Covers |
| --- | --- |
| `tests/search/test_extraction.py` | Document extraction, interval overlap, warnings, thresholds |
| `tests/search/test_adapters.py` | Cross-version adapter contract equivalence and compatibility errors |
| `tests/search/test_index.py` | Schema derivation, analyzers, Boolean, phrase, slop and phrase-prefix queries, strict single-word terms, ranking, pagination, reopen |
| `tests/search/test_examples.py` | Example-template registry, value collection, SQLite persistence |
| `tests/search/test_api.py` | Endpoint request parsing, response shapes, error statuses |
| `tests/search/test_build_state.py` | Build sentinel and rebuild signaling |
| `tests/search/test_reader_lifecycle.py` | Reader opened per request, nothing pinned or retained |
| `tests/search/test_record_cache_invalidation.py` | Record-data cache generation across a rebuild |
| `tests/search/test_field_registry_docs.py` | Registry hygiene and `tantivy` schema acceptance |

The generated Tantivy index is inspectable with standard tooling such as
`tantivy-cli` or `pytantivy`; there is no custom index inspection API.
