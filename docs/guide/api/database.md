# Database API

Endpoints for managing and querying the preprocessed BGC database.

## Get Database Entries

Get a paginated list of all entries in the current database.

**Endpoint:** `GET /api/database-entries`

**Query Parameters:**
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 50, max: 100)
- `search` - Text search filter (optional)

**Response:**
```json
{
  "page": 1,
  "per_page": 50,
  "total": 150,
  "total_pages": 3,
  "entries": [
    {
      "id": "NC_003888.json:NC_003888.3",
      "filename": "NC_003888.json",
      "record_id": "NC_003888.3",
      "description": "Streptomyces coelicolor A3(2) chromosome",
      "organism": "Streptomyces coelicolor A3(2)",
      "length": 8667507,
      "regions": 28
    }
  ],
  "search_query": ""
}
```

**Example - Basic Pagination:**
```javascript
const response = await fetch('/api/database-entries?page=1&per_page=25');
const data = await response.json();

console.log(`Page ${data.page} of ${data.total_pages}`);
console.log(`Total entries: ${data.total}`);

data.entries.forEach(entry => {
  console.log(`${entry.record_id}: ${entry.description}`);
});
```

**Example - Search:**
```javascript
const response = await fetch('/api/database-entries?search=Streptomyces&per_page=50');
const data = await response.json();

console.log(`Found ${data.total} matching entries`);
```

**Error Responses:**

*No database selected (Local Mode):*
```json
{
  "error": "No database selected. Please select a database first."
}
```

*Database file not found:*
```json
{
  "error": "Database file does not exist: /path/to/db.db"
}
```

---

## Select Database (Local Mode Only)

Select and load database metadata. Sets the active database for the current session.

**Endpoint:** `POST /api/select-database`

**Request Body:**
```json
{
  "path": "/path/to/attributes.db"
}
```

**Response:**
```json
{
  "message": "Database selected successfully",
  "database_path": "/path/to/attributes.db",
  "data_root": "/path/to/data",
  "index_stats": {
    "total_files": 42,
    "total_records": 150,
    "total_regions": 523
  },
  "version": "0.2.0"
}
```

**Fields:**
- `database_path` - Full path to the database file
- `data_root` - Root directory containing the JSON data files
- `index_stats` - Statistics about indexed data
- `version` - BGC Viewer version used to create the index

**Example:**
```javascript
const response = await fetch('/api/select-database', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    path: '/data/bgc_index/attributes.db'
  })
});

const result = await response.json();
console.log(`Loaded database with ${result.index_stats.total_records} records`);
console.log(`Data root: ${result.data_root}`);
```

**Error Responses:**

*Database file not found:*
```json
{
  "error": "Database file does not exist: /path/to/db.db"
}
```

*Invalid database:*
```json
{
  "error": "Invalid database file or missing metadata table"
}
```

---

## Check File Exists (Local Mode Only)

Check if a file exists at the given path. Useful for validating paths before preprocessing.

**Endpoint:** `POST /api/check_file_exists`

**Request Body:**
```json
{
  "path": "/path/to/file.db"
}
```

**Response:**
```json
{
  "exists": true
}
```

**Example:**
```javascript
const response = await fetch('/api/check_file_exists', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    path: '/data/index/attributes.db'
  })
});

const { exists } = await response.json();

if (exists) {
  const overwrite = confirm('File exists. Overwrite?');
  if (!overwrite) return;
}
```

---

## Notes

### Database Format

The database is a SQLite file created during preprocessing. It contains:
- Metadata table (data_root, version, timestamps)
- Entries table (filename, record_id, attributes)
- Indexes for fast searching

### Session State

In Local Mode, the selected database is stored in the session. Different users/sessions can work with different databases simultaneously.

### Public Mode

In Public Mode, the database path is fixed and configured via environment variables:
- `BGCV_INDEX_FILENAME` - Database filename (default: `attributes.db`)
- Database must be located in `/index` directory (Docker mount)
- Data files must be in `/data_root` directory (Docker mount)
