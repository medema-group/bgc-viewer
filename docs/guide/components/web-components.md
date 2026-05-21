# Web Components

BGC Viewer provides web components that can be easily integrated into any web application, regardless of framework.

## Installation

### Via npm

```bash
npm install @medemagroup/bgc-viewer-components
```

### Via CDN

```html
<script type="module" src="https://unpkg.com/@medemagroup/bgc-viewer-components@latest/dist/web-components/bgc-viewer-components.es.js"></script>
```

## Available Components

### Custom Elements (Web Components)

#### `<bgc-region-viewer-container>`

Container component with automatic data loading. This is the simplest way to display a BGC record.

**Features:**
- Automatic data fetching from a DataProvider
- Built-in loading states and error handling
- Only requires `dataProvider` and `recordId` props
- Manages all data lifecycle (fetching regions, features, PFAM colors, etc.)

**Best for:**
- Simple integrations where you just want to display a record by ID
- Quick demos and prototypes
- When using standard data providers (JSONFileProvider or BGCViewerAPIProvider)

**Usage:**

```html
<bgc-region-viewer-container 
  record-id="NC_003888.3"
  width="1000"
  height="500">
</bgc-region-viewer-container>

<script type="module">
  import { JSONFileProvider } from '@medemagroup/bgc-viewer-components';

  const provider = new JSONFileProvider();
  await provider.loadFromFile('/data/bgc.json');

  const container = document.querySelector('bgc-region-viewer-container');
  // Complex objects must be set via JavaScript properties
  container.dataProvider = provider;
</script>
```

> **Note:** Simple values (strings, numbers, booleans) can be set as HTML attributes. Complex objects like `dataProvider` must be set via JavaScript properties.

#### `<bgc-region-viewer>`

Core visualization component for displaying biosynthetic gene clusters.

**Features:**
- Region selector dropdown for switching between BGC regions
- Multi-select track dropdown for showing/hiding feature layers
- Interactive feature details panel (click features to see info)
- Full control over what data is displayed and when

**Best for:**
- When you have pre-loaded data or custom data sources
- Complex applications with state management
- Custom data loading logic or transformations
- Fine-grained control over rendering and updates

**Usage:**

```html
<bgc-region-viewer
  width="800"
  height="400"
  show-domains="true">
</bgc-region-viewer>

<script type="module">
  // RegionViewer requires pre-loaded data passed as props
  const viewer = document.querySelector('bgc-region-viewer');
  viewer.recordInfo = { recordId: 'NC_003888.3', filename: 'bgc.json' };
  viewer.regions = [/* array of regions */];
  viewer.features = [/* array of features */];
  viewer.pfamColorMap = {/* domain colors */};
</script>
```

### Choosing Between Components

| Aspect | RegionViewerContainer | RegionViewer |
|--------|----------------------|--------------|
| **Setup Complexity** | Simple (2 props) | More complex (many props) |
| **Data Loading** | Automatic | Manual |
| **Flexibility** | Limited | High |
| **Use Case** | Quick display by ID | Custom data flows |
| **Best For** | Demos, simple apps | Complex apps, custom logic |

### Exported Classes

The package also exports JavaScript classes for programmatic use:

#### `BGCViewerAPIProvider`

Data provider class for fetching data from the BGC Viewer REST API.

```javascript
import { BGCViewerAPIProvider } from '@medemagroup/bgc-viewer-components';

const provider = new BGCViewerAPIProvider('http://localhost:8000');
const data = await provider.fetchRegion('NC_003888');
```

#### `JSONFileProvider`

Data provider class for loading data from JSON files.

```javascript
import { JSONFileProvider } from '@medemagroup/bgc-viewer-components';

const provider = new JSONFileProvider();
const data = await provider.loadFromFile('/data/bgc.json');
```

#### `TrackViewer`

Low-level track viewer class for direct canvas-based rendering.

```javascript
import { TrackViewer } from '@medemagroup/bgc-viewer-components';

const viewer = new TrackViewer({
  container: '#viewer',
  width: 800,
  height: 400
});
viewer.render(data);
```

### TypeScript Types

The following TypeScript types are exported for type-safe development:

- `TrackViewerConfig` - Configuration options for TrackViewer
- `TrackData` - Track data structure
- `AnnotationData` - Annotation data structure
- `AnnotationType` - Annotation type enum
- `TrackViewerData` - Complete viewer data structure
- `DrawingPrimitive` - Drawing primitive interface
- `DrawingPrimitiveType` - Drawing primitive type enum

## Usage Examples

### Plain HTML

