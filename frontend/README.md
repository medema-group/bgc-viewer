# BGC Viewer Web Components

Framework-agnostic web components for visualizing biosynthetic gene cluster data.

For more details about the project structure and the stand-alone BGC Viewer, have a look at the project's [main readme](https://github.com/medema-group/bgc-viewer).

## Installation

```bash
npm install @kretep/bgc-viewer-components d3
```

**Note:** D3.js v7+ is a peer dependency and must be installed separately.

## Quick Start

### Using with ES Modules

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="node_modules/@kretep/bgc-viewer-components/dist/web-components/style.css">
</head>
<body>
  <bgc-region-viewer-container id="viewer"></bgc-region-viewer-container>

  <script src="https://d3js.org/d3.v7.min.js"></script>
  <script src="node_modules/bgc-viewer-components/public/viewer-components.umd.js"></script>
  
  <script type="module">
    import { JSONFileProvider } from '@kretep/bgc-viewer-components';
    
    // Load your antiSMASH JSON data
    const response = await fetch('path/to/antismash-output.json');
    const data = await response.json();
    
    // Create a data provider
    const provider = new JSONFileProvider(data);
    
    // Get the viewer element and configure it
    const viewer = document.getElementById('viewer');
    viewer.dataProvider = provider;
    viewer.setAttribute('record-id', data.records[0].id);
  </script>
</body>
</html>
```

### Using with a Bundler (Webpack, Vite, etc.)

```javascript
import '@kretep/bgc-viewer-components';
import '@kretep/bgc-viewer-components/style.css';

// The web components are now registered and ready to use
```

## Components

### `<bgc-region-viewer-container>`

The main container component that handles data loading and region selection.

**Properties:**
- `dataProvider` - Instance of a data provider (JSONFileProvider or BGCViewerAPIProvider)
- `record-id` - ID of the record to display
- `record-data` - Full record metadata (optional, for API provider)
- `initial-region-id` - ID of region to select initially (optional)

**Events:**
- `region-changed` - Emitted when user selects a different region
- `annotation-clicked` - Emitted when user clicks an annotation
- `error` - Emitted when an error occurs

## Data Providers

### JSONFileProvider

Load data directly from antiSMASH JSON output files:

```javascript
import { JSONFileProvider } from '@kretep/bgc-viewer-components';

const response = await fetch('data.json');
const jsonData = await response.json();
const provider = new JSONFileProvider(jsonData);
```

### BGCViewerAPIProvider

Connect to a BGC Viewer backend API:

```javascript
import { BGCViewerAPIProvider } from '@kretep/bgc-viewer-components';

const provider = new BGCViewerAPIProvider({
  baseURL: 'http://localhost:5000'
});
```

## TrackViewer

The package also exports a standalone `TrackViewer` class for creating custom genomic track visualizations with D3.js.

### Basic Usage

```javascript
import { TrackViewer } from '@kretep/bgc-viewer-components';

const viewer = new TrackViewer({
  container: '#viewer-container',
  domain: [0, 100],
  trackHeight: 30
});

viewer.setData({
  tracks: [
    { id: 'genes', label: 'Genes', height: 40 }
  ],
  annotations: [
    {
      id: 'gene1',
      trackId: 'genes',
      type: 'arrow',
      classes: ['gene'],
      label: 'geneA',
      start: 10,
      end: 30,
      direction: 'right'
    }
  ]
});
```

### TrackViewer API

See the [TrackViewer TypeScript types](src/TrackViewer.ts) for the complete API documentation.

## Example

See the [demos directory](https://github.com/medema-group/bgc-viewer/tree/main/demos/viewer-web-component) for a complete working example.

## Requirements

- D3.js v7 or higher (peer dependency)
- Modern browser with Web Components support

## Development

### Building from Source

```bash
# Install dependencies
npm install

# Build web components
npm run build:web-components

# Run tests
npm test

# Run tests with coverage
npm run test:coverage
```

### Project Structure

- `src/components/` - Vue components (RegionViewer, RegionViewerContainer)
- `src/services/dataProviders/` - Data provider implementations
- `src/TrackViewer.ts` - TrackViewer class for genomic track visualization
- `src/web-components.ts` - Web components entry point
- `dist/web-components/` - Built web components (after build)
- `demos/` - Example usage demonstrations

### Running the Demo

See the [demo README](../demos/viewer-web-component/README.md) for instructions on running a demo of the viewer component.

## License

Apache-2.0

## Links

- [GitHub Repository](https://github.com/medema-group/bgc-viewer)
- [Issue Tracker](https://github.com/medema-group/bgc-viewer/issues)
- [Full Documentation](https://github.com/medema-group/bgc-viewer#readme)
