# Data Sources and Input Formats

BGC Viewer supports a number of different approaches for loading biosynthetic gene cluster (BGC) data. This guide explains how each data source works, supported file formats, and when to use each approach.

## Overview

BGC Viewer can access data through two distinct sources:

### 1. BGC Viewer API (Backend with Database)

A Flask backend that indexes and serves data from a directory containing antiSMASH JSON output files. If you're using the application on a public server, the data is fixed and you don't need to worry about creating an index. If you're running the application locally, you'll need to create the index yourself, either through the
command line or through the user interface in the application.

**Different modes of use**
- Runs locally for private use.
- Runs on a server so you can explore your (large) data remotely.
- Runs on a public server for demos or public datasets.

**Key Features:**
- Requires preprocessing/indexing of data directory
- Currently supports antiSMASH JSON format only
- Efficient searching and filtering across large datasets

**How it works:**
Run preprocessing through the user interface or through the command line to index a directory of antiSMASH JSON files. The data can then be explored. It is loaded on-demand from the indexed database.

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
