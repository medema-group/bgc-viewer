# Database Schema Documentation

## Overview

The BGC Viewer uses a SQLite database to index and efficiently search antiSMASH JSON files. The schema is designed to support:
- Fast random access to specific records using byte positions
- Efficient file and record indexing
- Flexible attribute searching for record annotations and feature qualifiers
- Compact storage with minimal redundancy

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

### Table: `records`

Stores record-level information and byte positions for fast random access.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incrementing primary key |
| `file_id` | INTEGER | Foreign key to `files.id` |
| `record_id` | TEXT | Record identifier from JSON |
| `byte_start` | INTEGER | Starting byte position of record in file |
| `byte_end` | INTEGER | Ending byte position of record in file |

**Populated with:**
- `file_id`: Link to the file in the `files` table
- `record_id`: From JSON path `records[].id`
- `byte_start`, `byte_end`: Calculated by scanning the JSON file to find record boundaries

**Source in JSON:**
```json
{
  "records": [
    {
      "id": "NC_003888.3",  // → record_id
      ...
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

### Table: `attributes`

Stores searchable attributes extracted from record annotations and feature qualifiers.

| Column | Type | Description |
|--------|------|-------------|
| `record_id` | INTEGER | Foreign key to `records.id` |
| `attribute_name` | TEXT | Name/key of the attribute |
| `attribute_value` | TEXT | Value of the attribute (stored as text) |

**Populated with:**

Attributes are extracted from two sources within each record:

#### 1. Record Annotations:
- `record_id`: Links to `records.id`
- `attribute_name`, `attribute_value`: From flattened `annotations` object

**Source in JSON:**
```json
{
  "records": [
    {
      "id": "NC_003888.3",
      "annotations": {
        "molecule_type": "DNA",           // → attribute_name='molecule_type', attribute_value='DNA'
        "organism": "Streptomyces coelicolor A3(2)",  // → attribute_name='organism', attribute_value='Streptomyces coelicolor A3(2)'
        "topology": "linear"              // → attribute_name='topology', attribute_value='linear'
      }
    }
  ]
}
```

#### 2. Feature Qualifiers:
- `record_id`: Links to `records.id`
- All key-value pairs from feature `qualifiers` objects (excluding `translation` and values over 100 characters)

**Source in JSON:**
```json
{
  "records": [
    {
      "features": [
        {
          "type": "CDS",
          "qualifiers": {
            "locus_tag": "SC_RS00001",           // → attribute_name='locus_tag', attribute_value='SC_RS00001'
            "product": "hypothetical protein",   // → attribute_name='product', attribute_value='hypothetical protein'
            "db_xref": ["GeneID:123", "PF00001"] // → Multiple rows with attribute_name='db_xref'
          }
        }
      ]
    }
  ]
}
```

**Note:** The `translation` qualifier (which contains long amino acid sequences) is excluded to save space. Attribute values longer than 100 characters are also excluded.

**Constraints:**
- UNIQUE(`record_id`, `attribute_name`, `attribute_value`) - prevents duplicate entries
- FOREIGN KEY to `records(id)` ON DELETE CASCADE

**Indexes:**
- `idx_attributes_record_id` on `record_id`
- `idx_attributes_name` on `attribute_name`
- `idx_attributes_value` on `attribute_value`
- `idx_attributes_name_value` on `(attribute_name, attribute_value)`

---

## Entity Relationships

```
metadata (standalone - global settings)

files (1)
  └── records (many)
        └── attributes (many) [record_id references records.id]
```

## Data Flattening Rules

Complex nested structures in JSON are flattened into multiple attribute rows:

### Arrays
Each item in an array creates a separate row with the same `attribute_name`:
```json
"db_xref": ["GeneID:123", "PF00001"]
```
Creates two rows:
- `attribute_name='db_xref'`, `attribute_value='GeneID:123'`
- `attribute_name='db_xref'`, `attribute_value='PF00001'`

### Nested Objects
Keys are concatenated with underscores:
```json
"subregion": {
  "category": "biosynthetic"
}
```
Creates:
- `attribute_name='subregion_category'`, `attribute_value='biosynthetic'`

## Query Examples

### Get all records for a file:
```sql
SELECT r.* 
FROM records r 
JOIN files f ON r.file_id = f.id 
WHERE f.path = 'NC_003888.3.json';
```

### Search for records with a specific attribute value:
```sql
SELECT DISTINCT r.* 
FROM records r 
JOIN attributes a ON a.record_id = r.id 
WHERE a.attribute_value LIKE '%biosynthetic%';
```

### Search for records by attribute name and value:
```sql
SELECT DISTINCT r.* 
FROM records r 
JOIN attributes a ON a.record_id = r.id 
WHERE a.attribute_name = 'product' AND a.attribute_value = 'T1PKS';
```

### Get all unique attribute names:
```sql
SELECT DISTINCT attribute_name 
FROM attributes 
ORDER BY attribute_name;
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

2. **Indexes**: Comprehensive indexes on frequently queried columns ensure fast lookups and filtering.

3. **Compact Storage**: By excluding the `translation` qualifier and limiting attribute values to 100 characters, the database remains compact while retaining searchable data.

4. **Normalized Structure**: The simple three-table structure (`files`, `records`, `attributes`) provides efficient joins while avoiding the complexity of a fully polymorphic design.

5. **Unique Constraints**: The UNIQUE constraint on `(record_id, attribute_name, attribute_value)` prevents duplicate entries and reduces database size.

6. **Foreign Keys with Cascade**: Deleting a file automatically removes all associated records and attributes, maintaining referential integrity.

## Schema Version

This schema is used by bgc-viewer version 0.3.0 and later. The schema version can be checked via:
```sql
SELECT value FROM metadata WHERE key = 'version';
```
