# Region Search API

Full-text, exact, and structured search over antiSMASH regions, backed by an
embedded Tantivy index built during preprocessing. One indexed document is one region,
holding the products and categories of its protoclusters and the results of the
antiSMASH analysis modules for it. The result granularity is selected by the URL
path, which keeps each granularity an addressable resource and avoids
conflating record-level browsing with region-level search.

For how the query language behaves, see the
[search index guide](/development/search-index).

## Search

**Endpoints:**

```text
POST /api/search/region
POST /api/search/record
```

**Request body:**

```json
{
  "query": "pfam:PF00550 AND substrates:Leu",
  "page": 1,
  "per_page": 20
}
```

or, with a [structured filter](#structured-filters):

```json
{
  "filter": {
    "operator": "AND",
    "conditions": [
      { "field": "product_category", "operator": "in", "value": ["NRPS", "PKS"] },
      { "field": "knowncluster_top_similarity", "operator": "gte", "value": 50 }
    ],
    "groups": []
  },
  "sort": { "field": "length", "order": "desc" },
  "facets": ["product", "organism"],
  "facet_size": 20,
  "page": 1,
  "per_page": 20
}
```

- `query` — a Tantivy query string. An empty or whitespace-only query is
  rejected with `empty_query`.
- `filter` — a structured filter, sent instead of `query`; sending both is
  rejected with `invalid_request`. A filter without conditions matches every
  region, so an empty filter browses the whole index.
- `sort` — optional. Orders hits by a field whose schema entry is `sortable`
  (one value per region: exact text, numbers, and yes/no fields) instead of
  by relevance. `order` is `asc` (default) or `desc`. At the record level,
  records follow their first matching region in that order.
- `facets` — optional. Fields whose most common values are counted over every
  matching region; each must be a `facet` field in the schema (exact text and
  yes/no fields).
- `facet_size` — values per facet field (default: 20, max: 100).
- `page` — 1-based page number (default: 1).
- `per_page` — results per page (default: 20, max: 100).

The request body carries no level: the URL path is authoritative.

**Response:**

A successful response contains exactly `hits`, `has_more`, `total_regions`,
and `facets`.

- `has_more` — whether more hits exist beyond this page at the selected level.
- `total_regions` — the number of matching regions. At the record level this
  still counts regions, so it can exceed the number of records.
- `facets` — each requested facet field mapped to its most common values, as
  `{"value", "count"}` objects with the count of matching regions, most
  common first. Empty when no facets were requested.
- `score` in a hit is the relevance score, or `null` when hits are sorted.

`region` returns one hit per matching region, with the stored identity and
display values. `product` and `product_category` are lists, one entry per
distinct value among the region's protoclusters. `organism` and `input_file`
are left out when the source has none.

```json
{
  "hits": [
    {
      "score": 4.2135,
      "fields": {
        "record": "NC_003888.3",
        "region": 2,
        "start": 120400,
        "end": 189300,
        "product": ["terpene", "T2PKS"],
        "product_category": ["terpene", "PKS"],
        "organism": "Streptomyces coelicolor A3(2)",
        "output_file": "NC_003888.3.json",
        "input_file": "NC_003888.3.gbk"
      }
    }
  ],
  "has_more": false,
  "total_regions": 1,
  "facets": {}
}
```

`record` collapses matching regions to unique records, each scored by its
best-matching region:

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
  "has_more": false,
  "total_regions": 3,
  "facets": {}
}
```

**Example:**

```javascript
const response = await fetch('/api/search/region', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'pfam:PF00550 AND substrates:Leu',
    page: 1,
    per_page: 20,
  }),
});
const { hits, has_more } = await response.json();

