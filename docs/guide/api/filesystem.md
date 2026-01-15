# File System API (Local Mode Only)

Endpoints for browsing the filesystem, scanning for files, and preprocessing data.

::: warning Local Mode Only
These endpoints are only available when running in Local Mode (`BGCV_PUBLIC_MODE=false`).
In Public Mode, they return 404 errors.
:::

## Browse Filesystem

Browse directories on the server's filesystem.

**Endpoint:** `GET /api/browse`

**Query Parameters:**
- `path` - Directory path to browse (default: current directory)

**Response:**
```json
{
  "current_path": "/absolute/path/to/directory",
  "items": [
    {
      "name": "..",
      "type": "directory",
      "path": "/absolute/path/to/parent"
    },
    {
      "name": "data",
      "type": "directory",
      "path": "/absolute/path/to/directory/data"
    },
    {
      "name": "example.json",
      "type": "file",
      "path": "/absolute/path/to/directory/example.json",
      "size": 1048576
    },
    {
      "name": "attributes.db",
      "type": "database",
      "path": "/absolute/path/to/directory/attributes.db",
      "size": 524288
    }
  ]
}
```

**Item Types:**
- `directory` - Folder
- `file` - JSON file (`.json`, `.json.gz`, `.json.bz2`)
- `database` - Database file (`.db`)

**Example:**
```javascript
const response = await fetch('/api/browse?path=/data/bgc');
const { current_path, items } = await response.json();

console.log(`Current directory: ${current_path}`);

items.forEach(item => {
  if (item.type === 'directory') {
    console.log(`📁 ${item.name}`);
  } else if (item.type === 'file') {
    console.log(`📄 ${item.name} (${formatBytes(item.size)})`);
  } else if (item.type === 'database') {
    console.log(`🗄️ ${item.name}`);
  }
});
```

**Error Responses:**

*Path not found:*
```json
{
  "error": "Path does not exist"
}
```

*Not a directory:*
```json
{
  "error": "Path is not a directory"
}
```

*Permission denied:*
```json
{
  "error": "Permission denied"
}
```

---

## Scan Folder for JSON Files

Recursively scan a folder for JSON files suitable for preprocessing.

**Endpoint:** `POST /api/scan-folder`

**Request Body:**
```json
{
  "path": "/path/to/data/folder"
}
```

**Response:**
```json
{
  "folder_path": "/absolute/path/to/folder",
  "scan_type": "recursive",
  "count": 42,
  "json_files": [
    {
      "name": "NC_003888.json",
      "path": "/absolute/path/to/folder/NC_003888.json",
      "relative_path": "NC_003888.json",
      "size": 2097152,
      "directory": "."
    },
    {
      "name": "Y16952.json",
      "path": "/absolute/path/to/folder/subdir/Y16952.json",
      "relative_path": "subdir/Y16952.json",
      "size": 1048576,
      "directory": "subdir"
    }
  ]
}
```

**Example:**
```javascript
const response = await fetch('/api/scan-folder', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    path: '/data/antismash_output'
  })
});

const { count, json_files } = await response.json();

console.log(`Found ${count} JSON files:`);
json_files.forEach(file => {
  console.log(`  ${file.relative_path} (${formatBytes(file.size)})`);
});
```

**Notes:**
- Scans recursively through all subdirectories
- Includes `.json`, `.json.gz`, and `.json.bz2` files
- Results are sorted by relative path

---

## Preprocess Folder

Start preprocessing antiSMASH JSON files to create a searchable database.

**Endpoint:** `POST /api/preprocess-folder`

**Request Body:**
```json
{
  "path": "/path/to/data/folder",
  "index_path": "/path/to/output/attributes.db",
  "files": [
    "/path/to/file1.json",
    "/path/to/file2.json"
  ]
}
```

**Fields:**
- `path` - Folder containing JSON files (required)
- `index_path` - Output database file path (required)
- `files` - Specific files to process (optional, defaults to all JSON in folder)

**Response:**
```json
{
  "message": "Preprocessing started",
  "total_files": 42,
  "folder_path": "/absolute/path/to/folder"
}
```

