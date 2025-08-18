#!/bin/bash

# Exit on any error
set -e

echo "Building BGC Viewer (Frontend + Backend)..."

# Change to the project root directory
cd "$(dirname "$0")"

# Build frontend first
echo "=== Building Frontend ==="
cd frontend

# Clean previous build
rm -rf build/ dist/

# Install dependencies and build
npm install
npm run build

# Verify build output
if [ ! -f "build/index.html" ]; then
    echo "Error: Frontend build failed - index.html not found in build/"
    exit 1
fi

echo "Frontend build completed successfully!"
echo "Output: frontend/build/"
ls -la build/

cd ..

# Build backend (which includes copying frontend assets)
echo ""
echo "=== Building Backend ==="
cd backend

# Clean previous build
rm -rf dist/ bgc_viewer.egg-info/

# Copy frontend build files to static directory
echo "Copying frontend assets..."
if [ -d "../frontend/build" ]; then
    mkdir -p bgc_viewer/static
    cp -r ../frontend/build/* bgc_viewer/static/
    echo "Frontend assets copied to bgc_viewer/static/"
else
    echo "Warning: Frontend not built. Something went wrong."
    exit 1
fi

# Build Python package
echo "Building Python package..."
python -m build

# Verify build output
if [ ! -f "dist/bgc_viewer-0.1.1-py3-none-any.whl" ]; then
    echo "Error: Python wheel was not created"
    exit 1
fi

# Check wheel contents
echo "Checking package contents:"
python -m zipfile -l dist/bgc_viewer-0.1.1-py3-none-any.whl | grep -E "(static|index\.html|\.js|\.css)" || echo "Warning: No static files found in wheel"

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
echo "  pip install backend/dist/bgc_viewer-0.1.1-py3-none-any.whl"
echo "  bgc-viewer"
