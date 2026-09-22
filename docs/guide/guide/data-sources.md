# Data sources and input formats

BGC Viewer supports two main approaches for exploring biosynthetic gene cluster (BGC) data. Choose the approach that best fits your needs.

## Quick reference

| Approach | When to use | Supported formats |
|----------|------------|-------------------|
| **Direct file loading** | Quick exploration of a few files, no setup needed | antiSMASH JSON, GenBank |
| **Backend API with database** | Large datasets, persistent access, advanced search | antiSMASH JSON (preprocessed) |

## Direct file loading (client-side)

The fastest way to get started. Upload files directly in your browser—no server or preprocessing required.

**How it works:** Select one or more files using the file picker or drag them into the upload area. Files are read and processed in your browser, and data stays on your computer. Perfect for quick visualization without any setup.

**Supported formats:**
- antiSMASH JSON files (`.json`)
- GenBank format files (`.gb`, `.gbk`, `.genbank`)

**Best for:**
- Exploring a few genomes quickly
- Testing the viewer
- Analyzing single-genome results

## BGC Viewer API (Backend with Database)

For larger datasets or when you want persistent access to your data with powerful search capabilities.

**How it works:** Index a directory of antiSMASH JSON files once, then explore them through the web interface. The backend creates a searchable database, enabling efficient filtering and search across your entire dataset.

**Supported formats:**
- antiSMASH JSON files (`.json`)
- Gzip-compressed JSON (`.json.gz`)
- Bzip2-compressed JSON (`.json.bz2`)

**Best for:**
- Exploring large collections of antiSMASH results
- Running on a server for remote access
- Persistent data exploration across sessions


## Setting up the backend

If you're working with a large dataset or want to host the viewer on a server, you'll need to index your data first.

### Command line

```bash
# Index a directory of antiSMASH output files
python -m bgc_viewer.preprocess_cli /path/to/antismash/output

# Specify where to save the database
python -m bgc_viewer.preprocess_cli \
    /path/to/antismash/output \
    --output /path/to/attributes.db

# Verbose output for debugging
python -m bgc_viewer.preprocess_cli /path/to/antismash/output --verbose
```

The preprocessing tool will scan your directory for antiSMASH JSON files and create a searchable SQLite database containing extracted metadata (cluster types, products, organisms, etc.).

### Using the user interface

When running BGC Viewer locally:

1. Start the application: `python -m bgc_viewer.app`
2. Navigate to the data management section
3. Select the directory containing your antiSMASH output
4. Click "Index Directory" to start preprocessing
5. Monitor progress in the interface
6. Once complete, your indexed data is ready to explore

The UI method provides real-time progress feedback and error messages if anything goes wrong during indexing.
