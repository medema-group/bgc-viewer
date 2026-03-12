# Vue.js TrackViewer Demo

A Vue 3 + Vite application demonstrating the TrackViewer component from `@medemagroup/bgc-viewer-components`.

## Features

- **Interactive track visualization** - Zoom and pan through genomic regions
- **Multiple records and regions** - Switch between different records and BGC regions
- **Gene annotations** - Color-coded by function (biosynthetic, transport, regulatory, etc.)
- **Click interactions** - Click on genes to see details
- **Responsive controls** - Reset zoom and fit to screen
- **Modern build setup** - Vite + Vue 3 with hot module replacement

## Prerequisites

- Node.js 18+ and npm installed

## Installation

```bash
# Install dependencies
npm install
```

## Running the Demo

```bash
# Start development server with hot reload
npm run dev

# Then open: http://localhost:5174
```

The dev server needs to run from the repository root to access the data files. If you're in the `example-project` directory, run:

```bash
# From demos/example-project directory
cd ../..
npm --prefix demos/example-project run dev
```

## Building for Production

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
example-project/
├── src/
│   ├── App.vue         # Main Vue component
│   ├── main.js         # Application entry point
│   └── style.css       # Global styles
├── index.html          # HTML entry point
├── vite.config.js      # Vite configuration
├── package.json        # Dependencies and scripts
└── README.md           # This file
```

## How It Works

1. **Data Loading**: Loads antiSMASH JSON data from `../data/NC_003888.3.json`
2. **TrackViewer**: Creates a TrackViewer instance with gene annotations
3. **Vue.js Reactivity**: Uses Vue.js for UI controls and state management
4. **Gene Coloring**: Colors genes by function:
   - Red: Biosynthetic genes
   - Blue: Transport genes
   - Purple: Regulatory genes
   - Orange: Resistance genes
   - Gray: Other/Unknown

## Customization

### Change Data Source

Edit the fetch URL in `index.html`:

```javascript
const response = await fetch('../data/YOUR_FILE.json');
```

### Adjust Viewer Size

Modify the TrackViewer configuration:

```javascript
this.trackViewer = new TrackViewer({
  width: 1200,  // Change width
  height: 400,  // Change height
  trackHeight: 60,  // Height of each track
  // ... other options
});
```

### Color Scheme

Modify the `getGeneColor()` method to change gene colors based on your criteria.

## API Reference

For full TrackViewer API documentation, see:
- [TrackViewer Component Docs](https://github.com/medema-group/bgc-viewer/tree/main/docs/guide/components/track-viewer.md)
- [npm Package](https://www.npmjs.com/package/@medemagroup/bgc-viewer-components)

## Troubleshooting

### Data not loading

- Make sure you're running a web server (not opening `index.html` directly)
- Check that the data file exists at `../data/NC_003888.3.json`
- Check the browser console for CORS errors

### Dependencies not found

```bash
npm install
```

### TrackViewer not rendering

- Check that D3.js is loaded (it's a peer dependency)
- Verify the container element exists
- Check browser console for errors

## License

Apache-2.0
