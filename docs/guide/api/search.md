# Protocluster Search API

Full-text and exact search over protoclusters, backed by an embedded Tantivy
index built during preprocessing. The result granularity is selected by the URL
path, which keeps each granularity an addressable resource and avoids
conflating record-level browsing with protocluster-level search.

For how the query language behaves, see the
[search index guide](/development/search-index).

## Search

**Endpoints:**

```text
POST /api/search/protocluster
POST /api/search/region
POST /api/search/record
```

**Request body:**

```json
{
  "query": "pfam:PF00512 AND organism:Amycolatopsis",
  "page": 1,
  "per_page": 20
}
```

- `query` — a Tantivy query string. Required to be a string; an empty or
  whitespace-only query is rejected with `empty_query`.
- `page` — 1-based page number (default: 1).
- `per_page` — results per page (default: 20, max: 100).

The request body carries no level: the URL path is authoritative.

**Response:**

A successful response contains exactly `hits` and `total`. Request parameters
are not echoed back; the client already knows them and derives page counts
from its own `per_page`. `total` is the number of distinct units at the
selected level, not the raw matching-document count.

`protocluster` returns one hit per matching protocluster, with the stored
identity and display values:

```json
{
  "hits": [
    {
      "score": 4.2135,
      "fields": {
        "record": "NC_003888.3",
        "region": 1,
        "protocluster": 2,
        "start": 120400,
        "end": 189300,
        "product": "terpene",
        "category": "Terpene",
        "organism": "Streptomyces coelicolor A3(2)",
        "output_file": "NC_003888.3.json",
        "input_file": "NC_003888.3.gbk"
      }
    }
  ],
  "total": 1
}
```

`region` collapses matching protoclusters to unique regions, each scored by its
best-matching protocluster:

```json
{
  "hits": [
    {
      "score": 4.2135,
      "record": "NC_003888.3",
      "region": 1,
      "output_file": "NC_003888.3.json",
      "input_file": "NC_003888.3.gbk"
    }
  ],
  "total": 3
}
```

`record` collapses matching protoclusters to unique records:

```json
{
  "hits": [
    {
      "score": 4.2135,
      "record": "NC_003888.3",
      "output_file": "NC_003888.3.json",
      "input_file": "NC_003888.3.gbk"
    }
  ],
  "total": 2
}
```

**Example:**

```javascript
const response = await fetch('/api/search/protocluster', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'pfam:PF00512 AND pfam:PF00513',
    page: 1,
    per_page: 20,
  }),
});
const { hits, total } = await response.json();

console.log(`Found ${total} matching protoclusters`);
hits.forEach((hit) => {
  console.log(`${hit.fields.record} region ${hit.fields.region}: ${hit.fields.product}`);
});
```

Results are ordered by Tantivy relevance score. Equal scores resolve in
deterministic index-insertion order, so paging across page boundaries
preserves the same order as the full result set.

## Search schema

**Endpoint:** `GET /api/search/schema`

Level-independent metadata for the shared search help popup. Searchable fields
and examples are identical at every level, because the level changes only the
hit shape and what happens when a hit is selected, so the URL carries no
level and the response carries no level.

**Response:**

```json
{
  "fields": [
    {
      "name": "pfam",
      "kind": "exact",
      "unqualified": true,
      "description": "PFAM accession of a PFAM_domain overlapping the protocluster, with the version suffix removed, so PF00512.28 is searched as PF00512."
    },
    {
      "name": "region",
      "kind": "numeric",
      "unqualified": false,
      "description": "Region number of the smallest region feature containing the protocluster."
    }
  ],
  "examples": [
    "terpene",
    "category:PKS",
    "\"Homo Sapiens\"",
    "category:PKS AND product:T1PKS",
    "organism:Streptomyces NOT product:T1PKS"
  ],
  "query_syntax_url": "https://docs.rs/tantivy/latest/tantivy/query/struct.QueryParser.html"
}
```

- `fields` — public field metadata derived from the field registry: the public
  `name`, a user-facing `kind` of `exact`, `full_text`, or `numeric`, whether
  an unqualified term searches the field (`unqualified`), and a short
  `description` of what the field holds and where its values come from.
  Cardinality and boosts are internal indexing details and are not exposed,
  and there is no storage flag because every registered field is stored.
- `examples` — runnable example queries generated during preprocessing from
  values in the built index and read back from SQLite, in template order.
- `query_syntax_url` — a generic link to the Tantivy query-language
  documentation. The Tantivy library version is not exposed in this response.

The endpoint resolves the index only to signal availability. Field metadata
comes from the registry and examples come from SQLite, so the response never
reads values from the index.

## Errors

Every search error uses the same envelope:

```json
{
  "error": {
    "code": "unknown_field",
    "message": "Unknown field: pfma",
    "details": { "available_fields": ["category", "gene", "locus", "..."] }
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

An unrecognized level is not a registered route, so the framework's default
response is returned: a `POST` to an unknown level yields `405`, because the
single-page-app fallback only accepts `GET`.

A request that arrives mid-rebuild is rejected with `index_rebuilding` rather
than being served a partial index. `index_interrupted` means a previous build
was interrupted and left a sentinel behind; it is not retryable and requires
rerunning preprocessing.

## Notes

- Each request opens its own index handle and releases it when the response
  returns. No index object is cached between requests, so a completed rebuild
  is visible to the next request by construction.
- SQLite record browsing through `GET /api/database-entries` does not depend
  on a search index existing, and keeps working while the index is missing or
  being rebuilt.
- Advanced search applies to preprocessed backend datasets only. Files loaded
  directly into the browser keep their existing basic search behavior.
