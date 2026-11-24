# Quick Start

Get up and running with BGC Viewer in minutes!

## For End Users

### Step 1: Install BGC Viewer

Install the BGC Viewer package from PyPI:

```bash
pip install bgc-viewer
```

### Step 2: Run the Application

Start the BGC Viewer server:

```bash
bgc-viewer
```

The application will be available at http://localhost:5000

### Step 3: Load Your Data

1. Open http://localhost:5000 in your browser
2. Click **Index** in the header, then "Select folder to index" to preprocess your antiSMASH JSON files
3. Select your data folder and wait for preprocessing to complete
4. The records of the new index are listed under **Results**; search them with the query builder above
5. Click a result to view it below, and explore the interactive visualization!

To look at a few files without indexing them, or at an entry from antiSMASH DB or MIBiG,
click **Load data** in the header. Loaded records are listed in the **Loaded data** tab next to the search results.

## Basic Navigation

- **Zoom**: Use mouse wheel or pinch gesture
- **Pan**: Click and drag
- **Select**: Click on genes or domains
- **Viewer menu**: Right-click the menu button on the top right for options

## Need Help?

- [Developer Setup](./dev-setup.md) - If you want to contribute or modify the code
- [Configuration Options](./configuration.md) - Customize the application
- [REST API Reference](../api/overview.md) - Use BGC Viewer as an API
