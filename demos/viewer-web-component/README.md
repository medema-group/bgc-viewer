# BGC Viewer Web Components Demo

The BGC Viewer provides reusable web components for visualizing genomic data (antiSMASH output, but other formats also).

## Available Components

- **`<bgc-region-viewer-container>`** - Smart component that handles data loading and management (recommended for most cases)
- **`<bgc-region-viewer>`** - Pure presentation component for displaying genomic features (advanced usage)

## Quick Start

### 1. Load Required Dependencies and Web Components

```html
<!-- Required: D3.js and TrackViewer component -->
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="../../frontend/public/viewer-components.umd.js"></script>

<!-- Web components library -->
<script type="module" src="../../frontend/dist/web-components/bgc-viewer-components.es.js"></script>
<link rel="stylesheet" href="../../frontend/dist/web-components/style.css">
```

### 2. Use the Container Component (Recommended)

The container component handles all data loading automatically:

```html
<bgc-region-viewer-container
  id="viewer"
  record-id="NC_003888.3"
></bgc-region-viewer-container>

<script type="module">
  import '../../frontend/dist/web-components/bgc-viewer-components.es.js';
  
  // Create a data provider instance
  const provider = new BGCViewerComponents.JSONFileProvider({
    'NC_003888.3': '../data/NC_003888.3.json',
    'Y16952': '../data/Y16952.json'
  });
  
  // Set it on the component
  const viewer = document.getElementById('viewer');
  viewer.dataProvider = provider;
  
  // Set record data
  viewer.recordData = {
    entryId: 'NC_003888.3',
    recordId: 'NC_003888.3',
    filename: 'NC_003888.3.json'
  };
</script>
```

### 3. Use the Presentation Component (Advanced)

For full control over data loading, use the presentation component:

```html
<bgc-region-viewer id="viewer"></bgc-region-viewer>

<script>
  const viewer = document.getElementById('viewer');
  
  // You must provide all the data
  viewer.recordInfo = { recordId: '...', filename: '...', recordInfo: {...} };
  viewer.regions = [...];
  viewer.features = [...];
  viewer.pfamColorMap = {...};
</script>
```

## Events

Both components emit custom events that you can listen to:

- **`region-changed`** - Fired when the user selects a different region
- **`annotation-clicked`** - Fired when the user clicks on an annotation
- **`error`** - Fired when an error occurs

### Event Handling Example

```javascript
const viewer = document.getElementById('viewer');

viewer.addEventListener('region-changed', (event) => {
  console.log('Region changed to:', event.detail);
});

viewer.addEventListener('annotation-clicked', (event) => {
  console.log('Annotation clicked:', event.detail);
});

viewer.addEventListener('error', (event) => {
  console.error('Error:', event.detail);
});
```

## Data Providers

### JSONFileProvider

For standalone demos without a backend API:

```javascript
const provider = new BGCViewerComponents.JSONFileProvider({
  'NC_003888.3': '../data/NC_003888.3.json',
  'Y16952': '../data/Y16952.json',
  // Or use remote URLs
  'remote': 'https://antismash.secondarymetabolites.org/output/GCF_001457455.1/GCF_001457455.1.json'
});

viewer.dataProvider = provider;
```

### BGCViewerAPIProvider

For integration with the BGC Viewer backend API:

```javascript
const provider = new BGCViewerComponents.BGCViewerAPIProvider();
viewer.dataProvider = provider;
```

## Running the Demos

### Prerequisites

1. Build the web components:
   ```bash
   cd frontend
   npm run build:web-components
   ```

2. Start a web server from the repository root (required for ES modules):
   ```bash
   cd bgc-viewer
   python3 -m http.server 8080
   ```
   
   **Note:** The server must be started from the repository root to allow access to both the demo files and the built web components in `frontend/dist/web-components/`.

3. Open in browser:
   - Interactive test: http://localhost:8080/demos/viewer-web-component/index.html

### Demo Files

- **`viewer-web-component/index.html`** - Simple example on how to use the viewer component
- **`../data/`** - Sample JSON data files

## Component Properties

### bgc-region-viewer-container

| Property | Type | Description |
|----------|------|-------------|
| `dataProvider` | DataProvider | Data provider instance (JSONFileProvider or BGCViewerAPIProvider) |
| `recordData` | Object | Record metadata: `{ entryId, recordId, filename }` |
| `record-id` | String | Attribute to trigger loading |

### bgc-region-viewer

| Property | Type | Description |
|----------|------|-------------|
| `recordInfo` | Object | Record metadata and description |
| `regions` | Array | List of regions in the record |
| `features` | Array | Genomic features to display |
| `pfamColorMap` | Object | Pfam domain color mappings |
| `selectedRegionId` | String | Currently selected region ID |

## Framework Integration

These are standard web components and work with any framework:

### React
```jsx
import { useEffect, useRef } from 'react';

function BGCViewer() {
  const viewerRef = useRef(null);
  
  useEffect(() => {
    const viewer = viewerRef.current;
    viewer.dataProvider = new BGCViewerComponents.JSONFileProvider({...});
    viewer.recordData = { entryId: 'NC_003888.3', ... };
  }, []);
  
  return <bgc-region-viewer-container ref={viewerRef} />;
}
```

### Vue
```vue
<template>
  <bgc-region-viewer-container ref="viewer" />
</template>

<script setup>
import { ref, onMounted } from 'vue';

const viewer = ref(null);

onMounted(() => {
  viewer.value.dataProvider = new BGCViewerComponents.JSONFileProvider({...});
  viewer.value.recordData = { entryId: 'NC_003888.3', ... };
});
</script>
```

### Angular
```typescript
import { Component, ViewChild, ElementRef, AfterViewInit } from '@angular/core';

@Component({
  selector: 'app-bgc-viewer',
  template: '<bgc-region-viewer-container #viewer></bgc-region-viewer-container>'
})
export class BGCViewerComponent implements AfterViewInit {
  @ViewChild('viewer') viewer: ElementRef;
  
  ngAfterViewInit() {
    this.viewer.nativeElement.dataProvider = new BGCViewerComponents.JSONFileProvider({...});
    this.viewer.nativeElement.recordData = { entryId: 'NC_003888.3', ... };
  }
}
```

## Troubleshooting

### Components not registering
- Ensure you're using a web server (not `file://` protocol)
- Check that the build was successful in `frontend/dist/web-components/`

### Data not loading
- Verify the data provider is set before setting `recordData`
- Check browser console for error messages
- Ensure JSON files are in the correct location

### Styling issues
- Make sure to include the CSS file: `<link rel="stylesheet" href="../../frontend/dist/web-components/style.css">`
