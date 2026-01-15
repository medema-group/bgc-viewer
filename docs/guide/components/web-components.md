# Web Components

BGC Viewer provides web components that can be easily integrated into any web application, regardless of framework.

## Installation

### Via npm

```bash
npm install bgc-viewer
```

### Via CDN

```html
<script type="module" src="https://unpkg.com/bgc-viewer@latest/dist/web-components.js"></script>
```

## Available Components

### `<bgc-track-viewer>`

The main track viewer component.

```html
<bgc-track-viewer
  data-url="/api/data/NC_003888"
  width="800"
  height="400"
  show-domains="true">
</bgc-track-viewer>
```

### `<bgc-gene-card>`

Display detailed information about a gene.

```html
<bgc-gene-card
  gene-id="gene_001"
  data-url="/api/gene/gene_001">
</bgc-gene-card>
```

## Usage Examples

### Plain HTML

```html
<!DOCTYPE html>
<html>
<head>
  <title>BGC Viewer Example</title>
  <script type="module" src="https://unpkg.com/bgc-viewer@latest/dist/web-components.js"></script>
</head>
<body>
  <h1>My BGC Visualization</h1>
  
  <bgc-track-viewer
    data-url="/data/my-bgc.json"
    width="1000"
    height="500">
  </bgc-track-viewer>

  <script>
    const viewer = document.querySelector('bgc-track-viewer');
    
    viewer.addEventListener('gene-click', (event) => {
      console.log('Gene clicked:', event.detail);
    });
  </script>
</body>
</html>
```

### React

```jsx
import 'bgc-viewer/web-components';

function BgcView() {
  const handleGeneClick = (event) => {
    console.log('Gene clicked:', event.detail);
  };

  return (
    <bgc-track-viewer
      data-url="/data/my-bgc.json"
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
  <bgc-track-viewer
    :data-url="dataUrl"
    :width="800"
    :height="400"
    @gene-click="handleGeneClick"
  />
</template>

<script setup>
import 'bgc-viewer/web-components';

const dataUrl = '/data/my-bgc.json';

const handleGeneClick = (event) => {
  console.log('Gene clicked:', event.detail);
};
</script>
```

### Angular

```typescript
import { Component, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import 'bgc-viewer/web-components';

@Component({
  selector: 'app-bgc-view',
  template: `
    <bgc-track-viewer
      [attr.data-url]="dataUrl"
      [attr.width]="800"
      [attr.height]="400"
      (gene-click)="handleGeneClick($event)">
    </bgc-track-viewer>
  `,
  schemas: [CUSTOM_ELEMENTS_SCHEMA]
})
export class BgcViewComponent {
  dataUrl = '/data/my-bgc.json';

  handleGeneClick(event: CustomEvent) {
    console.log('Gene clicked:', event.detail);
  }
}
```

## Styling

Web components can be styled using CSS custom properties:

```css
bgc-track-viewer {
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
- String attributes: `data-url`, `color-scheme`
- Number attributes: `width`, `height`

### Methods

Access methods via the element reference:

```javascript
const viewer = document.querySelector('bgc-track-viewer');

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
