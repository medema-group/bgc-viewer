# BGC Viewer Documentation

This directory contains the complete documentation for the BGC Viewer project, built with VitePress.

## Documentation Structure

- **`guide/`** - VitePress documentation site (builds to `guide/.vitepress/dist/`)
  - User guides and tutorials
  - Component documentation and demos
  - REST API reference
  - Interactive examples

## Building Documentation

### Build for Local Preview

```bash
# Build with base path /
./scripts/build-docs.sh local

# Preview
./scripts/serve-docs.sh
```

Visit http://localhost:8080

### Build for GitHub Pages

```bash
# Build with base path /bgc-viewer/
./scripts/build-docs.sh
```

The built documentation will be in `_site/`.

## Deployment

Documentation is automatically deployed to GitHub Pages when changes are pushed to the main branch. See `.github/workflows/docs.yml` for the CI/CD configuration.

## Local Development

```bash
cd docs/guide
npm install
npm run docs:dev
```

Visit http://localhost:5173 (hot reload enabled)
