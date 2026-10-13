# BGC Viewer Web Components Demo

The BGC Viewer provides reusable web components for visualizing genomic data (antiSMASH output, but other formats also).

## Available Components

- **`<bgc-region-viewer-container>`** - Smart component that handles data loading and management (recommended for most cases)
- **`<bgc-region-viewer>`** - Pure presentation component for displaying genomic features (advanced usage)


## Running the Demos

### Prerequisites

1. Build the web components:
   ```bash
   cd frontend
   npm run build:web-components
   ```

2. Start a web server from the repository root (required for ES modules):
   ```bash
   python3 -m http.server 8080
   ```
   
   **Note:** The server must be started from the repository root to allow access to both the demo files and the built web components in `frontend/dist/web-components/`.

3. Open in browser:
   ```
   http://localhost:8080/demos/viewer-web-component/index.html
   ```

### Demo Files

- **`viewer-web-component/index.html`** - Interactive test page showing how to use the viewer component
- **`../data/`** - Sample JSON data files (NC_003888.3.json, Y16952.json)

## Quick Start

### 1. Load Required Dependencies and Web Components

```html
<!-- Required: D3.js -->
<script src="https://d3js.org/d3.v7.min.js"></script>

<!-- Required: Vue (as a peer dependency of the web components) -->
<script src="https://unpkg.com/vue@3.3.0/dist/vue.global.prod.js"></script>

<!-- Import map for module resolution (required for module imports) -->
<script type="importmap">
{
  "imports": {
    "vue": "https://unpkg.com/vue@3.3.0/dist/vue.esm-browser.prod.js",
    "d3": "https://cdn.jsdelivr.net/npm/d3@7/+esm"
  }
}
</script>

<!-- Web components library and styles -->
<script type="module">
  import { JSONFileProvider } from '../../frontend/dist/web-components/bgc-viewer-components.es.js';
  window.JSONFileProvider = JSONFileProvider;
</script>
<link rel="stylesheet" href="../../frontend/dist/web-components/style.css">
```

### 2. Use the Container Component (Recommended)

The container component handles all data loading automatically:

```html
<bgc-region-viewer-container id="viewer"></bgc-region-viewer-container>

<script>
  async function loadRecord(jsonUrl, recordId) {
    const viewer = document.getElementById('viewer');
    
    // Fetch the JSON data
    const response = await fetch(jsonUrl);
    const jsonData = await response.json();
    
    // Create a data provider instance
    const provider = new window.JSONFileProvider(jsonData);
    viewer.dataProvider = provider;
    
    // Get the first record from the JSON
    const firstRecordId = jsonData.records?.[0]?.id || recordId;
    const filename = jsonUrl.split('/').pop();
    
    // Set record data
    viewer.recordData = {
      entryId: `${filename}:${firstRecordId}`,
      recordId: firstRecordId,
      filename: filename
    };
    
    // Trigger loading by setting the recordId attribute
    viewer.setAttribute('record-id', firstRecordId);
  }
  
  // Load a record
  loadRecord('../data/NC_003888.3.json', 'NC_003888.3');
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

For standalone demos without a backend API, create a provider instance with the loaded JSON data:

```javascript
// First, fetch the JSON data
const response = await fetch('../data/NC_003888.3.json');
const jsonData = await response.json();

// Create a provider instance with the data
const provider = new JSONFileProvider(jsonData);
viewer.dataProvider = provider;
```

### BGCViewerAPIProvider

For integration with the BGC Viewer backend API:

```javascript
const provider = new BGCViewerComponents.BGCViewerAPIProvider();
viewer.dataProvider = provider;
```


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
    const loadData = async () => {
      const viewer = viewerRef.current;
      const response = await fetch('../data/NC_003888.3.json');
      const jsonData = await response.json();
      
      const provider = new window.JSONFileProvider(jsonData);
      viewer.dataProvider = provider;
      
      const firstRecordId = jsonData.records?.[0]?.id;
      viewer.recordData = { 
        entryId: firstRecordId, 
        recordId: firstRecordId, 
        filename: 'NC_003888.3.json' 
      };
      viewer.setAttribute('record-id', firstRecordId);
    };
    
    loadData();
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

onMounted(async () => {
  const response = await fetch('../data/NC_003888.3.json');
  const jsonData = await response.json();
  
  const provider = new window.JSONFileProvider(jsonData);
  viewer.value.dataProvider = provider;
  
  const firstRecordId = jsonData.records?.[0]?.id;
  viewer.value.recordData = { 
    entryId: firstRecordId, 
    recordId: firstRecordId, 
    filename: 'NC_003888.3.json' 
  };
  viewer.value.setAttribute('record-id', firstRecordId);
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
  
  async ngAfterViewInit() {
    const response = await fetch('../data/NC_003888.3.json');
    const jsonData = await response.json();
    
    const provider = new (window as any).JSONFileProvider(jsonData);
    this.viewer.nativeElement.dataProvider = provider;
    
    const firstRecordId = jsonData.records?.[0]?.id;
    this.viewer.nativeElement.recordData = { 
      entryId: firstRecordId, 
      recordId: firstRecordId, 
      filename: 'NC_003888.3.json' 
    };
    this.viewer.nativeElement.setAttribute('record-id', firstRecordId);
  }
}
```

## Troubleshooting

### Components not registering or CORS errors
- **Ensure you're using a web server** (not `file://` protocol) — see "Running the Demos" section
- Check that the build was successful in `frontend/dist/web-components/`
- Browser console should show: "✅ Web components loaded successfully"

### Data not loading
- Verify the web server is started from the repository root
- Check browser console for error messages
- Ensure JSON files are in the correct location: `demos/data/`
- Verify the data provider is set BEFORE setting `recordData`

### Styling issues
- Make sure to include the CSS file: `<link rel="stylesheet" href="../../frontend/dist/web-components/style.css">`
- Check that D3.js is loaded: `<script src="https://d3js.org/d3.v7.min.js"></script>`