```html
<!DOCTYPE html>
<html>
<head>
  <title>BGC Viewer Example</title>
  <script type="module" src="https://unpkg.com/@medemagroup/bgc-viewer-components@latest/dist/web-components/bgc-viewer-components.es.js"></script>
</head>
<body>
  <h1>My BGC Visualization</h1>
  
  <bgc-region-viewer-container id="viewer" width="1000" height="500">
  </bgc-region-viewer-container>

  <script type="module">
    import { JSONFileProvider } from 'https://unpkg.com/@medemagroup/bgc-viewer-components@latest/dist/web-components/bgc-viewer-components.es.js';

    const provider = new JSONFileProvider();
    await provider.loadFromFile('/data/my-bgc.json');

    const viewer = document.getElementById('viewer');
    viewer.dataProvider = provider;
    viewer.setAttribute('record-id', 'NC_003888.3'); // record ID from your JSON file

    viewer.addEventListener('gene-click', (event) => {
      console.log('Gene clicked:', event.detail);
    });
  </script>
</body>
</html>
```

### React

```jsx
import { useEffect, useRef } from 'react';
import { JSONFileProvider } from '@medemagroup/bgc-viewer-components';

function BgcView() {
  const viewerRef = useRef(null);

  useEffect(() => {
    const viewer = viewerRef.current;
    const provider = new JSONFileProvider();
    provider.loadFromFile('/data/my-bgc.json').then(() => {
      viewer.dataProvider = provider;
      viewer.setAttribute('record-id', 'NC_003888.3'); // record ID from your JSON file
    });
  }, []);

  const handleGeneClick = (event) => {
    console.log('Gene clicked:', event.detail);
  };

  return (
    <bgc-region-viewer-container
      ref={viewerRef}
      width="800"
      height="400"
      onGene-click={handleGeneClick}
    />
  );
}
```

### Vue

```vue
<template>
  <bgc-region-viewer-container
    ref="viewer"
    :width="800"
    :height="400"
    @gene-click="handleGeneClick"
  />
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { JSONFileProvider } from '@medemagroup/bgc-viewer-components';

const viewer = ref(null);

onMounted(async () => {
  const provider = new JSONFileProvider();
  await provider.loadFromFile('/data/my-bgc.json');
  viewer.value.dataProvider = provider;
  viewer.value.setAttribute('record-id', 'NC_003888.3'); // record ID from your JSON file
});

const handleGeneClick = (event) => {
  console.log('Gene clicked:', event.detail);
};
</script>
```

### Angular

```typescript
import { Component, ViewChild, ElementRef, AfterViewInit, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { JSONFileProvider } from '@medemagroup/bgc-viewer-components';

@Component({
  selector: 'app-bgc-view',
  template: `
    <bgc-region-viewer-container
      #viewer
      [attr.width]="800"
      [attr.height]="400"
      (gene-click)="handleGeneClick($event)">
    </bgc-region-viewer-container>
  `,
  schemas: [CUSTOM_ELEMENTS_SCHEMA]
})
export class BgcViewComponent implements AfterViewInit {
  @ViewChild('viewer') viewer!: ElementRef;

  ngAfterViewInit() {
    const provider = new JSONFileProvider();
    provider.loadFromFile('/data/my-bgc.json').then(() => {
      this.viewer.nativeElement.dataProvider = provider;
      this.viewer.nativeElement.setAttribute('record-id', 'NC_003888.3'); // record ID from your JSON file
    });
  }

  handleGeneClick(event: CustomEvent) {
    console.log('Gene clicked:', event.detail);
  }
}
```

## Styling

Web components can be styled using CSS custom properties:

```css
bgc-region-viewer {
  --gene-stroke: #333;
  --gene-fill: #4a90e2;
  --domain-stroke: #666;
  --domain-fill: #f39c12;
  --background: #ffffff;
  --text-color: #333;
  --font-family: 'Arial', sans-serif;
}
```

## API

### Properties

All web components support attribute-based configuration:

- Boolean attributes: `show-domains`, `show-labels`
- String attributes: `record-id`, `color-scheme`
- Number attributes: `width`, `height`
- JS-only properties: `dataProvider` (DataProvider instance)

### Methods

Access methods via the element reference:

```javascript
const viewer = document.querySelector('bgc-region-viewer');

// Zoom to region
viewer.zoomTo({ start: 1000, end: 5000 });

// Reset view
viewer.reset();

// Export as SVG
const svg = viewer.exportSVG();
```

### Events

Listen to custom events:

```javascript
viewer.addEventListener('gene-click', (event) => {
  console.log('Gene:', event.detail.gene);
});

viewer.addEventListener('zoom-change', (event) => {
  console.log('Zoom level:', event.detail.zoom);
});
```

## See Also

- [Track Viewer Component](./track-viewer.md)
- [Interactive Examples](../examples/interactive.md)
