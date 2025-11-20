# TrackViewer Demo

This demo shows the `TrackViewer` class from `@kretep/bgc-viewer-components` for creating custom genomic track visualizations.

## Features Demonstrated

- **Multiple track types**: Genes, regulatory elements, protein domains
- **Per-track height customization**: Different tracks can have different heights
- **Various annotation types**: Arrows, boxes, circles, triangles, pins
- **Drawing primitives**: Horizontal lines and backgrounds
- **Interactive features**: Zoom, pan, click handlers, hover tooltips
- **Dynamic updates**: Add tracks and update domain at runtime

## Running the Demo

1. **Build the web components** (from the repository root):
   ```bash
   cd frontend
   npm install
   npm run build:web-components
   ```

2. **Open the demo** in your browser:
   ```bash
   open demos/track-viewer/index.html
   # or just double-click the file
   ```

## Usage Example

```javascript
import { TrackViewer } from '@kretep/bgc-viewer-components';

const viewer = new TrackViewer({
  container: '#viewer-container',
  domain: [0, 100],
  trackHeight: 30,
  onAnnotationClick: (annotation, track) => {
    console.log(`Clicked ${annotation.label}`);
  }
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

## API Documentation

See the [TrackViewer TypeScript source](../../frontend/src/TrackViewer.ts) for complete API documentation.

## Annotation Types

- **arrow**: Directional gene arrow with optional left/right direction
- **box**: Rectangle with optional rounded corners
- **circle**: Circle marker at a specific position
- **triangle**: Triangle marker pointing upward
- **pin**: Pin/marker with a line and circle

## Drawing Primitives

- **horizontal-line**: Line spanning track width or a specific range
- **background**: Colored background for a track section
