#!/bin/bash

# Exit on any error
set -e

# Extract version from pyproject.toml
VERSION=$(grep '^version = ' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

echo "Building BGC Viewer version ${VERSION}..."

# Change to the project root directory
cd "$(dirname "$0")"


### ---------- Frontend ---------- ####

# Build frontend first
echo "=== Building Frontend ==="
cd frontend

# Clean previous build
rm -rf build/ dist/

# Install dependencies and build
npm install
npm run build

# Build web components
echo "Building web components..."
npm run build:web-components

# Verify build output
if [ ! -f "build/index.html" ]; then
    echo "Error: Frontend build failed - index.html not found in build/"
    exit 1
fi

echo "Frontend build completed successfully!"
echo "Output: frontend/build/"
ls -la build/

cd ..


### ---------- Backend ---------- ####

# Build backend (which includes copying frontend assets)
echo ""
echo "=== Building Backend ==="
cd backend

# Clean previous build
rm -rf dist/ bgc_viewer.egg-info/

# Copy frontend build files to static directory
echo "Copying frontend assets..."
if [ -d "../frontend/build" ]; then
    # Clean and recreate static directory to avoid accumulating old files
    rm -rf bgc_viewer/static
    mkdir -p bgc_viewer/static
    cp -r ../frontend/build/* bgc_viewer/static/
    echo "Frontend assets copied to bgc_viewer/static/"
else
    echo "Warning: Frontend not built. Something went wrong."
    exit 1
fi

# Build Rust extension and Python package with maturin
echo "Building Python package with Rust extension..."
if command -v cargo &> /dev/null; then
    echo "Building with Rust extension..."
    uv pip install maturin
    uv run maturin build --release --manifest-path rust_extensions/Cargo.toml --out dist
else
    echo "Warning: Rust not found. Building without Rust extension (slower preprocessing)."
    echo "To get the optimized version, install Rust: https://rustup.rs/"
    uv build
fi

# Verify build output
WHEEL_FILE=$(ls dist/bgc_viewer-${VERSION}-*.whl 2>/dev/null | head -n 1)
if [ -z "$WHEEL_FILE" ]; then
    echo "Error: No Python wheel was created"
    exit 1
fi

echo "Built wheel: $(basename $WHEEL_FILE)"

# Check wheel contents
echo "Checking package contents:"
python -m zipfile -l "$WHEEL_FILE" | grep -E "(static|index\.html|\.js|\.css|bgc_scanner)" || echo "Warning: Expected files not found in wheel"

echo "Backend build completed successfully!"
echo "Output: backend/dist/"
ls -la dist/

cd ..

echo ""
echo "=== Build Complete ==="
echo "Frontend build: frontend/build/"
echo "Backend package: backend/dist/"
echo ""
echo "To test the package:"
echo "  pip install backend/dist/bgc_viewer-${VERSION}-py3-none-any.whl"
echo "  bgc-viewer"
