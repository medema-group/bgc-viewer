# BGC Viewer Components

A TypeScript library providing D3.js-based visualization components for biosynthetic gene clusters (BGCs) and genomic regions.

## Features

- **RegionViewer**: Interactive visualization of genomic regions with tracks and annotations
- **Multiple annotation types**: Arrows, boxes, and markers
- **Zoom and pan**: Interactive navigation through genomic regions
- **TypeScript support**: Full type definitions for better developer experience
- **Customizable**: Flexible configuration for styling and behavior

## Installation

```bash
npm install bgc-viewer-components
```

## Usage

### Basic Example

```typescript
import { RegionViewer } from 'bgc-viewer-components';

// Create a viewer instance
const viewer = new RegionViewer({
  container: '#my-container',
  width: 800,
  height: 400,
  domain: [0, 10000] // genomic coordinates
});

// Add track data
viewer.setData({
  tracks: [
    { id: 'genes', label: 'Gene Track' },
    { id: 'domains', label: 'Protein Domains' }
  ],
  annotations: [
    {
      id: 'gene1',
      trackId: 'genes',
      type: 'arrow',
      class: 'gene',
      label: 'Gene A',
      start: 1000,
      end: 3000,
      direction: 'right'
    },
    {
      id: 'domain1',
      trackId: 'domains',
      type: 'box',
      class: 'domain',
      label: 'PKS Domain',
      start: 1200,
      end: 1800,
      direction: 'none'
    }
  ]
});
```

### Configuration Options

```typescript
interface RegionViewerConfig {
  container: string | HTMLElement;    // CSS selector or DOM element
  width?: number;                     // Width in pixels (default: 800)
  height?: number;                    // Height in pixels (default: 300)
  margin?: {                         // Margins around the chart
    top: number;                     // Default: 20
    right: number;                   // Default: 30
    bottom: number;                  // Default: 20
    left: number;                    // Default: 60
  };
  rowHeight?: number;                // Height of each track row (default: 30)
  domain?: [number, number];         // Genomic coordinate range (default: [0, 100])
  zoomExtent?: [number, number];     // Zoom scale limits (default: [0.5, 20])
  onAnnotationClick?: (annotation: AnnotationData, track: TrackData) => void;
  onAnnotationHover?: (annotation: AnnotationData, track: TrackData, event: MouseEvent) => void;
}
```

### Annotation Types

#### Arrow Annotations
Perfect for representing genes with directionality:

```typescript
{
  type: 'arrow',
  direction: 'right' | 'left' | 'none',
  // ... other properties
}
```

#### Box Annotations
Ideal for domains, regions, or features without directionality:

```typescript
{
  type: 'box',
  // ... other properties
}
```

#### Marker Annotations
Useful for point features or binding sites:

```typescript
{
  type: 'marker',
  // ... other properties
}
```

### API Methods

#### Data Management
```typescript
// Set complete dataset
viewer.setData(data: RegionViewerData): void

// Add individual tracks and annotations
viewer.addTrack(track: TrackData, annotations?: AnnotationData[]): void
viewer.addAnnotation(annotation: AnnotationData): void

// Remove tracks and annotations
viewer.removeTrack(trackId: string): void
viewer.removeAnnotation(annotationId: string): void
```

#### Navigation
```typescript
// Update the visible genomic range
viewer.updateDomain(domain: [number, number]): void

// Zoom to specific region
viewer.zoomTo(start: number, end: number): void

// Reset zoom to original view
viewer.resetZoom(): void
```

#### Data Retrieval
```typescript
// Get current configuration
const config = viewer.getConfig(): Required<RegionViewerConfig>

// Get current data
const data = viewer.getData(): RegionViewerData
```

#### Cleanup
```typescript
// Remove viewer from DOM and clean up event listeners
viewer.destroy(): void
```

### Event Handling

```typescript
const viewer = new RegionViewer({
  container: '#container',
  onAnnotationClick: (annotation, track) => {
    console.log(`Clicked ${annotation.label} in ${track.label}`);
  },
  onAnnotationHover: (annotation, track, event) => {
    console.log(`Hovering over ${annotation.label}`);
  }
});
```

### Styling

The component generates SVG elements with CSS classes that can be styled:

```css
/* Track labels */
.track-label {
  font-family: sans-serif;
  font-size: 12px;
  fill: #333;
}

/* Annotation elements */
.annotation {
  fill: #steelblue;
  stroke: #fff;
  stroke-width: 1px;
}

.annotation:hover,
.annotation.hovered {
  fill: #orange;
}

/* Custom annotation classes */
.annotation.gene {
  fill: #2ecc71;
}

.annotation.domain {
  fill: #3498db;
}

/* Tooltip styling */
.region-viewer-tooltip {
  background: white;
  border: 1px solid #ccc;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 3px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
```

## Type Definitions

The library is fully typed with TypeScript:

```typescript
export interface TrackData {
  id: string;
  label: string;
}

export type AnnotationType = 'arrow' | 'box' | 'marker';

export interface AnnotationData {
  id: string;
  trackId: string;
  type: AnnotationType;
  class: string;
  label: string;
  start: number;
  end: number;
  direction: 'left' | 'right' | 'none';
}

export interface RegionViewerData {
  tracks: TrackData[];
  annotations: AnnotationData[];
}
```

## Browser Support

- Modern browsers supporting ES2015+
- SVG support required
- Tested with Chrome, Firefox, Safari, and Edge

## Dependencies

- [D3.js](https://d3js.org/) v7.x for data visualization and DOM manipulation

## Development

```bash
# Install dependencies
npm install

# Build for development with watch mode
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Type check (via TypeScript compiler)
npx tsc --noEmit
```

## License

Apache-2.0

## Contributing

Issues and pull requests are welcome! Please ensure all tests pass and follow the existing code style.

## Related Projects

- [BGC Viewer](../README.md) - The main application using this component library
