#!/bin/bash
set -e

# Check if building for local preview or GitHub Pages
BUILD_MODE=${1:-production}

if [ "$BUILD_MODE" = "local" ]; then
  echo "Building BGC Viewer Documentation (LOCAL MODE)..."
  VITEPRESS_BASE="/"
else
  echo "Building BGC Viewer Documentation (PRODUCTION MODE)..."
  VITEPRESS_BASE="/bgc-viewer/"
fi
echo

# Build VitePress documentation
echo "Building VitePress documentation (base: $VITEPRESS_BASE)..."
cd docs/guide
npm ci --silent
VITEPRESS_BASE=$VITEPRESS_BASE npm run docs:build
echo "✓ VitePress documentation built successfully"
echo

cd ../..

# Copy to _site directory
echo "Preparing documentation site..."
rm -rf _site
mkdir -p _site
cp -r docs/guide/.vitepress/dist/* _site/

echo "✓ Documentation build complete"
echo
echo "Built documentation is available in: _site/"
echo
echo "To preview locally, run:"
echo "  ./scripts/serve-docs.sh"