console.log(`Has more results: ${has_more}`);
hits.forEach((hit) => {
  console.log(`${hit.fields.record} region ${hit.fields.region}: ${hit.fields.product.join(', ')}`);
});
```

## Structured filters

A structured filter is the query model of the BGC Atlas query builder. A
group joins its conditions and nested groups with `AND` or `OR`:

```json
{
  "operator": "AND",
  "conditions": [
    { "field": "record", "operator": "equals", "value": "NC_003888.3" }
  ],
  "groups": [
    {
      "operator": "OR",
      "conditions": [
        { "field": "product_category", "operator": "equals", "value": "RiPP" },
        { "field": "substrates", "operator": "equals", "value": "Ser" }
      ],
      "groups": []
    }
  ]
}
```

`operator` defaults to `AND`, and `conditions` and `groups` to empty lists.
Other keys, such as the `id`s the builder assigns, are ignored. A filter may
nest 8 groups deep and hold 200 conditions, each with up to 1000 values.

A condition compares one field to a `value` (a string, a number, or a list of
them) with an operator. The operators a field supports depend on its kind,
and the schema lists them per field:

| Operator | Kinds | Matches regions where |
| --- | --- | --- |
| `equals`, `not_equals` | exact, numeric, boolean | some value equals / no value equals `value` |
| `in`, `not_in` | exact | some value is / no value is in the list |
| `contains`, `not_contains` | exact, full text, path | some value contains / no value contains `value`, ignoring case |
| `starts_with`, `ends_with` | exact | some value starts / ends with `value`, ignoring case |
| `gt`, `gte`, `lt`, `lte` | numeric | some value compares so with `value` |
| `between` | numeric | some value lies in `[min, max]`, both inclusive; `null` or `""` leaves a bound open |
| `exists`, `not_exists` | exact, numeric, boolean | the field has some / no value; `value` is ignored |

- `equals` and `in` on exact fields are case-sensitive, so they suit values
  picked from the [field values](#field-values) endpoint. The substring
  operators ignore case.
- On full-text and path fields, `contains` matches each word of `value`
  inside some word of the field. On the catch-all `text` field this is the
  "any field contains" condition.
- Negated operators match regions without any value too: `not_equals NRPS`
  matches a region with no product at all.
- Boolean values are `true`/`false`, `"true"`/`"false"`, `"yes"`/`"no"`, or
  `1`/`0`.
- A condition on the pseudo-field `_query` with operator `matches` runs its
  value as a query string, so free query-language text can sit beside the
  other conditions. Its parse errors are reported as for `query`.

A condition whose value is still blank, such as an empty list or a
whitespace-only string, is dropped, so a half-built filter can be run. Every
other condition that cannot be honoured (an unknown field, an operator the
field does not support, or an unusable value such as `"abc"` for a number)
rejects the whole request with `unhonourable_filter`, since running the rest
would answer a broader question.

## Field values

**Endpoint:** `GET /api/search/values?field=pfam&q=PF005&size=20`

Suggested values of one field for a value picker, with the number of regions
holding each value across the whole index.

- `field` — required; a `facet` field in the schema.
- `q` — optional text a value must contain, ignoring case. Values that start
  with it come first, then the most common.
- `size` — number of values (default: 20, max: 100).

**Response:**

```json
{
  "field": "pfam",
  "values": [
    { "value": "PF00501", "count": 7 },
    { "value": "PF00550", "count": 11 }
  ]
}
```

## Search schema

**Endpoint:** `GET /api/search/schema`

Searchable fields and examples for search help popup.

**Response:**

```json
{
  "fields": [
    {
      "name": "pfam",
      "kind": "exact",
      "label": "PFAM",
      "group": "Functional hits",
      "multi": true,
      "default_search": true,
      "description": "PFAM accession of a PFAM_domain feature or a cluster_hmmer hit overlapping the region, with the version suffix removed, so PF00512.28 is searched as PF00512.",
      "operators": ["in", "not_in", "equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with", "exists", "not_exists"],
      "facet": true,
      "sortable": false
    },
    {
      "name": "region",
      "kind": "numeric",
      "label": "Region number",
      "group": "Region",
      "multi": false,
      "default_search": false,
      "description": "Region number of the region within its record.",
      "operators": ["equals", "not_equals", "gt", "gte", "lt", "lte", "between", "exists", "not_exists"],
      "facet": false,
      "sortable": true
    }
  ],
  "examples": [
    "PF00550",
    "product_category:PKS",
    "\"Streptomyces coelicolor A3(2)\"",
    "product_category:PKS AND product:T1PKS",
    "organism:\"Streptomyces coelicolor A3(2)\" NOT product:T1PKS"
  ],
  "query_syntax_url": "https://docs.rs/tantivy/latest/tantivy/query/struct.QueryParser.html",
  "raw_query_field": "_query"
}
```

- `fields` — one object per searchable field, in registry order, derived from
  the field registry. Each field object has exactly these keys:

  - `name` — the public field name, used as the prefix of a qualified query
    term: `pfam:PF00512` searches the field named `pfam`.
  - `kind` — how the field matches queries:
    - `exact` — the whole value is indexed as a single token with no case
      folding, so a term must equal the stored value exactly,
      case-sensitively.
    - `full_text` — the value is tokenized into words with lowercase
      normalization, so matching is case-insensitive and phrase queries
      work.
    - `path` — a file path, matched as a whole and by its components,
      split on `/` and `.`.
    - `numeric` — the value is stored as an integer or a decimal number and
      matched as a number.
    - `boolean` — the value is `true` or `false`.
  - `label` — a short display name for the field.
  - `group` — the section the field belongs to, such as `Region`,
    `NRPS/PKS`, or `Comparative`.
  - `multi` — whether a region can hold several values; they are returned as
    a list.
  - `default_search` — whether a bare term with no `field:` prefix is
    searched against this field. Only text fields (`exact`, `full_text`, and
    `path`) participate in default search.
  - `description` — a short plain-prose description of what the field
    holds and where its values come from. The search help popup renders it
    verbatim.
  - `operators` — the [structured-filter](#structured-filters) operators the
    field supports.
  - `facet` — whether the field's values can be counted with `facets` and
    suggested by the [field values](#field-values) endpoint.
  - `sortable` — whether hits can be sorted by the field.
- `examples` — runnable example queries generated during preprocessing from
  values in the built index and read back from SQLite, in template order.
- `query_syntax_url` — a generic link to the Tantivy query-language
  documentation.
- `raw_query_field` — the pseudo-field of a filter condition that runs a
  query string.

## Errors

Every search error uses the same envelope:

```json
{
  "error": {
    "code": "unknown_field",
    "message": "Unknown field: pfma",
    "details": { "available_fields": ["antismash_domains", "at_specificity", "..."] }
  }
}
```

| Condition | `code` | HTTP |
| --- | --- | --- |
| Malformed request body | `invalid_request` | 400 |
| Empty query | `empty_query` | 400 |
| Unknown field | `unknown_field`, with `details.available_fields` | 400 |
| Invalid syntax | `invalid_query` | 400 |
| Malformed filter | `invalid_filter` | 400 |
| Filter condition that cannot be honoured | `unhonourable_filter`, with `details.conditions` | 400 |
| Facet or values field that cannot be counted | `invalid_facet_field` | 400 |
| No database selected | `no_database` | 400 |
| Database file gone | `missing_database` | 404 |
| Index absent | `missing_index` | 404 |
| Index corrupt | `corrupt_index` | 500 |
| Rebuild in progress | `index_rebuilding` | 409 |
| Interrupted build | `index_interrupted` | 409 |
| Schema version mismatch | `incompatible_schema` | 409 |

A request that arrives mid-rebuild is rejected with `index_rebuilding` rather
than being served a partial index. `index_interrupted` means a previous build
was interrupted and left a sentinel behind; it is not retryable and requires
rerunning preprocessing.

`unhonourable_filter` lists every condition that could not be honoured, so a
saved or shared filter can be repaired from it:

```json
{
  "error": {
    "code": "unhonourable_filter",
    "message": "Cannot run this filter: field \"length\" does not support operator \"contains\" (supported: equals, not_equals, gt, gte, lt, lte, between, exists, not_exists). Fix or remove that condition; running the filter without it would answer a broader question.",
    "details": {
      "conditions": [
        {
          "field": "length",
          "operator": "contains",
          "reason": "unsupported_operator",
          "value": "1",
          "supported_operators": ["equals", "not_equals", "gt", "gte", "lt", "lte", "between", "exists", "not_exists"]
        }
      ]
    }
  }
}
```

`reason` is `unknown_field`, `unsupported_operator`, or `unusable_value`.
