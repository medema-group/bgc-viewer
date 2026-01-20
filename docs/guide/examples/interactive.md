# Interactive Demo

Try out the BGC Viewer components with live, interactive examples.

<script setup>
import { ref } from 'vue'

const selectedGene = ref(null)
const zoomLevel = ref(1.0)
const showDomains = ref(true)
const showLabels = ref(true)

const handleGeneClick = (gene) => {
  selectedGene.value = gene
}

const handleZoomChange = (zoom) => {
  zoomLevel.value = zoom
}
</script>

## Live Demo

<div class="demo-container">
  <div class="controls">
    <label>
      <input type="checkbox" v-model="showDomains"> Show Domains
    </label>
    <label>
      <input type="checkbox" v-model="showLabels"> Show Labels
    </label>
    <span class="zoom-indicator">Zoom: {{ zoomLevel.toFixed(2) }}x</span>
  </div>

  <!-- Demo would load here in actual VitePress -->
  <div class="viewer-placeholder">
    <p>BGC Track Viewer Demo</p>
    <p><em>Interactive viewer would appear here</em></p>
  </div>

  <div v-if="selectedGene" class="gene-details">
    <h3>Selected Gene</h3>
    <dl>
      <dt>Name:</dt>
      <dd>{{ selectedGene.name }}</dd>
      <dt>Position:</dt>
      <dd>{{ selectedGene.start }} - {{ selectedGene.end }}</dd>
      <dt>Strand:</dt>
      <dd>{{ selectedGene.strand > 0 ? 'Forward' : 'Reverse' }}</dd>
    </dl>
  </div>
</div>

<style scoped>
.demo-container {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
}

.controls {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 10px;
  background: #f5f5f5;
  border-radius: 4px;
}

.controls label {
  display: flex;
  align-items: center;
  gap: 5px;
}

.zoom-indicator {
  margin-left: auto;
  font-weight: bold;
}

.viewer-placeholder {
  min-height: 300px;
  background: #f9f9f9;
  border: 2px dashed #ddd;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}

.gene-details {
  margin-top: 20px;
  padding: 15px;
  background: #f0f7ff;
  border-left: 4px solid #4a90e2;
  border-radius: 4px;
}

.gene-details h3 {
  margin-top: 0;
}

.gene-details dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  margin: 0;
}

.gene-details dt {
  font-weight: bold;
}

.gene-details dd {
  margin: 0;
}
</style>

## Code Example

Here's the code for the interactive demo above:

```vue
<template>
  <div class="demo-container">
    <div class="controls">
      <label>
        <input type="checkbox" v-model="showDomains"> Show Domains
      </label>
      <label>
        <input type="checkbox" v-model="showLabels"> Show Labels
      </label>
    </div>

    <TrackViewer
      :data="bgcData"
      :options="viewerOptions"
      @gene-click="handleGeneClick"
      @zoom-change="handleZoomChange"
    />

    <div v-if="selectedGene" class="gene-details">
      <h3>Selected Gene: {{ selectedGene.name }}</h3>
      <p>Position: {{ selectedGene.start }} - {{ selectedGene.end }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { TrackViewer } from 'bgc-viewer';

const showDomains = ref(true);
const showLabels = ref(true);
const selectedGene = ref(null);

const viewerOptions = computed(() => ({
  width: 900,
  height: 350,
  showDomains: showDomains.value,
  showLabels: showLabels.value
}));

const handleGeneClick = (gene) => {
  selectedGene.value = gene;
};

const handleZoomChange = (zoom) => {
  console.log('Zoom level:', zoom);
};
</script>
```

## Try It Yourself

You can experiment with different options:

- Toggle domain visibility
- Toggle labels
- Click on genes to see details
- Zoom and pan the view
- Export the visualization

## More Examples

Check out these additional examples:

- [Basic Usage](./basic.md)
- [Track Viewer Component](../components/track-viewer.md)
- [Web Components](../components/web-components.md)
