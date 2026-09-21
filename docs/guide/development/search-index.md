# Search Index

Protocluster search runs on an embedded [Tantivy](https://github.com/quickwit-oss/tantivy) index built from antiSMASH JSON output and queried through Tantivy's native query language.

One Tantivy document is one protocluster.

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

## Search field registry

The registry defined what fields are indexed and how.

The field registry (`SEARCH_FIELD_REGISTRY`) in
[`backend/bgc_viewer/search/document.py`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/document.py)
is the single source of truth for searchable fields. Each entry's public
projection — the `name`, `kind`, `unqualified`, and `description` keys
served to searchers — is documented in the
[search API reference](/api/search#search-schema).

Every entry is a `SearchFieldDefinition`. Only `name` and
`description` keys reach the public web API directly.

- `name` — the public field name, also the Tantivy field name; served as
  `name`.
- `description` — plain-prose description served as `description`; no
  markup, because the help popup renders it verbatim.
- `attribute` — which attribute of the canonical document the field
  reads: looked up on `SearchFields` first, then on `SourceFile`.
- `value_type` — `text`, `keyword`, or `numeric`. `numeric` is stored as
  a Tantivy integer with a fast field; `text` and `keyword` are both
  stored as Tantivy text fields, where the type records the intent of the
  value — prose versus identifier — while the analyzer decides matching.
  Together with `analyzer` this also determines the public `kind`.
- `cardinality` — `single` or `multi`. A `multi` value is a tuple of
  non-empty, deduplicated strings, each indexed as its own term; a
  `single` empty string is not indexed at all.
- `analyzer` — `exact` maps to Tantivy's `raw` tokenizer (whole value,
  no case folding) and `full_text` to the `default` tokenizer (word
  segmentation, lowercase, indexed positions). `path` maps to a custom
  tokenizer registered on every index that splits on `/` and `.`, so a
  file path is searchable by directory, stem, or extension while the
  whole value still matches as a phrase. Only numeric fields carry
  `None`.
- `returned` — every registered field is stored so its value can be read
  back for example collection and diagnostics; `returned` selects which
  stored fields come back in ordinary search hits.
- `default_search` — whether an unqualified term searches the field;
  surfaced in the public API as `unqualified`.
- `boost` — a static query-time weight handed to the Tantivy query
  parser for every non-numeric field, scaling that field's score
  contribution. It is never stored in the index.
- `required` — canonical-document validation: a required field whose
  value is an empty string or empty tuple rejects the document at
  construction time.

## Query language

Tantivy's native `QueryParser` language is the public query contract.

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

### Path fields

The file fields (`output_file`, `input_file`) use a custom `path` analyzer: a
regular-expression tokenizer that matches the runs *between* `/` and `.`, so
`nested/NC_003888.3.json` indexes as the terms `nested`, `NC_003888`, `3`,
and `json`. Like the `raw` analyzer it replaces, it does no case folding, so
matching stays case-sensitive.

Because the whole value is a sequence of adjacent tokens, a quoted phrase over
the whole path still matches exactly, and each component matches on its own:

```text
output_file:"nested/NC_003888.3.json"   matches only that file
output_file:nested                       matches the directory component
output_file:NC_003888.3                 matches the stem in any directory
output_file:json                        matches every JSON file
```

A prefix on a multi-token phrase narrows the last component, so a searcher can
drop the (usually `json`) extension and match a file by its stem:

```text
output_file:"NC_003888.3"*              matches NC_003888.3.json
output_file:"nested/NC_003888"*         matches nested/NC_003888.3.json
```

The generated `path_prefix` example does exactly this: it strips the extension
from the collected path and appends `*`. It is skipped when the stripped path
would leave only a single component (e.g. `Y16952.json` → `Y16952`), because a
prefix phrase needs at least two terms.

A single bare component is still matched whole, not as a prefix, exactly as in
the exact and full-text cases: `output_file:nested*` matches nothing.

### No single-word prefix or typo tolerance

A trailing `*` on a bare term is not a wildcard. Tantivy's grammar folds it
into the term text and the tokenizer then drops it, so `Strepto*` is searched
as the exact word `strepto`.

Looser matching is available, but only inside a multi-word quoted phrase, where
the searcher asks for it explicitly.

A `~N` after a quoted phrase is Tantivy's native slop: how far the query words
may shift from sitting next to each other.

```text
organism:"His Amycolatopsis"~1    matches His Kinase Amycolatopsis
```

A `*` after a quoted phrase makes its **last word** a prefix:

```text
organism:"streptomyces coeli"*    matches Streptomyces coelicolor
```

## Search CLI

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

## Versioning

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

## Contributor recipes

### Adding a search field

1. Add one typed `SearchFieldDefinition` to `SEARCH_FIELD_REGISTRY` in
   `backend/bgc_viewer/search/document.py`, setting every key described
   in [Search field registry keys](#search-field-registry) above.
2. Add the attribute to `SearchFields` or `SourceFile` in `document.py`.
3. Add extraction for it to each adapter in
   `backend/bgc_viewer/search/extraction.py` that can provide it. Missing
   optional data produces an empty value, not a failed file.
4. Bump `SEARCH_SCHEMA_VERSION` if the change alters the stored schema, per
   the rules above.
5. Add a minimal fixture containing two protoclusters that differ only in the
   new field under `backend/bgc_viewer/tests/search/fixtures/antismash8/`.
6. Add exact or full-text, Boolean, unqualified-search, and missing-value
   tests as appropriate in `backend/bgc_viewer/tests/search/test_index.py`.

### Supporting a changed antiSMASH major version

Any valid 8.x file produces the same search-document structure. 
Other major versions run the
same v8-compatible extraction path optimistically and are accepted whenever
the required record, feature, location, and protocluster qualifier structures
can be read and the generated documents validate.
