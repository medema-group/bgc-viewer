# Basic Usage Example

This example demonstrates basic usage of the BGC Viewer components.

## Simple Track Viewer

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BGC Viewer - Basic Example</title>
  <script type="module" src="https://unpkg.com/bgc-viewer@latest/dist/web-components.js"></script>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    
    h1 {
      color: #333;
    }
    
    .viewer-container {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
    }
  </style>
</head>
<body>
  <h1>BGC Viewer - Basic Example</h1>
  
  <div class="viewer-container">
    <h2>Track Viewer</h2>
    <bgc-track-viewer
      data-url="/api/data/NC_003888"
      width="1000"
      height="400"
      show-domains="true">
    </bgc-track-viewer>
  </div>

  <script>
    // Add event listeners
    const viewer = document.querySelector('bgc-track-viewer');
    
    viewer.addEventListener('gene-click', (event) => {
      const gene = event.detail;
      alert(`Gene clicked: ${gene.name}\nStart: ${gene.start}\nEnd: ${gene.end}`);
    });
  </script>
</body>
</html>
```

## With Vue.js

```vue
<template>
  <div class="bgc-app">
    <h1>BGC Viewer Example</h1>
    
    <div class="controls">
      <button @click="zoomIn">Zoom In</button>
      <button @click="zoomOut">Zoom Out</button>
      <button @click="reset">Reset</button>
    </div>

    <TrackViewer
      ref="viewerRef"
      :data="bgcData"
      :options="viewerOptions"
      @gene-click="handleGeneClick"
      @domain-click="handleDomainClick"
    />

    <div v-if="selectedFeature" class="feature-info">
      <h3>{{ selectedFeature.type }}: {{ selectedFeature.name }}</h3>
      <pre>{{ JSON.stringify(selectedFeature, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { TrackViewer } from 'bgc-viewer';

const viewerRef = ref(null);
const bgcData = ref(null);
const selectedFeature = ref(null);

const viewerOptions = ref({
  width: 1000,
  height: 400,
  showDomains: true,
  showLabels: true,
  colorScheme: 'default'
});

onMounted(async () => {
  // Load BGC data
  const response = await fetch('/api/data/NC_003888');
  bgcData.value = await response.json();
});

const handleGeneClick = (gene) => {
  selectedFeature.value = { type: 'Gene', ...gene };
};

const handleDomainClick = (domain) => {
  selectedFeature.value = { type: 'Domain', ...domain };
};

const zoomIn = () => {
  viewerRef.value?.zoomIn();
};

const zoomOut = () => {
  viewerRef.value?.zoomOut();
};

const reset = () => {
  viewerRef.value?.reset();
};
</script>

<style scoped>
.bgc-app {
  padding: 20px;
}

.controls {
  margin: 20px 0;
}

.controls button {
  margin-right: 10px;
  padding: 8px 16px;
  background: #4a90e2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.controls button:hover {
  background: #357abd;
}

.feature-info {
  margin-top: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 4px;
}

.feature-info pre {
  background: white;
  padding: 10px;
  border-radius: 4px;
  overflow: auto;
}
</style>
```

## Programmatic Usage

```javascript
import { TrackViewer } from 'bgc-viewer';

// Create viewer instance
const viewer = new TrackViewer({
  container: '#viewer-container',
  data: bgcData,
  width: 1000,
  height: 400,
  options: {
    showDomains: true,
    showLabels: true,
    colorScheme: 'default'
  }
});

// Render
viewer.render();

// Add event listeners
viewer.on('gene-click', (gene) => {
  console.log('Gene clicked:', gene);
});

// Zoom to region
viewer.zoomTo({ start: 1000, end: 5000 });

// Export as SVG
const svg = viewer.exportSVG();
console.log('SVG:', svg);
```

## Next Steps

- [Interactive Demo](./interactive.md)
- [Component API](../components/track-viewer.md)
