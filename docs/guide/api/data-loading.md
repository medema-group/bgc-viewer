# Data Loading API

Endpoints for managing data loading state and loading specific BGC entries.

## Get Status

Get current application status including loaded data information.

**Endpoint:** `GET /api/status`

**Response:**
```json
{
  "has_loaded_data": true,
  "current_data_directory": "/path/to/data",
  "public_mode": false
}
```

**Fields:**
- `has_loaded_data` - Whether data is currently loaded in session
- `current_data_directory` - Path to current data directory (or null)
- `public_mode` - Whether running in public mode

**Example:**
```javascript
const response = await fetch('/api/status');
const status = await response.json();

if (status.has_loaded_data) {
  console.log('Data loaded from:', status.current_data_directory);
}
```

---

## Load Entry

Load a specific BGC entry (file + record) from the database.

**Endpoint:** `POST /api/load-entry`

**Request Body:**
```json
{
  "id": "filename.json:record_id"
}
```

The entry ID format is `filename:record_id` where:
- `filename` - JSON file name (relative to data root)
- `record_id` - Specific record ID within the file

**Response:**
```json
{
  "message": "Successfully loaded filename.json:NC_003888.3",
  "filename": "filename.json",
  "record_id": "NC_003888.3",
  "record_info": {
    "id": "NC_003888.3",
    "description": "Streptomyces coelicolor A3(2) chromosome",
    "feature_count": 1247
  }
}
```

**Error Responses:**

*No database selected (Local Mode):*
```json
{
  "error": "No database selected. Please select a database first."
}
```

*File not found:*
```json
{
  "error": "File filename.json not found in database folder"
}
```

*Record not found:*
```json
{
  "error": "Record record_id not found in filename.json"
}
```

**Example:**
```javascript
const response = await fetch('/api/load-entry', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    id: 'NC_003888.json:NC_003888.3'
  })
});

const result = await response.json();
console.log(`Loaded ${result.record_info.feature_count} features`);
```

**Notes:**
- Entry data is cached for performance
- Session state is updated to track loaded entry
- Subsequent API calls will use this loaded data

---

## Get Version

Get application version information.

**Endpoint:** `GET /api/version`

**Response:**
```json
{
  "version": "0.2.0",
  "name": "BGC Viewer"
}
```

**Example:**
```javascript
const response = await fetch('/api/version');
const { version, name } = await response.json();
console.log(`${name} v${version}`);
```