**Example:**
```javascript
// Start preprocessing
const response = await fetch('/api/preprocess-folder', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    path: '/data/antismash',
    index_path: '/data/index/attributes.db'
  })
});

const result = await response.json();
console.log(`Started processing ${result.total_files} files`);

// Poll for status
const checkStatus = async () => {
  const statusResponse = await fetch('/api/preprocessing-status');
  const status = await statusResponse.json();
  
  console.log(`Progress: ${status.files_processed}/${status.total_files}`);
  console.log(`Current: ${status.current_file}`);
  
  if (status.status === 'completed') {
    console.log('Preprocessing complete!');
  } else if (status.status === 'error') {
    console.error('Error:', status.error_message);
  } else {
    setTimeout(checkStatus, 1000);
  }
};

checkStatus();
```

**Error Responses:**

*Already running:*
```json
{
  "error": "Preprocessing is already running"
}
```

*Invalid folder:*
```json
{
  "error": "Invalid folder path"
}
```

*No JSON files found:*
```json
{
  "error": "No JSON files found in the folder"
}
```

---

## Get Preprocessing Status

Get the current status of a preprocessing operation.

**Endpoint:** `GET /api/preprocessing-status`

**Response:**
```json
{
  "is_running": true,
  "status": "running",
  "current_file": "NC_003888.json",
  "files_processed": 15,
  "total_files": 42,
  "folder_path": "/data/antismash",
  "error_message": null
}
```

**Status Values:**
- `idle` - No preprocessing in progress
- `running` - Currently processing
- `completed` - Successfully finished
- `error` - Failed with error

**Example:**
```javascript
const response = await fetch('/api/preprocessing-status');
const status = await response.json();

if (status.is_running) {
  const progress = (status.files_processed / status.total_files * 100).toFixed(1);
  console.log(`Processing: ${progress}%`);
  console.log(`Current file: ${status.current_file}`);
} else if (status.status === 'completed') {
  console.log('✓ Preprocessing complete');
} else if (status.status === 'error') {
  console.error('✗ Error:', status.error_message);
}
```

---

## Preprocessing Workflow

Complete example of the preprocessing workflow:

```javascript
class BGCPreprocessor {
  async scanFolder(folderPath) {
    const response = await fetch('/api/scan-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: folderPath })
    });
    return response.json();
  }

  async checkIndexExists(indexPath) {
    const response = await fetch('/api/check_file_exists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: indexPath })
    });
    const { exists } = await response.json();
    return exists;
  }

  async startPreprocessing(folderPath, indexPath, selectedFiles = null) {
    const response = await fetch('/api/preprocess-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: folderPath,
        index_path: indexPath,
        files: selectedFiles
      })
    });
    return response.json();
  }

  async waitForCompletion(onProgress) {
    return new Promise((resolve, reject) => {
      const checkStatus = async () => {
        const response = await fetch('/api/preprocessing-status');
        const status = await response.json();

        if (onProgress) {
          onProgress(status);
        }

        if (status.status === 'completed') {
          resolve(status);
        } else if (status.status === 'error') {
          reject(new Error(status.error_message));
        } else if (status.is_running) {
          setTimeout(checkStatus, 1000);
        }
      };
      
      checkStatus();
    });
  }

  async preprocessFolder(folderPath, indexPath) {
    // 1. Scan for files
    console.log('Scanning folder...');
    const scanResult = await this.scanFolder(folderPath);
    console.log(`Found ${scanResult.count} JSON files`);

    // 2. Check if index exists
    const exists = await this.checkIndexExists(indexPath);
    if (exists) {
      const overwrite = confirm('Index file exists. Overwrite?');
      if (!overwrite) return null;
    }

    // 3. Start preprocessing
    console.log('Starting preprocessing...');
    await this.startPreprocessing(folderPath, indexPath);

    // 4. Wait for completion
    const result = await this.waitForCompletion(status => {
      const progress = (status.files_processed / status.total_files * 100).toFixed(1);
      console.log(`Progress: ${progress}% - ${status.current_file || ''}`);
    });

    console.log('✓ Preprocessing complete!');
    return result;
  }
}

// Usage
const preprocessor = new BGCPreprocessor();
await preprocessor.preprocessFolder('/data/antismash', '/data/index/attributes.db');
```
