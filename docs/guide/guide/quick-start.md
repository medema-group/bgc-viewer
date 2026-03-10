# Quick Start

Get up and running with BGC Viewer in minutes!

## Step 1: Start the Backend

```bash
cd backend
uv run python -m bgc_viewer.app
```

The API will be available at http://localhost:5000

## Step 2: Start the Frontend

In a new terminal:

```bash
cd frontend
npm run dev
```

The application will be available at http://localhost:5173

## Step 3: Load Data

### Preprocess AntiSMASH Data

First, preprocess your antiSMASH JSON files. If you are running the application
locally, you can run the preprocessing through the web interface by clicking
"Select folder to index". Alternatively, you can run the preprocessing from the command line:

```bash
cd backend
python -m bgc_viewer.preprocessing preprocess \
  --input ../data/NC_003888.json \
  --output ../data/processed/
```

### Access Through the UI

1. Open http://localhost:5173 in your browser
2. Navigate to the file browser
3. Select your preprocessed data
4. Explore the interactive visualization!

## Using the Track Viewer

### Basic Navigation

- **Zoom**: Use mouse wheel or pinch gesture
- **Pan**: Click and drag
- **Select**: Click on genes or domains
- **Viewer menu**: Right-click the menu button on the top right for options

## Example: Visualizing a BGC

```javascript
import { TrackViewer } from '@medemagroup/bgc-viewer-components';

const viewer = new TrackViewer({
  container: '#viewer',
  dataUrl: '/api/data/NC_003888'
});

viewer.render();
```

## Next Steps

- [Web Components Guide](../components/web-components.md)
- [Track Viewer Component](../components/track-viewer.md)
- [REST API Reference](../api/overview.md)
