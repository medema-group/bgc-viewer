# Data Sources and Input Formats

BGC Viewer supports a number of different approaches for loading biosynthetic gene cluster (BGC) data. This guide explains how each data source works, supported file formats, and when to use each approach.

### 1. BGC Viewer API (Backend with Database)

A Flask backend that indexes and serves data from a directory containing antiSMASH JSON output files. If you're using the application on a public server, the data is fixed and you don't need to worry about creating an index. If you're running the application locally, you'll need to create the index yourself (see [Creating an Index](#creating-an-index)).

**Different modes of use**
- Runs locally for private use.
- Runs on a server so you can explore your (large) data remotely.
- Runs on a public server for demos or public datasets.

**Key Features:**
- Requires preprocessing/indexing of data directory
- Currently supports antiSMASH JSON format only
- Efficient searching and filtering across large datasets

**How it works:**
Run preprocessing through the user interface or through the command line to index a directory of antiSMASH JSON files (see [Creating an Index](#creating-an-index)). The data can then be explored. It is loaded on-demand from the indexed database.



### 2. Direct File Loading (Client-Side)

Load data files directly in the browser without uploading to a server.

**Key Features:**
- No server required - runs entirely in browser
- Files are never uploaded - processed locally
- Supports antiSMASH JSON and GenBank formats
- Best for single genomes or small collections
- Quick visualization without preprocessing

**How it works:**
1. User selects file(s) using browser file picker
2. Files are read and parsed in the browser
3. Data is stored in browser memory
4. Visualization happens entirely client-side

---

#### Creating an Index

The indexing process scans a directory for antiSMASH output files and creates a searchable SQLite database. This enables efficient searching and filtering across large datasets.

**Supported File Formats:**
- `.json` - antiSMASH JSON output
- `.json.gz` - Gzip-compressed JSON
- `.json.bz2` - Bzip2-compressed JSON

**Method 1: Command Line**

Use the preprocessing CLI tool to index a directory:

```bash
# Basic indexing
python -m bgc_viewer.preprocess_cli /path/to/antismash/output

# Specify output database location
python -m bgc_viewer.preprocess_cli \
    /path/to/antismash/output \
    --output /path/to/attributes.db

# Verbose output
python -m bgc_viewer.preprocess_cli /path/to/antismash/output --verbose
```

The tool will:
1. Scan the data directory for antiSMASH JSON files
2. Extract searchable attributes (cluster types, products, organisms, etc.)
3. Create/update the SQLite database file

**Method 2: User Interface**

When running BGC Viewer locally in LOCAL mode:

1. Start the application: `python -m bgc_viewer.app`
2. Navigate to the data management interface
3. Select the directory containing your antiSMASH output
4. Click "Index Directory" to start preprocessing
5. Monitor progress in the interface
6. Once complete, the indexed data is available for browsing

The UI method provides real-time feedback on indexing progress and any errors encountered.
