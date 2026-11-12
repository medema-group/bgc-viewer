# Search Index

Region search runs on an embedded [Tantivy](https://github.com/quickwit-oss/tantivy) index built from antiSMASH JSON output and queried through Tantivy's native query language.

One Tantivy document is one antiSMASH region. The products, categories, and
detection rules of the region's protoclusters are multi-valued fields of the
region, and the record level is found by grouping matching regions by record.
The field set follows the antiSMASH facets of the
[BGC Atlas](https://github.com/ZiemertLab/bgc-atlas-web-v2), whose field names
it reuses.

## Where things live

| Concern | Path |
| --- | --- |
| Field registry, location parsing, example templates, schema version | `backend/bgc_viewer/search/document.py` |
| Tantivy schema and query config, index build/open/search | `backend/bgc_viewer/search/index.py` |
| antiSMASH JSON extraction to Tantivy documents | `backend/bgc_viewer/search/extraction.py` |
| Region facets from the antiSMASH analysis modules | `backend/bgc_viewer/search/facets.py` |
| Build sentinel and rebuild signaling | `backend/bgc_viewer/search/build_state.py` |
| HTTP request/response contract | `backend/bgc_viewer/search/api.py` |
| Search CLI | `backend/bgc_viewer/search/cli.py` |
| Indexing CLI | `backend/preprocess_cli.py` |
| Preprocessing integration | `backend/bgc_viewer/preprocessing.py` |
| Search tests | `backend/bgc_viewer/tests/search/` |
| antiSMASH fixtures | `backend/bgc_viewer/tests/search/fixtures/` |

## Search fields

A searchable field is declared once, in the single registry `SEARCH_FIELDS` in
[`backend/bgc_viewer/search/document.py`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/document.py):
an ordered tuple of `SearchField(name, tokenizer, label, group, description,
multi, boost, in_hits, in_text, stored)` entries. Everything else is projected
from it:

1. **Schema** — `build_schema()` in
   [`backend/bgc_viewer/search/index.py`](https://github.com/medema-group/bgc-viewer/blob/main/backend/bgc_viewer/search/index.py)
   turns each entry into a Tantivy field. The `tokenizer` is the field type:
   `raw` (exact whole-value match), `default` (full-text), `path` (the custom
   path tokenizer), `integer`, `float`, or `boolean`. Exact text fields and
   all number and boolean fields are fast fields, so they can be sorted and
   aggregated.
2. **Query config** — also in `index.py`, derived from the registry:
   `_DEFAULT_SEARCH_FIELDS` (every text field), `_FIELD_BOOSTS` (the
   per-field query-time weight, never stored), and `_RETURNED_FIELDS` (which
   stored fields come back in ordinary hits; a `multi` field comes back as a
   list).
3. **Public metadata** — `PUBLIC_FIELDS` in `document.py`, projected from
   the registry: the `PublicFieldInfo(name, kind, label, group, multi,
   default_search, description)` rows served to the help popup and
   `GET /api/search/schema`. Both `kind` (`exact` / `full_text` / `path` /
   `numeric` / `boolean`) and `default_search` are derived from the tokenizer
   rather than declared separately.
4. **Extraction** — `_document_values()` in `extraction.py` collects the
   values of the fields read from features, the functions in `facets.py` those
   read from the record's `modules`, and `build_document()` writes them with
   the method for each field's type.

### The catch-all text field

The `text` field is full-text and indexed only. `build_document()` copies into
it every value of every text field that sets `in_text`: all of them except
sequences and SMILES (`core_seq`, `predicted_smiles`, …) and the path fields.
A bare word therefore also matches inside fields whose whole value it does not
equal, so `coelicolor` finds `organism:"Streptomyces coelicolor A3(2)"`.

### Module facets

The fields read from the antiSMASH analysis modules (NRPS/PKS predictions,
RiPP precursors, ClusterBlast, ClusterCompare, TFBS, …) are scoped to a region
with the full antiSMASH location and by the antiSMASH CDS name, which falls
back from the locus tag to the gene name and protein ID, as the modules key
their results by that name. Module content is read leniently: a missing or
differently shaped part yields no values instead of failing the file, and a
field whose module did not run is absent rather than zero.

The current field set is defined in the code, not duplicated here: see
`SEARCH_FIELDS` in `document.py`.

A field's `kind` and its tokenizer describe the same matching behavior from
two angles: `exact`↔`raw`, `full_text`↔`default`, `path`↔`path`,
`numeric`↔`numeric`. Every non-numeric field participates in default search
(a bare term searches it); numeric fields do not.

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
text:AMYCOLATOPSIS    matches  text:amycolatopsis    matches
```

`organism` is an exact field, so a word of it is searched through `text` or a
bare term: `organism:Streptomyces` matches only an organism named exactly
`Streptomyces`.

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
text:"His Amycolatopsis"~1    matches His Kinase Amycolatopsis
```

A `*` after a quoted phrase makes its **last word** a prefix:

```text
text:"streptomyces coeli"*    matches Streptomyces coelicolor
```

## Search CLI

The CLI is the primary manual experimentation surface. Run it from the
`backend/` directory:

```bash
# Build SQLite and Tantivy indexes
uv run python preprocess_cli.py /path/to/data --output /tmp/bgv/attributes.db

# Query it
uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'pfam:PF00550 AND pfam:PF00668'
uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'substrates:Leu AND knowncluster_top_similarity:[50 TO 100]'
uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'product:terpene' --offset 2 --limit 2

# Result granularity: region (default) or record
uv run python -m bgc_viewer.search.cli search /tmp/bgv/tantivy.index 'pfam:PF00550' --level record
```

Search documents are extracted from the JSON files in parallel worker processes,
one per CPU by default. Each worker holds one decoded record in memory, about six
times the record's size in the JSON file, so on machines with little RAM and very
large records, limit the workers with `--jobs` (e.g. `--jobs 4`). Documents,
warnings, and errors are replayed in file order, so the result is the same for
any number of workers.

Tantivy chooses its writer thread count automatically; tied-hit order and sampled
example values may vary between rebuilds.

## Versioning

Bump `SEARCH_SCHEMA_VERSION` in `document.py` whenever a change alters the
stored Tantivy schema or the values that get stored, which means changing a
field's:

- `name` (the `SEARCH_FIELDS` entry in `document.py`)
- tokenizer (`raw` / `default` / `path` / `integer` / `float` / `boolean`)
- `stored` or `in_text`, which change what is stored or copied into `text`
- the extraction semantics of an existing field (what values
  `_document_values()` or `facets.py` collect for it)

Do **not** bump it for query-time or display-only changes: the boost
(`boost`), the returned-field flag (`in_hits`), and the public `label`,
`group`, and `description` are projected from the registry and applied when a
query is parsed or a response is assembled, leaving the stored index
untouched.

## Contributor recipes

### Adding a search field

A new field touches two places plus tests:

1. **Registry** — add a `SearchField` entry to `SEARCH_FIELDS` in
   `document.py`, or use the `_keyword`, `_sequence`, or `_number` helpers.
   Give it a `label` and `group` for display, set `multi=True` when a region
   can hold several values, and `in_hits=True` when the value should come back
   in ordinary hits. The Tantivy schema, query config, and public metadata are
   projected from this entry; default search is automatic for every text field.
2. **Extraction** — collect the values as a list under the field name, in
   `_document_values()` in `extraction.py` for a value read from features, or
   in a function of `facets.py` for one read from the record's `modules`. An
   empty list adds nothing, so missing optional data produces no value rather
   than a failed file.
3. Bump `SEARCH_SCHEMA_VERSION`, as the stored schema changes.
4. Add tests: feature-derived fields in
   `backend/bgc_viewer/tests/search/test_extraction.py`, module-derived ones in
   `test_facets.py`, whose shared record has two regions so each test can check
   the value is scoped to the right one.

### Supporting a changed antiSMASH major version

There is no per-version adapter. `extraction.py` reads the current
antiSMASH JSON structure directly and is version-agnostic: the declared
`version` is read only for diagnostics (the duplicate-identity message).
Any file whose record, feature, location, and region and protocluster
qualifier structure matches the expected shape extracts successfully
regardless of the declared major version. If a future major version changes
that structure, update `_extract_records` / `_document_values` in
`extraction.py` (and bump `SEARCH_SCHEMA_VERSION` if the stored values
change). Module results are read leniently, so a changed module schema empties
the affected fields rather than failing the file; update its function in
`facets.py`.
