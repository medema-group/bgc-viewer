# Track Viewer Component

The Track Viewer is the main interactive component for visualizing biosynthetic gene clusters.

## Overview

The Track Viewer provides a zoomable, pannable interface for exploring gene clusters with annotations, domains, and other features.

## Basic Usage

### As a Vue Component

```vue
<template>
  <TrackViewer
    :data="bgcData"
    :options="viewerOptions"
    @gene-click="handleGeneClick"
  />
</template>

<script setup>
import { TrackViewer } from 'bgc-viewer';
import { ref } from 'vue';

const bgcData = ref(null);
const viewerOptions = ref({
  width: 800,
  height: 400,
  showDomains: true
});

const handleGeneClick = (gene) => {
  console.log('Gene clicked:', gene);
};
</script>
```

### As a Web Component

```html
<script type="module">
  import 'bgc-viewer/web-components';
</script>

<bgc-track-viewer
  data-url="/api/data/NC_003888"
  width="800"
  height="400">
</bgc-track-viewer>
```

## Props / Attributes

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `data` | Object | null | BGC data object |
| `dataUrl` | String | null | URL to fetch BGC data |
| `width` | Number | 800 | Viewer width in pixels |
| `height` | Number | 400 | Viewer height in pixels |
| `showDomains` | Boolean | true | Show protein domains |
| `showLabels` | Boolean | true | Show gene labels |
| `colorScheme` | String | 'default' | Color scheme name |

## Events

| Event | Payload | Description |
|-------|---------|-------------|
| `gene-click` | Gene object | Fired when a gene is clicked |
| `domain-click` | Domain object | Fired when a domain is clicked |
| `region-select` | Region object | Fired when a region is selected |
| `zoom-change` | Zoom level | Fired when zoom level changes |

## Interactive Demo

::: demo Track Viewer Demo

```vue
<template>
  <div>
    <TrackViewer
      :data="sampleData"
      :options="options"
      @gene-click="selectedGene = $event"
    />
    <div v-if="selectedGene" class="gene-info">
      <h3>Selected Gene: {{ selectedGene.name }}</h3>
      <p>{{ selectedGene.description }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const sampleData = ref({
  // Sample BGC data
});

const options = ref({
  width: 700,
  height: 300
});

const selectedGene = ref(null);
</script>
```

:::

## Customization

### Color Schemes

You can customize colors using CSS variables:

```css
bgc-track-viewer {
  --gene-color: #4a90e2;
  --domain-color: #f39c12;
  --background-color: #ffffff;
}
```

### Custom Renderers

```javascript
const viewer = new TrackViewer({
  customRenderers: {
    gene: (gene, ctx) => {
      // Custom gene rendering logic
    },
    domain: (domain, ctx) => {
      // Custom domain rendering logic
    }
  }
});
```

## API Reference

### Methods

#### `render()`

Renders or re-renders the visualization.

```javascript
viewer.render();
```

#### `zoomTo(region)`

Zooms to a specific genomic region.

```javascript
viewer.zoomTo({ start: 1000, end: 5000 });
```

#### `reset()`

Resets the view to initial state.

```javascript
viewer.reset();
```

#### `exportSVG()`

Exports the current view as SVG.

```javascript
const svg = viewer.exportSVG();
```

## See Also

- [Web Components Guide](./web-components.md)
- [Interactive Examples](../examples/interactive.md)
