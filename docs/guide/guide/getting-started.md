# Getting Started

Welcome to BGC Viewer! This guide will help you get started with visualizing biosynthetic gene clusters.

## What is BGC Viewer?

BGC Viewer is an interactive visualization tool for exploring Biosynthetic Gene Clusters (BGCs) from antiSMASH output files. It provides:

- **Interactive track viewer** - Zoom, pan, and explore gene clusters
- **Domain annotations** - Visualize protein domains and their functions
- **Web components** - Easy integration into your own applications
- **Fast data processing** - Optimized with Rust extensions

## Architecture

BGC Viewer consists of two main components:

### Backend (Python + Flask)

The backend provides:
- Data preprocessing and indexing
- REST API for data access
- Database management
- File handling utilities

### Frontend (Vue.js + TypeScript)

The frontend provides:
- Interactive visualization components
- Web components for easy embedding
- Responsive UI

## Next Steps

- [Installation Guide](./installation.md) - Set up BGC Viewer
- [Quick Start](./quick-start.md) - Run your first visualization
- [Component Reference](../components/track-viewer.md) - Explore available components
