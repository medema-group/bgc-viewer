# REST API Overview

The BGC Viewer backend provides a RESTful API for accessing the biosynthetic gene cluster data.

::: information Backend is optional
The backend is not required to use the BGC Viewer components in a web application. Other data sources are still available without it. Alternatively, a custom API could be provided that is tailored to your needs.
:::


## Base URL

When running locally:
```
http://localhost:5005/api
```

## Response Format

All API responses are in JSON format. Successful responses typically include the requested data, while errors return:

```json
{
  "error": "Error message description"
}
```

## Operating Modes

BGC Viewer can run in two modes:

### Local Mode (Default)
- Full filesystem access
- Database selection and preprocessing
- Session-based data management
- Development and single-user deployments

### Public Mode
- Restricted to pre-configured data
- No filesystem browsing
- Multi-user support with Redis sessions
- Production deployments

Set via environment variable:
```bash
export BGCV_PUBLIC_MODE=true
```

## Authentication

Currently, BGC Viewer does not require authentication. Sessions are used to track user state (loaded data, selected database, etc.).

## Pagination

Endpoints that return lists support pagination:

**Query Parameters:**
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 50, max: 100)

**Response Format:**
```json
{
  "page": 1,
  "per_page": 50,
  "total": 150,
  "total_pages": 3,
  "items": [...]
}
```

## Search

Some endpoints support text search via the `search` query parameter:

```
GET /api/database-entries?search=biosynthetic
```

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 403 | Forbidden - Access denied |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Resource state conflict |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Session storage issue |

## API Sections

- **[Data Loading](./data-loading.md)** - Loading and managing BGC data
- **[Records & Features](./records.md)** - Accessing genomic features and annotations
- **[Database](./database.md)** - Database management and queries
- **[File System](./filesystem.md)** - File browsing and preprocessing (Local Mode only)

## Quick Example

```javascript
// Check API status
const response = await fetch('http://localhost:5005/api/status');
const status = await response.json();

console.log(status);
// {
//   "has_loaded_data": false,
//   "current_data_directory": null,
//   "public_mode": false
// }

// Get API version
const version = await fetch('http://localhost:5005/api/version');
const versionData = await version.json();

console.log(versionData);
// {
//   "version": "0.2.0",
//   "name": "BGC Viewer"
// }
```

## Rate Limiting

Currently, there are no rate limits implemented. For public deployments, consider implementing rate limiting at the reverse proxy level.

## CORS

In Local Mode, CORS allows all origins. In Public Mode, configure allowed origins via:

```bash
export BGCV_ALLOWED_ORIGINS="https://example.com,https://app.example.com"
```
