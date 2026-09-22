# Search Index

Protocluster search runs on an embedded [Tantivy](https://github.com/quickwit-oss/tantivy) index built from antiSMASH JSON output and queried through Tantivy's native query language.

One Tantivy document is one protocluster.

## Where things live

| Concern | Path |
| --- | --- |
| Public field metadata, location parsing, example templates, schema version | `backend/bgc_viewer/search/document.py` |
| Tantivy schema, query config, index build/open/search | `backend/bgc_viewer/search/index.py` |
| antiSMASH JSON extraction to Tantivy documents | `backend/bgc_viewer/search/extraction.py` |
| Build sentinel and rebuild signaling | `backend/bgc_viewer/search/build_state.py` |
| HTTP request/response contract | `backend/bgc_viewer/search/api.py` |
| Development CLI | `backend/bgc_viewer/search/cli.py` |
| Preprocessing integration | `backend/bgc_viewer/preprocessing.py` |
| Search tests | `backend/bgc_viewer/tests/search/` |
| antiSMASH fixtures | `backend/bgc_viewer/tests/search/fixtures/` |

## Search fields

There is no single field-registry object. A searchable field is declared in
four places that the tests keep in step:

1. **Schema** — `_SCHEMA` in
   [`backend/bgc_viewer/search/index.py`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/index.py):
   the ordered `(name, tokenizer)` list that `build_schema()` turns into
   Tantivy fields. The tokenizer is `raw` (exact whole-value match),
   `default` (full-text), `path` (the custom path tokenizer), or
   `numeric` (a stored integer with a fast field).
2. **Query config** — also in `index.py`: `_DEFAULT_SEARCH_FIELDS`
   (derived: every non-numeric field), `_FIELD_BOOSTS` (the per-field
   query-time weight, never stored), and `_RETURNED_FIELDS` (which stored
   fields come back in ordinary hits).
3. **Public metadata** — `PUBLIC_FIELDS` in `document.py`: the
   `PublicFieldInfo(name, kind, unqualified, description)` rows served to
   the help popup and `GET /api/search/schema`. The public `kind`
   (`exact` / `full_text` / `path` / `numeric`) and `unqualified` flag
   are written here directly rather than derived from a registry.
4. **Extraction** — `_document()` in `extraction.py`: how each field is
   populated from antiSMASH JSON.

The current field set is defined in the code, not duplicated here: see
`_SCHEMA` in `index.py` for the indexed fields and their tokenizers, and
`PUBLIC_FIELDS` in `document.py` for the public `kind`, `unqualified`,
and `description` of each.

A field's `kind` and its schema tokenizer describe the same matching
behavior from two angles: `exact`↔`raw`, `full_text`↔`default`,
`path`↔`path`, `numeric`↔`numeric`. Every non-numeric field is
unqualified (searched by a bare term); numeric fields are not.

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

Bump `SEARCH_SCHEMA_VERSION` in `document.py` whenever a change alters the
stored Tantivy schema or the values that get stored, which means changing a
field's:

- `name` (the `_SCHEMA` entry in `index.py`)
- tokenizer (`raw` / `default` / `path`) or its numeric-vs-text nature
- the extraction semantics of an existing field (what value
  `_document()` writes for it)

Do **not** bump it for query-time or display-only changes: the boost
(`_FIELD_BOOSTS`), the unqualified/default-search set
(`_DEFAULT_SEARCH_FIELDS`), the returned-field set
(`_RETURNED_FIELDS`), and the public `description` are applied when a
query is parsed or a response is assembled and leave the stored index
untouched.

## Contributor recipes

### Adding a search field

A new field touches four places plus tests:

1. **Schema** — add `(name, tokenizer)` to `_SCHEMA` in `index.py`,
   where `tokenizer` is `raw`, `default`, `path`, or `numeric`. This is
   what `build_schema()` indexes and stores.
2. **Query config** — in `index.py`: add a boost to `_FIELD_BOOSTS` for
   a text field (numeric fields are not boosted), and add
   `(name, "text" | "numeric")` to `_RETURNED_FIELDS` if the value
   should come back in ordinary hits. Unqualified search is automatic for
   every non-numeric field via `_DEFAULT_SEARCH_FIELDS`.
3. **Public metadata** — add a `PublicFieldInfo(name, kind, unqualified,
   description)` to `PUBLIC_FIELDS` in `document.py`. Keep `kind`
   consistent with the schema tokenizer and `unqualified` consistent with
   the default-search rule (true for every non-numeric field).
4. **Extraction** — populate the field in `_document()` in
   `extraction.py`: add each item for a multi-valued field, skip a single
   text field when empty, and use `add_integer` for a numeric field.
   Missing optional data produces an empty value, not a failed file.
5. Bump `SEARCH_SCHEMA_VERSION` if the change alters the stored schema,
   per the rules above.
6. Add a minimal fixture containing two protoclusters that differ only in
   the new field under `backend/bgc_viewer/tests/search/fixtures/antismash8/`.
7. Add exact or full-text, Boolean, unqualified-search, and missing-value
   tests as appropriate in `backend/bgc_viewer/tests/search/test_index.py`,
   and a `PUBLIC_FIELDS` row check in `test_api.py`.

### Supporting a changed antiSMASH major version

There is no per-version adapter. `extraction.py` reads the current
antiSMASH JSON structure directly and is version-agnostic: the declared
`version` is read only for diagnostics (the duplicate-identity message).
Any file whose record, feature, location, and protocluster qualifier
structure matches the expected shape extracts successfully regardless of
the declared major version. If a future major version changes that
structure, update `_extract_records` / `_document` in `extraction.py`
(and bump `SEARCH_SCHEMA_VERSION` if the stored values change).
