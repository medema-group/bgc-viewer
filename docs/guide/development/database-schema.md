# Database Schema Documentation

> **⚠️ Warning**: The database specification is still under development and subject to change. The schema may be modified in future releases, and backward compatibility is not guaranteed.


## Overview

The BGC Viewer uses a SQLite database to index antiSMASH JSON files. The schema is designed to support:
- Fast random access to specific records using byte positions
- Listing files and records with a few summary fields, without opening the JSON files
- Compact storage with minimal redundancy

The database does not index attribute values. Searching by annotation or feature qualifier goes through the Tantivy search index, a `tantivy.index` directory built next to the database in the same preprocessing run (see [Search Index](./search-index.md)).

Record boundaries and summary fields are found by the Rust `bgc_scanner` extension (`backend/rust_extensions`), which streams each file once. `.json.gz` and `.json.bz2` files are decompressed on the fly, and byte positions always refer to the decompressed content.

## Schema Structure

### Table: `metadata`

Stores global database metadata.

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Metadata key (PRIMARY KEY) |
| `value` | TEXT | Metadata value |

**Populated with:**
- `version`: Package version of bgc-viewer used to create the database
- `data_root`: Absolute path to the data directory containing the JSON files
- `creation_date`: ISO-formatted timestamp of database creation
- `modified_date`: ISO-formatted timestamp of last database modification

**Source in JSON:** Not from JSON files - generated during preprocessing

---

### Table: `files`

Stores file paths relative to the data root.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `path` | TEXT | File path relative to data_root (UNIQUE) |

**Populated with:**
- The relative path of each JSON file processed (e.g., `NC_003888.3.json`, `subdir/sample.json`)

**Source in JSON:** Not from JSON - derived from file system path

**Indexes:**
- `idx_files_path` on `path`

---

### Table: `file_attributes`

Stores file-level values from the top level of each JSON file.

| Column | Type | Description |
|--------|------|-------------|
| `file_id` | INTEGER | Foreign key to `files.id` |
| `attribute_name` | TEXT | `version` or `input_file` |
| `attribute_value` | TEXT | The value from the JSON file |

**Source in JSON:**
```json
{
  "version": "7.1.0",          // → attribute_name='version'
  "input_file": "NC_003888.3.gbk",  // → attribute_name='input_file'
  "records": [...]
}
```

A row is only written when the value is a string.

**Constraints:**
- UNIQUE(`file_id`, `attribute_name`, `attribute_value`)
- FOREIGN KEY to `files(id)` ON DELETE CASCADE

---

### Table: `records`

Stores record-level information and byte positions for fast random access.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `file_id` | INTEGER | Foreign key to `files.id` |
| `record_id` | TEXT | Record identifier from JSON |
| `byte_start` | INTEGER | Offset of the record's opening `{` in the (decompressed) file |
| `byte_end` | INTEGER | Offset just past the record's closing `}` |
| `description` | TEXT | Record description, or NULL |
| `organism` | TEXT | Organism of the record, or NULL |
| `feature_count` | INTEGER | Number of features in the record |
| `region_count` | INTEGER | Number of regions in the record |

**Populated with:**
- `file_id`: Link to the file in the `files` table
- `record_id`: From `records[].id`; `record_<n>` when the record has no string id
- `byte_start`, `byte_end`: Found by scanning the JSON file for record boundaries
- `description`: From `records[].description`
- `organism`: First `organism` qualifier of the first `source` feature that has one
- `feature_count`: Length of `records[].features`
- `region_count`: Length of `records[].regions` when present, otherwise the number of features with `type` `region`

**Source in JSON:**
```json
{
  "records": [
    {
      "id": "NC_003888.3",  // → record_id
      "description": "Streptomyces coelicolor A3(2) complete genome",  // → description
      "features": [  // → feature_count
        {
          "type": "source",
          "qualifiers": {"organism": ["Streptomyces coelicolor A3(2)"]}  // → organism
        },
        {"type": "region", ...},  // → counted in region_count
        ...
      ]
    }
  ]
}
```

**Constraints:**
- FOREIGN KEY to `files(id)` ON DELETE CASCADE

**Indexes:**
- `idx_records_file_id` on `file_id`
- `idx_records_record_id` on `record_id`

---

### Table: `search_examples`

Stores runnable example queries generated from the Tantivy index at the end of preprocessing. The search help popup serves them.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key; orders the examples |
| `template` | TEXT | Name of the template the example was generated from |
| `query` | TEXT | The example query |

---

## Entity Relationships

```
metadata (standalone - global settings)
search_examples (standalone - generated example queries)

files (1)
  ├── file_attributes (many) [file_id references files.id]
  └── records (many) [file_id references files.id]
```

## Query Examples

### Get all records for a file:
```sql
SELECT r.* 
FROM records r 
JOIN files f ON r.file_id = f.id 
WHERE f.path = 'NC_003888.3.json';
```

### Get the byte range of a record:
```sql
SELECT r.byte_start, r.byte_end
FROM records r
JOIN files f ON r.file_id = f.id
WHERE f.path = 'NC_003888.3.json' AND r.record_id = 'NC_003888.3';
```

### Count records per file:
```sql
SELECT f.path, COUNT(r.id) as record_count 
FROM files f 
LEFT JOIN records r ON r.file_id = f.id 
GROUP BY f.id, f.path;
```

## Performance Considerations

1. **Byte Positions**: The `byte_start` and `byte_end` columns in the `records` table enable fast random access to specific records without parsing the entire JSON file.

2. **Single-pass scanning**: The Rust scanner walks each file once in a streaming fashion, skipping string contents with SIMD search, so memory use does not grow with file size. Files are scanned in parallel threads.

3. **No attribute rows**: Attribute values are indexed only by Tantivy, so the SQLite database stays small, with a handful of rows per file.

4. **Foreign Keys with Cascade**: Deleting a file automatically removes all associated records and file attributes, maintaining referential integrity.

## Schema Version

This schema is used by bgc-viewer version 0.3.0 and later. The schema version can be checked via:
```sql
SELECT value FROM metadata WHERE key = 'version';
```
